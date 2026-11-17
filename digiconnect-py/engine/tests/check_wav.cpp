// Checks the recording writer (engine/src/wavwriter.h). Build: g++ -std=c++17 -I engine/src engine/tests/check_wav.cpp -o wav_test && ./wav_test
#include "wavwriter.h"
#include <cstdio>
#include <vector>
#include <cstring>
#include <cstdint>

static uint32_t rd32(const unsigned char *p) { return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24); }

int main() {
    const char *path = "check_rec_test.wav";
    { WavWriter w; if (!w.open(path, 8000)) { std::puts("FAIL cannot open"); return 1; }
      std::vector<int16_t> s(800); for (size_t i = 0; i < s.size(); ++i) s[i] = (int16_t)(i * 10);
      w.write(s.data(), s.size()); w.write(s.data(), 160); w.close(); }
    FILE *f = std::fopen(path, "rb"); unsigned char h[44]; size_t n = std::fread(h, 1, 44, f); std::fseek(f, 0, SEEK_END); long size = std::ftell(f); std::fclose(f);
    int fails = 0;
    auto check = [&](bool ok, const char *what) { std::printf("%s  %s\n", ok ? "ok  " : "FAIL", what); if (!ok) ++fails; };
    check(n == 44 && std::memcmp(h, "RIFF", 4) == 0 && std::memcmp(h + 8, "WAVE", 4) == 0, "RIFF/WAVE header");
    check(rd32(h + 24) == 8000, "sample rate 8000");
    check(h[22] == 1 && h[34] == 16, "mono, 16 bit");
    check(rd32(h + 40) == 960 * 2, "data size matches 960 samples");
    check(rd32(h + 4) == (uint32_t)(size - 8), "RIFF size matches the file");
    std::remove(path);
    std::printf("%s\n", fails ? "FAILED" : "ALL OK");
    return fails;
}
