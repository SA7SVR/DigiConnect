#include "elink.h"
#include <cmath>
#include <cstring>
#include <QRandomGenerator>

// ---- packet helpers (no sockets; used by the engine, the self-test and the unit tests) ----------------------------------------------------------------

static void put32(QByteArray &b, quint32 v) { b.append(char(v >> 24)); b.append(char(v >> 16)); b.append(char(v >> 8)); b.append(char(v)); }
static void put16(QByteArray &b, quint16 v) { b.append(char(v >> 8)); b.append(char(v)); }
static void sdes_item(QByteArray &b, int type, const QString &s) { QByteArray t = s.toLatin1().left(255); b.append(char(type)); b.append(char(t.size())); b.append(t); }

QByteArray ELINK::build_rtcp_sdes(quint32 ssrc, const QString &call, const QString &name, const QString &loc)
{
	QByteArray out;
	out.append(char(0x80)); out.append(char(0xC9)); put16(out, 1); put32(out, ssrc);       // empty receiver report first, as EchoLink stations do
	QByteArray items;
	sdes_item(items, 1, call);                                                              // CNAME
	sdes_item(items, 2, call + "      " + name);                                           // NAME
	sdes_item(items, 3, QString());                                                         // EMAIL
	sdes_item(items, 4, QString());                                                         // PHONE
	sdes_item(items, 5, loc);                                                               // LOC
	sdes_item(items, 6, "DigiConnect");                                                     // TOOL
	items.append(char(0));
	while ((items.size() + 8) % 4) items.append(char(0));
	QByteArray sd;
	sd.append(char(0x81)); sd.append(char(0xCA)); put16(sd, quint16((items.size() + 4) / 4)); put32(sd, ssrc); sd.append(items);
	return out + sd;
}

QByteArray ELINK::build_rtcp_bye(quint32 ssrc, const QString &reason)
{
	QByteArray out;
	out.append(char(0x80)); out.append(char(0xC9)); put16(out, 1); put32(out, ssrc);
	QByteArray r = reason.toLatin1().left(255);
	QByteArray body; put32(body, ssrc); body.append(char(r.size())); body.append(r);
	while (body.size() % 4) body.append(char(0));
	QByteArray bye; bye.append(char(0x81)); bye.append(char(0xCB)); put16(bye, quint16(body.size() / 4)); bye.append(body);
	return out + bye;
}

QByteArray ELINK::build_rtp(quint16 seq, quint32 ts, quint32 ssrc, const QByteArray &payload, int pt)
{
	QByteArray p; p.append(char(0x80)); p.append(char(pt & 0x7f)); put16(p, seq); put32(p, ts); put32(p, ssrc); p.append(payload);
	return p;
}

ELINK::RtcpInfo ELINK::parse_rtcp(const QByteArray &b)
{
	RtcpInfo r; int pos = 0;
	while (pos + 4 <= b.size()) {
		const uchar v = uchar(b[pos]) >> 6, pt = uchar(b[pos + 1]);
		const int len = ((uchar(b[pos + 2]) << 8) | uchar(b[pos + 3]) ) * 4 + 4;
		if (v != 2 || len < 4 || pos + len > b.size()) break;
		if (pt == 203) r.bye = true;
		else if (pt == 202) {
			r.sdes = true;
			int i = pos + 8;                                                                // header (4) + SSRC (4)
			while (i + 2 <= pos + len) {
				const int type = uchar(b[i]); if (type == 0) break;
				const int l = uchar(b[i + 1]); if (i + 2 + l > pos + len) break;
				const QString s = QString::fromLatin1(b.mid(i + 2, l));
				if (type == 1) r.cname = s; else if (type == 2) r.name = s;
				i += 2 + l;
			}
		}
		pos += len;
	}
	return r;
}

ELINK::RtpInfo ELINK::parse_rtp(const QByteArray &b)
{
	RtpInfo r;
	if (b.size() < 12 || (uchar(b[0]) >> 6) != 2) return r;
	int hdr = 12 + 4 * (uchar(b[0]) & 0x0f);
	if (uchar(b[0]) & 0x10) { if (b.size() < hdr + 4) return r; hdr += 4 + 4 * ((uchar(b[hdr + 2]) << 8) | uchar(b[hdr + 3])); }
	if (b.size() < hdr) return r;
	r.pt = uchar(b[1]) & 0x7f;
	r.seq = quint16((uchar(b[2]) << 8) | uchar(b[3]));
	r.ts = (quint32(uchar(b[4])) << 24) | (quint32(uchar(b[5])) << 16) | (quint32(uchar(b[6])) << 8) | uchar(b[7]);
	r.ssrc = (quint32(uchar(b[8])) << 24) | (quint32(uchar(b[9])) << 16) | (quint32(uchar(b[10])) << 8) | uchar(b[11]);
	r.payload = b.mid(hdr); r.ok = true;
	return r;
}

