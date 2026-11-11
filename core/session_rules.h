// DigiConnect — session rules engine (original code, no Qt dependency).
// Implements the operating rules: separate Listen / Connect(TX), single vs
// multiple listening with per-network capacity, PTT hold/latch with fixed
// destination and time limit, activity-colour state, input validators.
// Time is injected (tick(ms)) so the logic is fully unit-testable.
#pragma once
#include <string>
#include <vector>
#include <cstdint>

namespace dc {

enum class Net { DMR, DStar, EchoLink, C4FM };
enum class CardState { Neutral, Green, Pink, Amber };   // selection outline is separate
enum class ListenMode { Single, Multiple };
enum class Result { Ok, Focused, Replaced, Refused };

struct Target {
    Net net = Net::DMR;
    std::string id;      // TG number / reflector+module / EchoLink callsign / YSF id
    std::string name;
    bool operator==(const Target& o) const { return net == o.net && id == o.id; }
};

struct Receiver {
    int handle = 0;
    Target target;
    bool muted = false;
    float volume = 1.0f;      // per-receiver (DMR strip)
    bool reportsTraffic = false;   // actual received traffic (not just public activity)
    bool blocked = false;
};

struct OpResult {
    Result r = Result::Ok;
    int handle = 0;                    // receiver affected / created
    std::vector<int> removed;          // receivers closed by this operation
    std::string reason;                // set when refused
};

class SessionRules {
public:
    static constexpr int kMaxDmr = 4;
    static constexpr int kMaxPerOtherNet = 1;
    static constexpr int kWarnSeconds = 15;

    // ---- listening -------------------------------------------------------
    ListenMode mode() const { return mode_; }
    OpResult setMode(ListenMode m);                 // refused during TX
    OpResult listen(const Target& t);               // never touches TX
    OpResult stopListening(int handle);
    void stopAll();                                 // ends listening, TX and PTT
    const std::vector<Receiver>& receivers() const { return rx_; }
    Receiver* find(int handle);
    int focused() const { return focus_; }
    void focus(int handle);
    void setMuted(int handle, bool m);
    void setNetworkMuted(Net n, bool m) { netMuted_[(int)n] = m; }
    void setNetworkVolume(Net n, float v) { netVol_[(int)n] = v < 0 ? 0 : (v > 1 ? 1 : v); }
    float effectiveVolume(const Receiver& r) const;  // net x receiver x mute x ducking

    // ---- selection (never starts anything by itself) ---------------------
    void select(const Target& t) { selected_ = t; hasSelected_ = true; }
    bool hasSelection() const { return hasSelected_; }
    const Target& selection() const { return selected_; }

    // ---- transmit path ---------------------------------------------------
    OpResult connectTx(const Target& t);             // one TX session at a time
    void disconnectTx();                             // ends TX; reception unaffected
    bool txConnected() const { return txConn_; }
    const Target& txTarget() const { return txTarget_; }
    bool pttAvailable() const;                       // selected == connected TX target
    bool pttActive() const { return ptt_; }
    bool pttLatched() const { return latched_; }
    OpResult pttPress(bool latch);                   // hold or latch
    void pttRelease();                               // release hold / Stop TX
    bool setLimit(int seconds);                      // 60/120/180, refused during TX
    int limit() const { return limit_; }
    int remainingSeconds() const { return remaining_; }
    bool countdownRed() const { return ptt_ && remaining_ <= kWarnSeconds; }
    void tick(int ms);                               // advance countdown
    void focusLost();                                // window focus lost → stop TX
    void setDucking(bool d) { ducking_ = d; }
    bool ducking() const { return ducking_; }

    // ---- presentation ----------------------------------------------------
    CardState cardState(const Receiver& r) const;
    bool isSelected(const Target& t) const { return hasSelected_ && selected_ == t; }

    // ---- validators ------------------------------------------------------
    static bool validDmrTg(const std::string& s);        // 1..16777215
    static bool validDtmf(const std::string& s);         // 1..32 of 0-9 A-D * #
    static bool validFavoriteName(const std::string& s); // 1..80 characters (UTF-8 code points)
    static bool validTextSize(int px) { return px >= 11 && px <= 20; }

private:
    int countNet(Net n) const;
    void endPtt();
    std::vector<Receiver> rx_;
    int nextHandle_ = 1, focus_ = 0;
    ListenMode mode_ = ListenMode::Single;
    float netVol_[4] = {1, 1, 1, 1};
    bool netMuted_[4] = {false, false, false, false};
    Target selected_; bool hasSelected_ = false;
    bool txConn_ = false; Target txTarget_;
    bool ptt_ = false, latched_ = false; int limit_ = 120, remaining_ = 0, msAcc_ = 0;
    bool ducking_ = true;
};

} // namespace dc
