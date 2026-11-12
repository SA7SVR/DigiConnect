// dcengine — headless protocol engine. One link at a time (multi-receiver comes later).
// Control: JSON lines on stdin.  Events: JSON lines on stdout.  Diagnostics: stderr.
#include "dcengine.h"
#include <QCoreApplication>
#include <QJsonDocument>
#include <QSocketNotifier>
#include <QMediaDevices>
#include <QAudioDevice>
#include <QJsonArray>
#include <QTimer>
#include <QAudioSource>
#include <QAudioSink>
#include <QBuffer>
#include <memory>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#ifdef Q_OS_WIN
#include <io.h>
#include <fcntl.h>
#include <process.h>
#else
#include <unistd.h>
#endif

Engine::Engine(QObject *parent) : QObject(parent) {
    qRegisterMetaType<Mode::MODEINFO>("Mode::MODEINFO");
}

void Engine::emit_ev(const QJsonObject &o) {
    QByteArray b = QJsonDocument(o).toJson(QJsonDocument::Compact) + "\n";
    fwrite(b.constData(), 1, b.size(), stdout);
    fflush(stdout);
}

void Engine::handle(const QJsonObject &c) {
    const QString cmd = c.value("cmd").toString();
    if (cmd == "hello") {
        emit_ev({{"ev", "hello"}, {"engine", "dcengine"}, {"version", "1"}});
    } else if (cmd == "devices") {
        // Names exactly as the audio code matches them (Qt descriptions), so a choice made in the UI always finds its device.
        QJsonArray in, out;
        for (const auto &d : QMediaDevices::audioInputs()) in.append(d.description());
        for (const auto &d : QMediaDevices::audioOutputs()) out.append(d.description());
        emit_ev({{"ev", "devices"}, {"inputs", in}, {"outputs", out},
                 {"default_in", QMediaDevices::defaultAudioInput().description()}, {"default_out", QMediaDevices::defaultAudioOutput().description()}});
    } else if (cmd == "test_mic") {
        test_mic(c.value("device").toString(), c.value("ms").toInt(1500));
    } else if (cmd == "test_spk") {
        test_spk(c.value("device").toString());
    } else if (cmd == "connect") {
        connect_to(c);
    } else if (cmd == "disconnect") {
        teardown("disconnected", "");
    } else if (cmd == "ptt") {
        if (m_status == Mode::CONNECTED_RW || m_status == Mode::CONNECTED_RO) {
            if (c.value("on").toBool()) emit tx_pressed(); else emit tx_released();
        }
    } else if (cmd == "volume") {
        m_inVol = c.value("in").toDouble(1.0); emit in_vol(m_inVol);
    } else if (cmd == "out_volume") {
        emit out_vol(c.value("out").toDouble(1.0));
    } else if (cmd == "agc") {
        emit agc(c.value("on").toBool());
    } else if (cmd == "tg") {
        emit dmr_tg(c.value("tg").toInt());
    } else if (cmd == "dtmf") {
        emit dtmf(c.value("keys").toString().toUtf8());
    } else if (cmd == "quit") {
        teardown("disconnected", "");
        QCoreApplication::quit();
    }
}

static double peak_of(const QByteArray &b, QAudioFormat::SampleFormat f) {
    double pk = 0;
    const char *p = b.constData();
    switch (f) {
    case QAudioFormat::UInt8:   for (int i = 0; i < b.size(); ++i) pk = std::max(pk, std::fabs(((uint8_t)p[i] - 128) / 128.0)); break;
    case QAudioFormat::Int32:   for (int i = 0; i + 3 < b.size(); i += 4) { int32_t x; memcpy(&x, p + i, 4); pk = std::max(pk, std::fabs(x / 2147483648.0)); } break;
    case QAudioFormat::Float:   for (int i = 0; i + 3 < b.size(); i += 4) { float x; memcpy(&x, p + i, 4); pk = std::max(pk, (double)std::fabs(x)); } break;
    default:                    for (int i = 0; i + 1 < b.size(); i += 2) { int16_t x; memcpy(&x, p + i, 2); pk = std::max(pk, std::fabs(x / 32768.0)); }
    }
    return pk;
}