// ---- the mode ----------------------------------------------------------------------------------------------------------------------------------------

ELINK::ELINK()
{
	m_mode = "ELINK";
	m_genc = gsm_create(); m_gdec = gsm_create();
	m_ssrc = quint32(QRandomGenerator::global()->generate());
	m_seq = quint16(QRandomGenerator::global()->generate());
	m_rtpts = QRandomGenerator::global()->generate();
}

ELINK::~ELINK()
{
	if (m_genc) gsm_destroy(m_genc);
	if (m_gdec) gsm_destroy(m_gdec);
}

void ELINK::hexlog(const char *dir, const QByteArray &b)
{
	if (m_hexlogged >= 12) return;                                                          // the first few packets only: enough to see what a real station sends
	++m_hexlogged;
	emit update_log(QString("EchoLink %1 %2 bytes: %3").arg(dir).arg(b.size()).arg(QString::fromLatin1(b.left(64).toHex(' '))));
}

void ELINK::hostname_lookup(QHostInfo i)
{
	if (i.addresses().isEmpty()) { m_modeinfo.status = DISCONNECTED; m_modeinfo.netmsg = "EL_The station address could not be found"; emit update(m_modeinfo); return; }
	m_address = i.addresses().first();
	m_remote_rtp = quint16(m_modeinfo.port > 0 ? m_modeinfo.port : 5198);
	m_remote_rtcp = quint16(m_remote_rtp + 1);
	m_rtp = new QUdpSocket(this); m_rtcp = new QUdpSocket(this);
	// A station answers to the ports it received from, and many only accept 5198/5199: bind them, and fall back to any port when another program (the EchoLink client) holds them.
	if (!m_rtp->bind(QHostAddress::AnyIPv4, 5198) || !m_rtcp->bind(QHostAddress::AnyIPv4, 5199)) {
		emit update_log("EchoLink: UDP 5198/5199 are in use by another program (is the EchoLink client running?); using other ports - stations may not be able to answer");
		m_rtp->close(); m_rtcp->close();
		m_rtp->bind(QHostAddress::AnyIPv4, 0); m_rtcp->bind(QHostAddress::AnyIPv4, 0);
	}
	connect(m_rtp, SIGNAL(readyRead()), this, SLOT(process_rtp()));
	connect(m_rtcp, SIGNAL(readyRead()), this, SLOT(process_rtcp()));
	m_modeinfo.status = CONNECTING;
	m_lastheard = QDateTime::currentMSecsSinceEpoch();
	m_ping_timer = new QTimer(this);
	connect(m_ping_timer, SIGNAL(timeout()), this, SLOT(tick()));
	m_ping_timer->start(1000);
	send_sdes();
}

void ELINK::send_sdes()
{
	if (!m_rtcp) return;
	const QByteArray p = build_rtcp_sdes(m_ssrc, m_modeinfo.callsign, m_name, m_loc);
	m_rtcp->writeDatagram(p, m_address, m_remote_rtcp);
	hexlog("SEND rtcp", p);
}

void ELINK::tick()
{
	const qint64 now = QDateTime::currentMSecsSinceEpoch();
	++m_ticks;
	if (!m_connected) { send_sdes(); return; }                                             // not answered yet: ask again every second
	if (m_ticks % 10 == 0) send_sdes();                                                     // keep-alive
	if (now - m_lastheard > 50000) {                                                        // the station went away without a goodbye
		m_modeinfo.status = TIMEOUT; emit update(m_modeinfo);
	}
}

void ELINK::process_rtcp()
{
	while (m_rtcp && m_rtcp->hasPendingDatagrams()) {
		QByteArray b; b.resize(int(m_rtcp->pendingDatagramSize()));
		QHostAddress from; quint16 port = 0;
		m_rtcp->readDatagram(b.data(), b.size(), &from, &port);
		if (from.isEqual(m_address, QHostAddress::TolerantConversion)) handle_rtcp(b);
	}
}

