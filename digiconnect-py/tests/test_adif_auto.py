"""Every saved contact is appended to the chosen ADIF file (one header only), and the file reads back with the same callsigns."""
import pathlib, tempfile
from app.store import Store


def test_saved_contacts_go_to_adif_file():
    d = pathlib.Path(tempfile.mkdtemp()); st = Store(d); st.settings["callsign"] = "SA7SVR"
    out = d / "contacts.adi"; st.settings["adif_auto_path"] = str(out)
    st.add_qso(dict(callsign="SV1OZ", start_utc="2026-11-17T21:30:00", system="DMR", band="70cm", freq="438.800", name="Dimitris", country="Greece"))
    st.add_qso(dict(callsign="SV1BRU", start_utc="2026-11-17T21:40:00", system="DMR", band="70cm", freq="438.800"))
    text = out.read_text(encoding="utf-8")
    assert text.count("<EOH>") == 1, text[:200]
    recs = st.parse_adif(text)
    assert [r["CALL"] for r in recs] == ["SV1OZ", "SV1BRU"], recs


def test_no_file_when_not_chosen():
    d = pathlib.Path(tempfile.mkdtemp()); st = Store(d); st.settings["callsign"] = "SA7SVR"
    st.add_qso(dict(callsign="SV1OZ", start_utc="2026-11-17T21:30:00", system="DMR"))
    assert not list(d.glob("*.adi"))


def test_contact_sent_over_udp_to_the_logbook_port():
    import socket
    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); srv.bind(("127.0.0.1", 0)); srv.settimeout(3)
    port = srv.getsockname()[1]
    d = pathlib.Path(tempfile.mkdtemp()); st = Store(d); st.settings["callsign"] = "SA7SVR"
    st.settings["logbook_udp_host"] = "127.0.0.1"; st.settings["logbook_udp_port"] = port
    st.add_qso(dict(callsign="SV1OZ", start_utc="2026-11-17T21:30:00", system="DMR", band="70cm"))
    data, _ = srv.recvfrom(4096)
    text = data.decode("utf-8")
    assert "<CALL:5>SV1OZ" in text and "<EOR>" in text and "<EOH>" not in text, text
    srv.close()


def test_no_udp_when_port_not_set():
    d = pathlib.Path(tempfile.mkdtemp()); st = Store(d); st.settings["callsign"] = "SA7SVR"
    assert st.send_qso_udp(dict(callsign="SV1OZ")) is False