// Microphone test: records for `ms` with the same Qt audio code the transmitter uses and reports the peak level.
void Engine::test_mic(const QString &name, int ms) {
    QAudioDevice dev = QMediaDevices::defaultAudioInput();
    for (const auto &d : QMediaDevices::audioInputs()) if (d.description() == name) dev = d;
    if (dev.isNull()) { emit_ev({{"ev", "test_mic"}, {"ok", false}, {"msg", "No microphone found"}}); return; }
    QAudioFormat f = dev.preferredFormat();
    auto *src = new QAudioSource(dev, f, this);
    QIODevice *io = src->start();
    if (!io) { emit_ev({{"ev", "test_mic"}, {"ok", false}, {"msg", "The microphone could not be opened"}, {"device", dev.description()}, {"error", (int)src->error()}}); src->deleteLater(); return; }
    auto peak = std::make_shared<double>(0.0); auto bytes = std::make_shared<qint64>(0);
    connect(io, &QIODevice::readyRead, this, [=] { QByteArray b = io->readAll(); *bytes += b.size(); *peak = std::max(*peak, peak_of(b, f.sampleFormat())); });
    QTimer::singleShot(ms, this, [=] {
        const int err = (int)src->error();
        src->stop();
        emit_ev({{"ev", "test_mic"}, {"ok", *bytes > 0}, {"peak", *peak}, {"bytes", (double)*bytes}, {"device", dev.description()}, {"rate", f.sampleRate()}, {"channels", f.channelCount()}, {"error", err}});
        src->deleteLater();
    });
}

// Speaker test: plays a short 880 Hz tone through the chosen output with the same Qt audio code the receiver uses.
void Engine::test_spk(const QString &name) {
    QAudioDevice dev = QMediaDevices::defaultAudioOutput();
    for (const auto &d : QMediaDevices::audioOutputs()) if (d.description() == name) dev = d;
    if (dev.isNull()) { emit_ev({{"ev", "test_spk"}, {"ok", false}, {"msg", "No speakers found"}}); return; }
    QAudioFormat f = dev.preferredFormat();
    const int rate = f.sampleRate() > 0 ? f.sampleRate() : 48000, ch = f.channelCount() > 0 ? f.channelCount() : 2;
    const int n = rate * 6 / 10;
    QByteArray data;
    for (int i = 0; i < n; ++i) {
        const double env = std::min(1.0, std::min(i, n - i) / (rate * 0.03));
        const double v = 0.3 * env * std::sin(2 * M_PI * 880.0 * i / rate);
        for (int c = 0; c < ch; ++c) {
            switch (f.sampleFormat()) {
            case QAudioFormat::UInt8: { uint8_t x = (uint8_t)(128 + v * 127); data.append((char)x); break; }
            case QAudioFormat::Int32: { int32_t x = (int32_t)(v * 2147483647.0); data.append((const char *)&x, 4); break; }
            case QAudioFormat::Float: { float x = (float)v; data.append((const char *)&x, 4); break; }
            default: { int16_t x = (int16_t)(v * 32767.0); data.append((const char *)&x, 2); }
            }
        }
    }
    auto *buf = new QBuffer(this); buf->setData(data); buf->open(QIODevice::ReadOnly);
    auto *sink = new QAudioSink(dev, f, this);
    sink->start(buf);
    QTimer::singleShot(900, this, [=] {
        const int err = (int)sink->error();
        sink->stop();
        emit_ev({{"ev", "test_spk"}, {"ok", err == 0}, {"device", dev.description()}, {"rate", rate}, {"channels", ch}, {"error", err}});
        sink->deleteLater(); buf->deleteLater();
    });
}