void ELINK::process_rtp()
{
	while (m_rtp && m_rtp->hasPendingDatagrams()) {
		QByteArray b; b.resize(int(m_rtp->pendingDatagramSize()));
		QHostAddress from; quint16 port = 0;
		m_rtp->readDatagram(b.data(), b.size(), &from, &port);
		if (from.isEqual(m_address, QHostAddress::TolerantConversion)) handle_rtp(b);
	}
}

void ELINK::handle_rtcp(const QByteArray &b)
{
	hexlog("RECV rtcp", b);
	m_lastheard = QDateTime::currentMSecsSinceEpoch();
	const RtcpInfo r = parse_rtcp(b);
	if (r.bye) {
		m_modeinfo.status = m_connected ? CLOSED : DISCONNECTED;
		m_modeinfo.netmsg = m_connected ? "EL_The station ended the connection" : "EL_The station refused the connection (it may be busy, or not accept your callsign)";
		emit update(m_modeinfo);
		return;
	}
	if (r.sdes) {
		QString nm = r.name.simplified(); if (nm.isEmpty()) nm = r.cname.simplified();
		if (!nm.isEmpty()) { m_peer = nm.section(' ', 0, 0); m_modeinfo.src = m_peer; m_modeinfo.gw = m_peer; m_modeinfo.usertxt = nm.section(' ', 1); }
	}
	if (!m_connected && (r.sdes || !r.bye)) connected();
}

void ELINK::connected()
{
	if (m_connected) return;
	m_connected = true;
	m_modeinfo.status = CONNECTED_RW;
	m_txtimer = new QTimer(this); connect(m_txtimer, SIGNAL(timeout()), this, SLOT(transmit())); m_txtimer->start(19);
	m_rxtimer = new QTimer(this); connect(m_rxtimer, SIGNAL(timeout()), this, SLOT(process_rx_data())); m_rxtimer->start(19);
	m_audio = new AudioEngine(m_audioin, m_audioout);
	m_audio->init(); m_audio->start_playback(); m_audio->start_capture();
	m_modeinfo.sw_vocoder_loaded = true;
	emit update(m_modeinfo);
}

void ELINK::handle_rtp(const QByteArray &b)
{
	hexlog("RECV rtp", b);
	const qint64 now = QDateTime::currentMSecsSinceEpoch();
	m_lastheard = now;
	if (!m_connected) connected();
	const RtpInfo r = parse_rtp(b);
	if (!r.ok) return;
	if (r.payload.startsWith("oNDATA")) {                                                   // text from the station (greeting, name, location)
		emit update_log("EL_TEXT\t" + QString::fromLatin1(r.payload.mid(6)).replace('\r', '\n'));
		return;
	}
	if (r.pt != 3 || r.payload.size() < 33) return;
	const int frames = r.payload.size() / 33;
	if (!m_rxactive) {
		m_rxactive = true; m_laststream = 0;
		m_modeinfo.stream_state = STREAM_NEW; m_modeinfo.streamid = r.ssrc; emit update(m_modeinfo);
	}
	m_lastrx = now;
	int16_t pcm[160];
	for (int f = 0; f < frames; ++f) {
		if (gsm_decode(m_gdec, (gsm_byte *)(r.payload.constData() + f * 33), pcm) != 0) continue;
		for (int i = 0; i < 160; ++i) m_audioq.enqueue(pcm[i]);
	}
	if (now - m_laststream > 300) { m_laststream = now; m_modeinfo.stream_state = STREAMING; emit update(m_modeinfo); }
}

void ELINK::end_rx()
{
	m_rxactive = false;
	m_modeinfo.stream_state = STREAM_END; emit update(m_modeinfo);
	m_modeinfo.stream_state = STREAM_IDLE;
}

void ELINK::process_rx_data()
{
	const qint64 now = QDateTime::currentMSecsSinceEpoch();
	// start with a little head start so the speakers do not starve between packets; a short tail at the end of a transmission is played at once
	if (!m_playing && (m_audioq.size() >= 480 || (!m_audioq.isEmpty() && now - m_lastrx > 120))) m_playing = true;
	if (!m_playing) { if (m_rxactive && now - m_lastrx > 500) end_rx(); return; }
	int16_t pcm[160];
	for (int i = 0; i < 160; ++i) pcm[i] = m_audioq.isEmpty() ? 0 : m_audioq.dequeue();
	m_audio->write(pcm, 160);
	emit update_output_level(m_audio->level());
	if (m_audioq.isEmpty()) m_playing = false;
}

