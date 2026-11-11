// dcengine — headless protocol engine controlled with JSON lines on stdin/stdout.
#pragma once
#include <QObject>
#include <QJsonObject>
#include "src/mode.h"

class Engine : public QObject {
    Q_OBJECT
public:
    explicit Engine(QObject *parent = nullptr);
public slots:
    void handle(const QJsonObject &cmd);
    void on_update(Mode::MODEINFO info);
    void on_log(QString s);
    void on_level(unsigned short l);
signals:
    void tx_pressed();
    void tx_released();
    void in_vol(qreal);
    void out_vol(qreal);
    void swrx(int);
    void swtx(int);
    void agc(int);
    void dmr_tg(int);
    void dtmf(QByteArray);
private:
    void connect_to(const QJsonObject &c);
    void test_mic(const QString &name, int ms);
    void test_spk(const QString &name);
    void teardown(const QString &state, const QString &msg);
    void emit_ev(const QJsonObject &o);
    Mode *m_mode = nullptr;
    QThread *m_thread = nullptr;
    int m_status = Mode::DISCONNECTED;
    QString m_proto;
    qint64 m_lastLevel = 0;
    double m_inVol = 1.0;      // microphone level (1 = full device level; above 1 = software gain)
};
