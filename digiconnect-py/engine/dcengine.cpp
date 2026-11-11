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
#include <cstdio>
#ifdef Q_OS_WIN
#include <io.h>
#include <fcntl.h>
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
        QJsonArray in, out;
        for (const auto &d : QMediaDevices::audioInputs()) in.append(d.description());
        for (const auto &d : QMediaDevices::audioOutputs()) out.append(d.description());
        emit_ev({{"ev", "devices"}, {"inputs", in}, {"outputs", out}});
    } else if (cmd == "connect") {
        connect_to(c);
    } else if (cmd == "disconnect") {
        teardown("disconnected", "");
    } else if (cmd == "ptt") {
        if (m_status == Mode::CONNECTED_RW || m_status == Mode::CONNECTED_RO) {
            if (c.value("on").toBool()) emit tx_pressed(); else emit tx_released();
        }
    } else if (cmd == "volume") {
        emit in_vol(c.value("in").toDouble(0.5));
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
        m_mode->set_iax_params(c.value("iax_user").toString(), c.value("iax_pass").toString(), "", refname, host, port);
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
    if (m_status == Mode::CONNECTING && i.status == Mode::DISCONNECTED) { teardown("error", "Connection refused or no answer from the server"); return; }
    if (m_status == Mode::CONNECTING && (i.status == Mode::CONNECTED_RW || i.status == Mode::CONNECTED_RO)) {
        m_status = i.status;
        emit swrx(1); emit swtx(1); emit in_vol(0.5);
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
    return rc;
}
