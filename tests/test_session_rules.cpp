#include "../core/session_rules.h"
#include <cstdio>
#include <cstdlib>
using namespace dc;
static int fails = 0;
#define CHECK(c) do { if (!(c)) { std::printf("FAIL line %d: %s\n", __LINE__, #c); ++fails; } } while (0)
static Target T(Net n, const char* id) { Target t; t.net = n; t.id = id; t.name = id; return t; }

int main() {
    { // single mode: new receiver replaces previous across networks
        SessionRules s;
        auto a = s.listen(T(Net::DMR, "91")); CHECK(a.r == Result::Ok);
        auto b = s.listen(T(Net::DStar, "REF001C")); CHECK(b.r == Result::Replaced && b.removed.size() == 1);
        CHECK(s.receivers().size() == 1);
    }
    { // multiple: 4 DMR + 1 each other; fifth DMR refused and the four preserved
        SessionRules s; s.setMode(ListenMode::Multiple);
        for (const char* tg : {"91", "2", "240", "2401"}) CHECK(s.listen(T(Net::DMR, tg)).r == Result::Ok);
        auto f = s.listen(T(Net::DMR, "9")); CHECK(f.r == Result::Refused && s.receivers().size() == 4);
        CHECK(s.listen(T(Net::DStar, "REF001C")).r == Result::Ok);
        CHECK(s.listen(T(Net::C4FM, "00001")).r == Result::Ok);
        CHECK(s.listen(T(Net::EchoLink, "SM7XYZ")).r == Result::Ok);
        CHECK(s.receivers().size() == 7);
        auto r = s.listen(T(Net::DStar, "XRF012A")); CHECK(r.r == Result::Replaced && s.receivers().size() == 7);
        auto d = s.listen(T(Net::DMR, "91")); CHECK(d.r == Result::Focused && s.receivers().size() == 7);  // no duplicate
    }
    { // back to single keeps the focused receiver, stops others
        SessionRules s; s.setMode(ListenMode::Multiple);
        s.listen(T(Net::DMR, "91")); int h = s.listen(T(Net::DMR, "2")).handle; s.listen(T(Net::DStar, "REF001C"));
        s.focus(h);
        auto o = s.setMode(ListenMode::Single);
        CHECK(s.receivers().size() == 1 && s.receivers()[0].handle == h && o.removed.size() == 2);
    }
    { // listen and TX are independent; PTT only for selected+connected target
        SessionRules s; Target tg = T(Net::DMR, "91");
        s.select(tg); s.listen(tg);
        CHECK(!s.pttAvailable() && s.pttPress(false).r == Result::Refused);   // listening is not TX
        s.connectTx(tg); CHECK(s.pttAvailable());
        s.select(T(Net::DMR, "2")); CHECK(!s.pttAvailable());                 // other selection: no PTT
        s.select(tg);
        CHECK(s.pttPress(false).r == Result::Ok && s.pttActive() && !s.pttLatched());
        s.pttRelease(); CHECK(!s.pttActive() && s.txConnected() && s.receivers().size() == 1);
    }
    { // latch, limit, red last 15 s, timeout ends TX
        SessionRules s; Target tg = T(Net::DMR, "91"); s.select(tg); s.connectTx(tg);
        CHECK(s.setLimit(60) && !s.setLimit(90));
        s.pttPress(true); CHECK(s.pttLatched() && s.remainingSeconds() == 60);
        CHECK(!s.setLimit(180));                                              // limit fixed during TX
        s.tick(44000); CHECK(s.remainingSeconds() == 16 && !s.countdownRed());
        s.tick(1000);  CHECK(s.remainingSeconds() == 15 && s.countdownRed());
        s.tick(15000); CHECK(!s.pttActive());                                 // zero ends TX
    }
    { // destination fixed during TX; mode locked; focus loss and stopAll stop TX
        SessionRules s; Target tg = T(Net::DMR, "91"); s.select(tg); s.connectTx(tg); s.pttPress(true);
        CHECK(s.connectTx(T(Net::DMR, "2")).r == Result::Refused && s.txTarget() == tg);
        CHECK(s.setMode(ListenMode::Multiple).r == Result::Refused);
        s.focusLost(); CHECK(!s.pttActive());
        s.pttPress(false); s.stopAll(); CHECK(!s.pttActive() && !s.txConnected() && s.receivers().empty());
    }
    { // latch pressed again = Stop TX
        SessionRules s; Target tg = T(Net::DMR, "91"); s.select(tg); s.connectTx(tg);
        s.pttPress(true); s.pttPress(true); CHECK(!s.pttActive());
    }
    { // ducking and self-monitor suppression
        SessionRules s; s.setMode(ListenMode::Multiple);
        Target a = T(Net::DMR, "91"), b = T(Net::DMR, "2");
        int ha = s.listen(a).handle, hb = s.listen(b).handle; s.select(a); s.connectTx(a);
        CHECK(s.effectiveVolume(*s.find(hb)) == 1.f);
        s.pttPress(false);
        CHECK(s.effectiveVolume(*s.find(ha)) == 0.f);                          // matching RX suppressed
        CHECK(s.effectiveVolume(*s.find(hb)) < 1.f);                           // others ducked
        s.setDucking(false); CHECK(s.effectiveVolume(*s.find(hb)) == 1.f);
        s.setNetworkMuted(Net::DMR, true); CHECK(s.effectiveVolume(*s.find(hb)) == 0.f);
    }
    { // card colours: amber only in multiple mode and only for real, unmuted traffic
        SessionRules s; Target a = T(Net::DMR, "91"); int h = s.listen(a).handle;
        s.find(h)->reportsTraffic = true; CHECK(s.cardState(*s.find(h)) == CardState::Pink);
        s.setMode(ListenMode::Multiple); CHECK(s.cardState(*s.find(h)) == CardState::Amber);
        s.setMuted(h, true); CHECK(s.cardState(*s.find(h)) == CardState::Pink);
    }
    { // validators
        CHECK(SessionRules::validDmrTg("91") && SessionRules::validDmrTg("16777215"));
        CHECK(!SessionRules::validDmrTg("0") && !SessionRules::validDmrTg("16777216") && !SessionRules::validDmrTg("-5") && !SessionRules::validDmrTg("9a"));
        CHECK(SessionRules::validDtmf("*123#AD") && !SessionRules::validDtmf("") && !SessionRules::validDtmf("12E") && !SessionRules::validDtmf(std::string(33, '1')));
        CHECK(SessionRules::validFavoriteName("Ελλάδα") && !SessionRules::validFavoriteName("") && !SessionRules::validFavoriteName(std::string(81, 'x')) && SessionRules::validFavoriteName(std::string(80, 'x')));
        CHECK(SessionRules::validTextSize(11) && SessionRules::validTextSize(20) && !SessionRules::validTextSize(21));
    }
    std::printf(fails ? "%d FAILED\n" : "ALL PASSED\n", fails);
    return fails ? 1 : 0;
}
