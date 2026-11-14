/*
	Copyright (C) 2019-2021 Doug McLain

	This program is free software: you can redistribute it and/or modify
	it under the terms of the GNU General Public License as published by
	the Free Software Foundation, either version 3 of the License, or
	(at your option) any later version.

	This program is distributed in the hope that it will be useful,
	but WITHOUT ANY WARRANTY; without even the implied warranty of
	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
	GNU General Public License for more details.

	You should have received a copy of the GNU General Public License
	along with this program.  If not, see <https://www.gnu.org/licenses/>.
*/

#ifndef DMR_H
#define DMR_H

#include "mode.h"
#include "DMRDefines.h"
#include "cbptc19696.h"

class DMR : public Mode
{
	Q_OBJECT
public:
	DMR();
	~DMR();
	void set_dmr_rewind(bool on, quint16 port) override;
	void set_dmr_params(uint8_t essid, QString password, QString lat, QString lon, QString location, QString desc, QString freq, QString url, QString swid, QString pkid, QString options);
	uint8_t * get_eot();
private slots:
	void process_udp();
	void process_rx_data();
	void process_modem_data(QByteArray);
	void get_ambe();
	void send_ping();
	void send_disconnect();
	void transmit();
	void hostname_lookup(QHostInfo i);
	void dmr_tgid_changed(int id);
	void rewind_tick();
    void dmrpc_state_changed(int p){m_flco = p ? FLCO_USER_USER : FLCO_GROUP; m_txflco = m_flco; }
    void cc_changed(int cc) {m_txcc = cc;}
	void slot_changed(int s) {m_txslot = s + 1; }
	void send_frame();
	void mmdvm_direct_connect();
private:
	uint32_t m_essid;
	QString m_password;
	QString m_lat;
	QString m_lon;
	QString m_location;
	QString m_desc;
	QString m_freq;
	QString m_url;
	QString m_swid;
	QString m_pkid;
	uint32_t m_txsrcid;
	uint32_t m_txdstid;
	uint32_t m_txstreamid;
	uint8_t m_txslot;
	uint8_t m_txcc;
	uint8_t packet_size;
	uint8_t m_ambe[27];
	uint32_t m_defsrcid;
	uint8_t m_dmrFrame[55];
	uint8_t m_dataType;
	uint32_t m_dmrcnt;
	FLCO m_flco;
	FLCO m_txflco;
	CBPTC19696 m_bptc;
	bool m_raw[128U];
	bool m_data[72U];
	QString m_options;

	void byteToBitsBE(uint8_t byte, bool* bits);
	void bitsToByteBE(const bool* bits, uint8_t& byte);
	void build_frame();
	void encode_header(uint8_t);
	void encode_data();
	void encode16114(bool* d);
	void encode_qr1676(uint8_t* data);
	void get_slot_data(uint8_t* data);
	void lc_get_data(uint8_t*);
	void lc_get_data(bool* bits);
	void encode_embedded_data();
	uint8_t get_embedded_data(uint8_t* data, uint8_t n);
	void get_emb_data(uint8_t* data, uint8_t lcss);
	void full_lc_encode(uint8_t* data, uint8_t type);
	void addDMRDataSync(uint8_t* data, bool duplex);
	void addDMRAudioSync(uint8_t* data, bool duplex);
	void setup_connection();
	void handle_dmrd(const QByteArray &buf);
	void send_net(const QByteArray &dmrd);

	// ---- BrandMeister "Rewind" (Open DMR Terminal Protocol): BrandMeister refuses Homebrew from software-only clients -------------------
	bool m_rewind = false;
	quint16 m_rw_port = 54006;
	QList<quint16> m_rw_ports;
	int m_rw_try = 0, m_rw_tick = 0;
	uint32_t m_rw_seq = 0, m_rw_rtseq = 0, m_rw_subtg = 0;
	qint64 m_rw_auth_ms = 0, m_rw_last_ms = 0;
	QTimer *m_rw_timer = nullptr;
	bool m_rw_rxactive = false;
	uint32_t m_rw_rxstream = 0, m_rw_rxsrc = 0, m_rw_rxdst = 0, m_rw_rxcnt = 0;
	bool m_rw_rxprivate = false;
	void rewind_send_raw(uint16_t type, uint16_t flags, uint32_t number, const QByteArray &data);
	void rewind_send(uint16_t type, const QByteArray &data = QByteArray());
	void rewind_keepalive();
	void rewind_subscribe(uint32_t tg, bool cancel);
	void rewind_attempt();
	void rewind_fail(const QString &code, const QString &why);
	void process_rewind(const QByteArray &buf);
	void rewind_send_dmrd(const QByteArray &dmrd);
	void rewind_lc(uint8_t *lc12, bool terminator);
	void rewind_rx_dmrd(bool data, uint8_t dt, const uint8_t *ambe27);
};

#endif // DMR_H
