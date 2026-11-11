#include "session_rules.h"
#include <algorithm>

namespace dc {

static int maxFor(Net n) { return n == Net::DMR ? SessionRules::kMaxDmr : SessionRules::kMaxPerOtherNet; }

int SessionRules::countNet(Net n) const {
    return (int)std::count_if(rx_.begin(), rx_.end(), [n](const Receiver& r) { return r.target.net == n; });
}
Receiver* SessionRules::find(int h) {
    for (auto& r : rx_) if (r.handle == h) return &r;
    return nullptr;
}
void SessionRules::focus(int h) { if (find(h)) focus_ = h; }
void SessionRules::setMuted(int h, bool m) { if (auto* r = find(h)) r->muted = m; }

OpResult SessionRules::listen(const Target& t) {
    OpResult o;
    for (auto& r : rx_) if (r.target == t) {            // already listened: focus, no duplicate
        focus_ = r.handle; o.r = Result::Focused; o.handle = r.handle; return o;
    }
    if (mode_ == ListenMode::Single) {                  // replaces previous receiver on any network
        for (auto& r : rx_) o.removed.push_back(r.handle);
        rx_.clear();
        if (!o.removed.empty()) o.r = Result::Replaced;
    } else if (t.net != Net::DMR) {                     // one receiver per non-DMR network
        for (auto it = rx_.begin(); it != rx_.end();) {
            if (it->target.net == t.net) { o.removed.push_back(it->handle); it = rx_.erase(it); o.r = Result::Replaced; }
            else ++it;
        }
    } else if (countNet(Net::DMR) >= maxFor(Net::DMR)) { // fifth DMR refused, existing four kept
        o.r = Result::Refused; o.reason = "dmr-capacity";
        return o;
    }
    Receiver r; r.handle = nextHandle_++; r.target = t;
    rx_.push_back(r);
    focus_ = r.handle; o.handle = r.handle;
    if (o.r != Result::Replaced) o.r = Result::Ok;
    return o;
}

OpResult SessionRules::stopListening(int h) {
    OpResult o;
    auto it = std::find_if(rx_.begin(), rx_.end(), [h](const Receiver& r) { return r.handle == h; });
    if (it == rx_.end()) { o.r = Result::Refused; o.reason = "unknown"; return o; }
    o.handle = h; o.removed.push_back(h);
    rx_.erase(it);
    if (focus_ == h) focus_ = rx_.empty() ? 0 : rx_.back().handle;
    return o;
}

OpResult SessionRules::setMode(ListenMode m) {
    OpResult o;
    if (ptt_) { o.r = Result::Refused; o.reason = "tx-active"; return o; }   // not changeable during TX
    if (m == ListenMode::Single && mode_ == ListenMode::Multiple && rx_.size() > 1) {
        int keep = find(focus_) ? focus_ : rx_.front().handle;                 // keep selected/foreground receiver
        for (auto it = rx_.begin(); it != rx_.end();) {
            if (it->handle != keep) { o.removed.push_back(it->handle); it = rx_.erase(it); } else ++it;
        }
        focus_ = keep;
    }
    mode_ = m;
    return o;
}

void SessionRules::stopAll() { rx_.clear(); focus_ = 0; endPtt(); disconnectTx(); }

float SessionRules::effectiveVolume(const Receiver& r) const {
    int n = (int)r.target.net;
    if (r.muted || r.blocked || netMuted_[n]) return 0.f;
    float v = netVol_[n] * r.volume;
    if (ducking_ && ptt_ && !(txTarget_ == r.target)) v *= 0.25f;   // reduce competing audio during TX
    if (ptt_ && txTarget_ == r.target) v = 0.f;                     // suppress matching RX while transmitting
    return v;
}

// ---- transmit ------------------------------------------------------------
OpResult SessionRules::connectTx(const Target& t) {
    OpResult o;
    if (ptt_) { o.r = Result::Refused; o.reason = "tx-active"; return o; }  // destination fixed during TX
    txTarget_ = t; txConn_ = true;
    return o;
}
void SessionRules::disconnectTx() { endPtt(); txConn_ = false; }
bool SessionRules::pttAvailable() const { return txConn_ && hasSelected_ && selected_ == txTarget_; }

OpResult SessionRules::pttPress(bool latch) {
    OpResult o;
    if (!pttAvailable()) { o.r = Result::Refused; o.reason = "not-tx-ready"; return o; }
    if (ptt_) {                                       // pressing Latch again acts as Stop TX
        if (latched_ && latch) endPtt();
        return o;
    }
    ptt_ = true; latched_ = latch; remaining_ = limit_; msAcc_ = 0;
    return o;
}
void SessionRules::pttRelease() { endPtt(); }   // release hold, or Stop TX when latched
void SessionRules::endPtt() { ptt_ = false; latched_ = false; remaining_ = 0; msAcc_ = 0; }
bool SessionRules::setLimit(int s) {
    if (ptt_ || !(s == 60 || s == 120 || s == 180)) return false;
    limit_ = s; return true;
}
void SessionRules::tick(int ms) {
    if (!ptt_) return;
    msAcc_ += ms;
    while (msAcc_ >= 1000 && remaining_ > 0) { msAcc_ -= 1000; --remaining_; }
    if (remaining_ <= 0) endPtt();                    // timeout ends transmission
}
void SessionRules::focusLost() { if (ptt_) endPtt(); }

// ---- presentation --------------------------------------------------------
CardState SessionRules::cardState(const Receiver& r) const {
    bool actual = r.reportsTraffic && !r.muted && !r.blocked && !netMuted_[(int)r.target.net];
    if (mode_ == ListenMode::Multiple && actual) return CardState::Amber;    // whole-card amber only in multiple mode
    return CardState::Pink;                                                  // listening enabled/focused
}

// ---- validators ----------------------------------------------------------
bool SessionRules::validDmrTg(const std::string& s) {
    if (s.empty() || s.size() > 8) return false;
    uint64_t v = 0;
    for (char c : s) { if (c < '0' || c > '9') return false; v = v * 10 + (c - '0'); }
    return v >= 1 && v <= 16777215;
}
bool SessionRules::validDtmf(const std::string& s) {
    if (s.empty() || s.size() > 32) return false;
    for (char c : s) if (!((c >= '0' && c <= '9') || (c >= 'A' && c <= 'D') || c == '*' || c == '#')) return false;
    return true;
}
bool SessionRules::validFavoriteName(const std::string& s) {
    size_t cp = 0;
    for (unsigned char c : s) if ((c & 0xC0) != 0x80) ++cp;       // count UTF-8 code points
    return cp >= 1 && cp <= 80;
}

} // namespace dc