void Engine::connect_to(const QJsonObject &c) {
    if (m_mode) teardown("disconnected", "");
    m_proto = c.value("mode").toString();
    const QString host = c.value("host").toString();
    const int port = c.value("port").toInt();
    const QString callsign = c.value("callsign").toString().simplified();
    if (m_proto.isEmpty() || host.isEmpty() || port <= 0 || callsign.isEmpty()) {
        emit_ev({{"ev", "status"}, {"state", "error"}, {"msg", "mode, host, port and callsign are required"}});
        return;
    }
    m_status = Mode::CONNECTING;
    emit_ev({{"ev", "status"}, {"state", "connecting"}, {"mode", m_proto}, {"host", host}, {"port", port}});

    const QString module = c.value("module").toString();
    const QString refname = c.value("name").toString(host);
    m_mode = Mode::create_mode(m_proto);
    if (!m_mode) { teardown("error", "Unsupported mode " + m_proto); return; }
    m_thread = new QThread;
    m_mode->moveToThread(m_thread);

    if (m_proto == "IAX") {
        m_mode->set_iax_params(c.value("iax_user").toString(), c.value("iax_pass").toString(), c.value("iax_name").toString(), refname, host, port);
        connect(this, SIGNAL(dtmf(QByteArray)), m_mode, SLOT(send_dtmf(QByteArray)));
    }
    m_mode->init(callsign, (uint32_t)c.value("dmrid").toDouble(), (uint16_t)c.value("nxdnid").toInt(),
                 module.isEmpty() ? ' ' : module.at(0).toLatin1(), refname, host, port, c.value("ipv6").toBool(),
                 c.value("vocoder").toString("Software vocoder"), "", c.value("capture").toString(), c.value("playback").toString(), false);
    m_mode->set_modem_flags(false, true, false, false, false);
    m_mode->set_modem_params(115200, 0, 0, 100, 50, 100, 4, 50, 50, 50, 50, 50, 50, 50, 50);

    connect(m_mode, SIGNAL(update(Mode::MODEINFO)), this, SLOT(on_update(Mode::MODEINFO)));
    connect(m_mode, SIGNAL(update_log(QString)), this, SLOT(on_log(QString)));
    connect(m_mode, SIGNAL(update_output_level(unsigned short)), this, SLOT(on_level(unsigned short)));
    connect(m_thread, SIGNAL(started()), m_mode, SLOT(begin_connect()));
    connect(m_thread, SIGNAL(finished()), m_mode, SLOT(deleteLater()));
    connect(this, SIGNAL(tx_pressed()), m_mode, SLOT(start_tx()));
    connect(this, SIGNAL(tx_released()), m_mode, SLOT(stop_tx()));
    connect(this, SIGNAL(in_vol(qreal)), m_mode, SLOT(in_audio_vol_changed(qreal)));
    connect(this, SIGNAL(out_vol(qreal)), m_mode, SLOT(out_audio_vol_changed(qreal)));
    connect(this, SIGNAL(swrx(int)), m_mode, SLOT(swrx_state_changed(int)));
    connect(this, SIGNAL(swtx(int)), m_mode, SLOT(swtx_state_changed(int)));
    connect(this, SIGNAL(agc(int)), m_mode, SLOT(agc_state_changed(int)));

    if (m_proto == "DMR") {
        QString pass = c.value("password").toString();
        m_mode->set_dmr_params((uint8_t)c.value("essid").toInt(), pass, c.value("lat").toString("0"), c.value("lon").toString("0"),
                               c.value("location").toString(), c.value("description").toString("DigiConnect"), c.value("freq").toString("438800000"),
                               c.value("url").toString(), c.value("swid").toString("DigiConnect"), c.value("pkgid").toString("DigiConnect"), c.value("options").toString());
        m_mode->set_dmr_cc(c.value("cc").toInt(1));
        connect(this, SIGNAL(dmr_tg(int)), m_mode, SLOT(dmr_tgid_changed(int)));
        emit dmr_tg(c.value("tg").toInt());
    }
    m_thread->start();
    // Connectionless protocols (C4FM, D-Star, NXDN, P25, M17 ...) only know they are connected when the server answers. When it never does,
    // say so instead of showing a link that is not there.
    Mode *started = m_mode;
    QTimer::singleShot(15000, this, [this, started] {
        if (m_mode == started && m_mode && m_status == Mode::CONNECTING)
            teardown("error", "No answer from the server within 15 seconds - check the address and port, and that the network does not block UDP");
    });
}

