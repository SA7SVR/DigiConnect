// Checks the microphone processing (engine/src/micdsp.h) on synthetic 8 kHz audio. Build and run:
#include <QJsonDocument>
//   g++ -std=c++17 -fPIC -I engine/src $(pkg-config --cflags --libs Qt6Core) engine/tests/check_micdsp.cpp -o micdsp_test && ./micdsp_test
#include "micdsp.h"
#include <QJsonObject>
#include <cstdio>
#include <cmath>

static int fails = 0;
static void check(bool ok, const char *what) { std::printf("%s  %s\n", ok ? "ok  " : "FAIL", what); if (!ok) ++fails; }

// steady-state peak of a sine of frequency f and amplitude a, measured after the filters have settled
static double sine_peak(MicDsp &d, double f, double a, double secs = 1.0) {
    const int n = (int)(8000 * secs), settle = 4000;
    double pk = 0;
    for (int i = 0; i < n; ++i) {
        const float y = d.process((float)(a * 32767.0 * std::sin(2 * M_PI * f * i / 8000.0)));
        if (i >= settle) pk = std::fmax(pk, std::fabs(y));
    }
    return pk / 32767.0;
}

static MicDsp make(const char *json) {
    MicDsp d; d.configure(QJsonDocument::fromJson(json).object()); return d;
}

int main() {
    // 1. default settings: bypassed exactly
    { MicDsp d; bool same = true; for (int i = 0; i < 1000; ++i) { float x = (float)(i * 37 % 2000 - 1000); if (d.process(x) != x) same = false; }
      check(same, "defaults pass the audio through unchanged"); }
    // 2. +6 dB input gain doubles the level (about 1 % tolerance)
    { MicDsp d = make("{\"gain\":6}"); double p = sine_peak(d, 1000, 0.25); check(std::fabs(p / 0.25 - 1.995) < 0.02, "input gain +6 dB doubles the level"); }
    // 3. output level 50 % halves it
    { MicDsp d = make("{\"out\":50}"); double p = sine_peak(d, 1000, 0.5); check(std::fabs(p / 0.5 - 0.5) < 0.01, "output level 50 % halves the level"); }
    // 4. high-pass 200 Hz removes rumble and keeps speech
    { MicDsp d = make("{\"highpass\":200}"); double low = sine_peak(d, 50, 0.5); MicDsp e = make("{\"highpass\":200}"); double mid = sine_peak(e, 1000, 0.5);
      check(low / 0.5 < 0.15, "high-pass 200 Hz cuts 50 Hz rumble"); check(mid / 0.5 > 0.9, "high-pass 200 Hz keeps 1 kHz speech"); }
    // 5. bass +12 dB lifts low frequencies more than the 1 kHz middle
    { MicDsp d0; double b0 = sine_peak(d0, 100, 0.1); MicDsp d = make("{\"bass\":12}"); double b = sine_peak(d, 100, 0.1);
      check(b / b0 > 3.0, "bass +12 dB raises 100 Hz by about 4x"); }
    // 6. treble -12 dB lowers 4 kHz and leaves 300 Hz
    { MicDsp d0; double t0 = sine_peak(d0, 3500, 0.1); MicDsp d = make("{\"treble\":-12}"); double t = sine_peak(d, 3500, 0.1);
      MicDsp e = make("{\"treble\":-12}"); double l = sine_peak(e, 300, 0.1); MicDsp f0; double l0 = sine_peak(f0, 300, 0.1);
      check(t / t0 < 0.5, "treble -12 dB lowers 3.5 kHz"); check(std::fabs(l / l0 - 1) < 0.05, "treble -12 dB leaves 300 Hz"); }
    // 7. noise gate: quiet hiss is silenced, a loud voice passes
    { MicDsp d = make("{\"gate\":-30}"); double hiss = sine_peak(d, 1000, 0.01, 2.0); check(hiss < 0.003, "noise gate -30 dB silences a -40 dB hiss");
      MicDsp e = make("{\"gate\":-30}"); double voice = sine_peak(e, 1000, 0.3, 2.0); check(voice > 0.27, "noise gate -30 dB passes a loud voice"); }
    // 8. compressor at 100 % lowers a loud peak
    { MicDsp d = make("{\"comp\":100}"); double p = sine_peak(d, 1000, 0.9, 2.0); check(p < 0.6, "compressor 100 % reduces a 0.9 full-scale peak"); }
    // 9. output never exceeds 16-bit range
    { MicDsp d = make("{\"gain\":12,\"out\":150}"); bool ok = true; for (int i = 0; i < 2000; ++i) { float y = d.process(30000.0f * (i % 2 ? 1 : -1)); if (y > 32767.0f || y < -32768.0f) ok = false; }
      check(ok, "output is clipped to 16 bit"); }
    // 10. loud input is limited softly: no flat-topped (clipped) run of samples, and full scale is never exceeded
    { MicDsp d = make("{\"gain\":12}"); int run = 0, worst = 0; float prev = 0; bool inrange = true;
      for (int i = 0; i < 8000; ++i) { float y = d.process((float)(0.9 * 32767.0 * std::sin(2 * M_PI * 500 * i / 8000.0))); if (std::fabs(y) > 32767.0f) inrange = false;
        run = (i > 2000 && y == prev) ? run + 1 : 0; if (run > worst) worst = run; prev = y; }
      check(inrange, "soft limiter keeps the output within full scale"); check(worst < 3, "soft limiter has no flat-topped (clipped) peaks"); }
    std::printf("%s\n", fails ? "FAILED" : "ALL OK");
    return fails ? 1 : 0;
}
