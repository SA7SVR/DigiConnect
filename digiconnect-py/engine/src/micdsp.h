// Microphone processing for the transmit path: input gain, 3-band equaliser, high-pass filter, noise gate,
// compressor and output level. Works on 8 kHz mono samples, after the resampler and before the audio queue.
// With every setting at its default the processing is bypassed exactly, so a station that never touches the
// microphone page transmits the same audio as before.
#ifndef MICDSP_H
#define MICDSP_H

#include <QJsonObject>
#include <cmath>

class MicDsp {
public:
    struct Settings {
        double gain = 0;        // dB, -12..12
        double bass = 0;        // dB, -12..12 (low shelf 250 Hz)
        double mid = 0;         // dB, -12..12 (peaking 1.5 kHz)
        double treble = 0;      // dB, -12..12 (high shelf 3 kHz)
        int highpass = 0;       // Hz: 0 (off), 80, 120 or 200
        double gate = -60;      // dB, -60..0; -60 = gate off
        double comp = 0;        // 0..100 %
        double out = 100;       // 0..150 %
    };

    void configure(const QJsonObject &o) {
        Settings s;
        s.gain = clampd(o.value("gain").toDouble(s.gain), -12, 12);
        s.bass = clampd(o.value("bass").toDouble(s.bass), -12, 12);
        s.mid = clampd(o.value("mid").toDouble(s.mid), -12, 12);
        s.treble = clampd(o.value("treble").toDouble(s.treble), -12, 12);
        s.highpass = o.value("highpass").toInt(s.highpass);
        s.gate = clampd(o.value("gate").toDouble(s.gate), -60, 0);
        s.comp = clampd(o.value("comp").toDouble(s.comp), 0, 100);
        s.out = clampd(o.value("out").toDouble(s.out), 0, 150);
        set(s);
    }

    void set(const Settings &s) {
        m_s = s;
        const double fs = 8000.0;
        m_gain = std::pow(10.0, m_s.gain / 20.0);
        m_out = m_s.out / 100.0;
        m_hp_on = m_s.highpass > 0;
        if (m_hp_on) biquad_highpass(m_hp, m_s.highpass, fs);
        m_eq_on = m_s.bass != 0 || m_s.mid != 0 || m_s.treble != 0;
        if (m_s.bass != 0) biquad_shelf(m_lo, 250.0, m_s.bass, fs, false);
        if (m_s.mid != 0) biquad_peak(m_mid, 1500.0, m_s.mid, fs);
        if (m_s.treble != 0) biquad_shelf(m_hi, 3000.0, m_s.treble, fs, true);
        m_gate_on = m_s.gate > -60.0;
        m_gate_thr = 32767.0 * std::pow(10.0, m_s.gate / 20.0);
        m_comp_on = m_s.comp > 0;
        m_ratio = 1.0 + 7.0 * m_s.comp / 100.0;          // 1:1 at 0 %, 8:1 at 100 %
        m_comp_thr = 32767.0 * std::pow(10.0, -20.0 / 20.0);   // compressor works above -20 dBFS
    }

    const Settings &settings() const { return m_s; }
    bool gate_open() const { return !m_gate_on || m_gate_g > 0.5f; }
    double limit_db() const { return m_lim >= 1.0f ? 0.0 : 20.0 * std::log10((double)m_lim); }   // gain taken off by the limiter (dB, <= 0)
    bool bypass() const { return !m_hp_on && !m_eq_on && !m_gate_on && !m_comp_on && m_gain == 1.0 && m_out == 1.0; }