void ELINK::toggle_tx(bool tx) { tx ? start_tx() : stop_tx(); }

void ELINK::start_tx()
{
	if (!m_connected) return;
	int16_t pcm[160];
	while (m_audio->read(pcm)) {}                                                           // drop the sound that piled up before the key was pressed
	m_txq.clear();
	m_tx = true;
	m_modeinfo.stream_state = TRANSMITTING; emit update(m_modeinfo);
}

void ELINK::stop_tx()
{
	if (!m_tx) return;
	m_tx = false;
	if (!m_txq.isEmpty()) { int16_t pcm[640] = {0}; int n = 0; while (!m_txq.isEmpty() && n < 640) pcm[n++] = m_txq.dequeue(); send_audio_packet(pcm); }
	m_txq.clear();
	m_modeinfo.stream_state = STREAM_END; emit update(m_modeinfo);
	m_modeinfo.stream_state = STREAM_IDLE;
}

void ELINK::transmit()
{
	if (!m_connected || !m_audio) return;
	int16_t pcm[160];
	const uint16_t s = m_audio->read(pcm);
	if (m_tx) for (int i = 0; i < s; ++i) m_txq.enqueue(pcm[i]);
	else if (!m_dtmfq.isEmpty()) for (int i = 0; i < 160 && !m_dtmfq.isEmpty(); ++i) m_txq.enqueue(m_dtmfq.dequeue());
	else return;
	while (m_txq.size() >= 640) { int16_t blk[640]; for (int i = 0; i < 640; ++i) blk[i] = m_txq.dequeue(); send_audio_packet(blk); }
}

void ELINK::send_audio_packet(const int16_t *pcm640)
{
	QByteArray payload;
	for (int f = 0; f < 4; ++f) {
		gsm_signal in[160]; gsm_byte out[33];
		for (int i = 0; i < 160; ++i) in[i] = pcm640[f * 160 + i];
		gsm_encode(m_genc, in, out);
		payload.append((const char *)out, 33);
	}
	const QByteArray p = build_rtp(m_seq++, m_rtpts, m_ssrc, payload);
	m_rtpts += 640;
	if (m_rtp) m_rtp->writeDatagram(p, m_address, m_remote_rtp);
}

// EchoLink has no out-of-band DTMF between stations: the keys travel as ordinary tones in the voice stream.
void ELINK::send_dtmf(QByteArray keys)
{
	static const char *rows = "123A456B789C*0#D";
	static const int lo[4] = {697, 770, 852, 941}, hi[4] = {1209, 1336, 1477, 1633};
	for (char k : keys) {
		const char *p = strchr(rows, toupper(k)); if (!p || !*p) continue;
		const int idx = int(p - rows), f1 = lo[idx / 4], f2 = hi[idx % 4];
		for (int n = 0; n < 960; ++n) {                                                     // 120 ms tone
			const double e = std::min(1.0, std::min(n, 960 - n) / 40.0);
			m_dtmfq.enqueue(int16_t(e * 6000 * (std::sin(2 * M_PI * f1 * n / 8000.0) + std::sin(2 * M_PI * f2 * n / 8000.0))));
		}
		for (int n = 0; n < 640; ++n) m_dtmfq.enqueue(0);                                   // 80 ms gap
	}
}

void ELINK::send_disconnect()
{
	if (!m_rtcp) return;
	const QByteArray p = build_rtcp_bye(m_ssrc, "jan");
	m_rtcp->writeDatagram(p, m_address, m_remote_rtcp);
	m_rtcp->writeDatagram(p, m_address, m_remote_rtcp);                                    // twice: a lost goodbye leaves the station busy until it times out
}

void ELINK::deleteLater()
{
	if (m_connected || m_modeinfo.status == CONNECTING) {
		if (m_txtimer) m_txtimer->stop();
		if (m_rxtimer) m_rxtimer->stop();
		if (m_ping_timer) m_ping_timer->stop();
		send_disconnect();
		if (m_audio) { delete m_audio; m_audio = nullptr; }
	}
	QObject::deleteLater();
}
