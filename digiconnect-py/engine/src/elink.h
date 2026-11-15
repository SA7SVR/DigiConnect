// EchoLink station-to-station voice (RTP/RTCP over UDP, GSM 06.10 audio).
// The directory (login, station list) is handled by the application; this mode only talks to one station.
#ifndef ELINK_H
#define ELINK_H

#include "mode.h"

extern "C" {
#include "gsm/gsm.h"
}

class ELINK : public Mode
{
	Q_OBJECT
public:
	ELINK();
	~ELINK();
	void set_el_params(QString name, QString location) override { m_name = name; m_loc = location; }

	// Packet builders / parsers are public static so the self-test and the unit tests can use them without a socket.
	static QByteArray build_rtcp_sdes(quint32 ssrc, const QString &call, const QString &name, const QString &loc);
	static QByteArray build_rtcp_bye(quint32 ssrc, const QString &reason);
	static QByteArray build_rtp(quint16 seq, quint32 ts, quint32 ssrc, const QByteArray &payload, int pt = 3);
	struct RtcpInfo { bool sdes = false, bye = false; QString cname, name; };
	static RtcpInfo parse_rtcp(const QByteArray &b);
	struct RtpInfo { bool ok = false; int pt = 0; quint16 seq = 0; quint32 ts = 0, ssrc = 0; QByteArray payload; };
	static RtpInfo parse_rtp(const QByteArray &b);

private slots:
	void deleteLater();
	void hostname_lookup(QHostInfo i);
	void send_disconnect();
	void process_rtp();
	void process_rtcp();
	void tick();
	void process_rx_data();
	void start_tx();
	void stop_tx();
	void toggle_tx(bool);
	void transmit();
	void send_dtmf(QByteArray);
private:
	void handle_rtcp(const QByteArray &b);
	void handle_rtp(const QByteArray &b);
	void send_sdes();
	void send_audio_packet(const int16_t *pcm640);
	void connected();
	void end_rx();
	void hexlog(const char *dir, const QByteArray &b);

	QString m_name, m_loc, m_peer;
	QUdpSocket *m_rtp = nullptr, *m_rtcp = nullptr;
	quint16 m_remote_rtp = 5198, m_remote_rtcp = 5199;
	quint32 m_ssrc = 0;
	quint16 m_seq = 0;
	quint32 m_rtpts = 0;
	gsm m_genc = nullptr, m_gdec = nullptr;
	QQueue<int16_t> m_audioq;        // decoded sound waiting for the speakers
	QQueue<int16_t> m_txq;           // microphone / DTMF sound waiting to be sent
	QQueue<int16_t> m_dtmfq;
	bool m_connected = false, m_rxactive = false, m_playing = false;
	qint64 m_lastheard = 0, m_lastrx = 0, m_laststream = 0;
	int m_ticks = 0, m_hexlogged = 0;
	quint16 m_lastseq = 0;
	bool m_haveseq = false;
};

#endif