    float process(float x) {
        if (bypass()) return x;
        float y = x * (float)m_gain;
        if (m_hp_on) y = m_hp.run(y, m_hp_z);
        if (m_s.bass != 0) y = m_lo.run(y, m_lo_z);
        if (m_s.mid != 0) y = m_mid.run(y, m_mid_z);
        if (m_s.treble != 0) y = m_hi.run(y, m_hi_z);
        const float a = std::fabs(y);
        // level follower: fast attack, slow release (5 ms / 120 ms at 8 kHz)
        m_env = a > m_env ? m_att * m_env + (1 - m_att) * a : m_rel * m_env + (1 - m_rel) * a;
        if (m_gate_on) {
            const double target = m_env >= m_gate_thr ? 1.0 : 0.0;
            m_gate_g += (float)((target - m_gate_g) * (target > m_gate_g ? 0.05 : 0.002));   // opens quickly, closes gently
            y *= m_gate_g;
        }
        if (m_comp_on && m_env > m_comp_thr) {
            const double db_in = 20.0 * std::log10(m_env / m_comp_thr);
            const double db_out = db_in / m_ratio;
            y *= (float)std::pow(10.0, -(db_in - db_out) / 20.0);
        }
        y *= (float)m_out;
        // Limiter with 1 ms look-ahead: the gain is lowered before a peak arrives and released slowly afterwards,
        // so loud speech gets quieter without flat-topped (clipped) peaks, which are what sound harsh.
        const float knee = 0.8f * 32767.0f;
        m_la[m_la_i] = y; m_la_i = (m_la_i + 1) % kLook;
        const float out = m_la[m_la_i];                       // the sample from kLook samples ago
        float peak = 0;
        for (int k = 0; k < kLook; ++k) peak = std::fmax(peak, std::fabs(m_la[k]));
        const float target = peak > knee ? knee / peak : 1.0f;
        if (target < m_lim) m_lim = target; else m_lim += (target - m_lim) * 0.0005f;
        y = out * m_lim;
        if (y > 32767.0f) y = 32767.0f; else if (y < -32768.0f) y = -32768.0f;   // safety only
        return y;
    }

private:
    struct Biquad {
        double b0 = 1, b1 = 0, b2 = 0, a1 = 0, a2 = 0;
        float run(float x, double *z) {               // direct form II transposed; z = {z1, z2}
            const double y = b0 * x + z[0];
            z[0] = b1 * x - a1 * y + z[1];
            z[1] = b2 * x - a2 * y;
            return (float)y;
        }
    };
    static double clampd(double v, double lo, double hi) { return v < lo ? lo : (v > hi ? hi : v); }
    static void norm(Biquad &q, double b0, double b1, double b2, double a0, double a1, double a2) {
        q.b0 = b0 / a0; q.b1 = b1 / a0; q.b2 = b2 / a0; q.a1 = a1 / a0; q.a2 = a2 / a0;
    }
    static void biquad_highpass(Biquad &q, double fc, double fs) {          // RBJ cookbook, Q = 0.707
        const double w = 2 * M_PI * fc / fs, c = std::cos(w), al = std::sin(w) / (2 * 0.707);
        norm(q, (1 + c) / 2, -(1 + c), (1 + c) / 2, 1 + al, -2 * c, 1 - al);
    }
    static void biquad_peak(Biquad &q, double fc, double db, double fs) {   // RBJ cookbook, Q = 1
        const double A = std::pow(10.0, db / 40.0), w = 2 * M_PI * fc / fs, c = std::cos(w), al = std::sin(w) / 2;
        norm(q, 1 + al * A, -2 * c, 1 - al * A, 1 + al / A, -2 * c, 1 - al / A);
    }
    static void biquad_shelf(Biquad &q, double fc, double db, double fs, bool high) {   // RBJ cookbook, shelf slope S = 1
        const double A = std::pow(10.0, db / 40.0), w = 2 * M_PI * fc / fs, c = std::cos(w), s = std::sin(w);
        const double al = s / 2 * std::sqrt(2.0), sa = 2 * std::sqrt(A) * al;
        if (!high)
            norm(q, A * ((A + 1) - (A - 1) * c + sa), 2 * A * ((A - 1) - (A + 1) * c), A * ((A + 1) - (A - 1) * c - sa),
                 (A + 1) + (A - 1) * c + sa, -2 * ((A - 1) + (A + 1) * c), (A + 1) + (A - 1) * c - sa);
        else
            norm(q, A * ((A + 1) + (A - 1) * c + sa), -2 * A * ((A - 1) + (A + 1) * c), A * ((A + 1) + (A - 1) * c - sa),
                 (A + 1) - (A - 1) * c + sa, 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - sa);
    }

    Settings m_s;
    double m_gain = 1, m_out = 1, m_gate_thr = 0, m_comp_thr = 1, m_ratio = 1;
    bool m_hp_on = false, m_eq_on = false, m_gate_on = false, m_comp_on = false;
    Biquad m_hp, m_lo, m_mid, m_hi;
    double m_hp_z[2] = {0, 0}, m_lo_z[2] = {0, 0}, m_mid_z[2] = {0, 0}, m_hi_z[2] = {0, 0};
    float m_env = 0, m_gate_g = 1, m_lim = 1;
    static constexpr int kLook = 8;
    float m_la[kLook] = {0, 0, 0, 0, 0, 0, 0, 0};
    int m_la_i = 0;
    const float m_att = (float)std::exp(-1.0 / (0.005 * 8000.0));
    const float m_rel = (float)std::exp(-1.0 / (0.120 * 8000.0));
};

#endif // MICDSP_H