void Engine::teardown(const QString &state, const QString &msg) {
    if (m_thread) {
        m_thread->quit();
        m_thread->wait(3000);
        m_thread->deleteLater();
        m_thread = nullptr;
    }
    m_mode = nullptr;
    m_status = Mode::DISCONNECTED;
    QJsonObject o{{"ev", "status"}, {"state", state}};
    if (!msg.isEmpty()) o["msg"] = msg;
    emit_ev(o);
}

void Engine::on_update(Mode::MODEINFO i) {
    if (!m_mode) return;
    if (m_status == Mode::CONNECTING && i.status == Mode::DISCONNECTED) {
        teardown("error", i.netmsg.startsWith("DMR_") ? i.netmsg : QString("Connection refused or no answer from the server"));       // DMR_NAK_*: the master answered and refused (see DMR::process_udp)
        return;
    }
    if (m_status == Mode::CONNECTING && (i.status == Mode::CONNECTED_RW || i.status == Mode::CONNECTED_RO)) {
        m_status = i.status;
        emit swrx(1); emit swtx(1); emit in_vol(m_inVol);
        emit_ev({{"ev", "status"}, {"state", "connected"}, {"rw", i.status == Mode::CONNECTED_RW}, {"vocoder", i.sw_vocoder_loaded}});
        return;
    }
    if ((m_status == Mode::CONNECTED_RW || m_status == Mode::CONNECTED_RO) && (i.status == Mode::TIMEOUT || i.status == Mode::DISCONNECTED || i.status == Mode::CLOSED)) {
        teardown("timeout", "The server stopped answering");
        return;
    }
    static const char *names[] = {"new", "streaming", "end", "lost", "idle", "tx", "tx", "unknown", "packet", "packet"};
    if (i.stream_state >= 0 && i.stream_state <= Mode::PACKET_SENT && i.stream_state != Mode::STREAM_IDLE) {
        // Keep printable ASCII only: protocol fields are fixed-width and may carry padding/garbage bytes.
        auto clean = [](const QString &s) {
            QString r;
            for (const QChar &c : s) if (c.unicode() >= 0x20 && c.unicode() < 0x7f) r.append(c); else break;
            return r.simplified();
        };
        QJsonObject o{{"ev", "rx"}, {"state", names[i.stream_state]}, {"mode", m_proto}, {"callsign", clean(i.callsign)}, {"src", clean(i.src)}, {"dst", clean(i.dst)},
                      {"gw", clean(i.gw)}, {"srcid", (double)i.srcid}, {"dstid", (double)i.dstid}, {"stream", (double)i.streamid}, {"usertxt", clean(i.usertxt)}};
        emit_ev(o);
    }
}

void Engine::on_log(QString s) { emit_ev({{"ev", "log"}, {"text", s}}); }

void Engine::on_level(unsigned short l) {
    qint64 now = QDateTime::currentMSecsSinceEpoch();
    if (now - m_lastLevel < 80) return;
    m_lastLevel = now;
    emit_ev({{"ev", "level"}, {"out", (int)l}});
}

int main(int argc, char **argv) {
#ifdef Q_OS_WIN
    _setmode(_fileno(stdout), _O_BINARY); _setmode(_fileno(stdin), _O_BINARY);
#endif
    QCoreApplication app(argc, argv);
    Engine eng;
    // Read stdin on a helper thread (works on every OS, including Windows pipes).
    class Reader : public QThread { public: Engine *e; void run() override {
        char buf[65536];
        while (fgets(buf, sizeof buf, stdin)) {
            QJsonDocument d = QJsonDocument::fromJson(QByteArray(buf));
            if (d.isObject()) QMetaObject::invokeMethod(e, [this, o = d.object()] { e->handle(o); }, Qt::QueuedConnection);
        }
        QMetaObject::invokeMethod(e, [] { QCoreApplication::quit(); }, Qt::QueuedConnection);   // parent closed the pipe
    } };
    Reader r; r.e = &eng; r.start();
    int rc = app.exec();
    r.wait(200);
    // The reader thread may still be blocked in fgets(): destroying a running QThread aborts the process (exit code 6, a "crash" on every normal quit).
    fflush(stdout); fflush(stderr);
    _exit(rc);
}
