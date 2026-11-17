// Writes 16-bit mono PCM to a WAV file. A placeholder header is written first; close() fills in the real sizes.
#ifndef WAVWRITER_H
#define WAVWRITER_H

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>

class WavWriter {
public:
    WavWriter() = default;
    ~WavWriter() { close(); }
    WavWriter(const WavWriter &) = delete;
    WavWriter &operator=(const WavWriter &) = delete;

    bool open(const std::string &path, uint32_t rate) {
        close();
        f_ = std::fopen(path.c_str(), "wb");
        if (!f_) return false;
        rate_ = rate; samples_ = 0;
        put_header(0);
        return true;
    }
    void write(const int16_t *pcm, size_t n) {
        if (!f_ || n == 0) return;
        std::fwrite(pcm, sizeof(int16_t), n, f_);
        samples_ += n;
    }
    void close() {
        if (!f_) return;
        std::fseek(f_, 0, SEEK_SET);
        put_header(samples_);
        std::fclose(f_);
        f_ = nullptr;
    }
    bool is_open() const { return f_ != nullptr; }
    uint64_t samples() const { return samples_; }

private:
    void put_header(uint64_t n) {
        const uint32_t data = (uint32_t)(n * 2), riff = 36 + data, byte_rate = rate_ * 2;
        uint8_t h[44];
        std::memcpy(h, "RIFF", 4); le32(h + 4, riff); std::memcpy(h + 8, "WAVE", 4);
        std::memcpy(h + 12, "fmt ", 4); le32(h + 16, 16); le16(h + 20, 1); le16(h + 22, 1);
        le32(h + 24, rate_); le32(h + 28, byte_rate); le16(h + 32, 2); le16(h + 34, 16);
        std::memcpy(h + 36, "data", 4); le32(h + 40, data);
        std::fwrite(h, 1, 44, f_);
    }
    static void le16(uint8_t *p, uint16_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }
    static void le32(uint8_t *p, uint32_t v) { le16(p, (uint16_t)v); le16(p + 2, (uint16_t)(v >> 16)); }

    std::FILE *f_ = nullptr;
    uint32_t rate_ = 8000;
    uint64_t samples_ = 0;
};

#endif // WAVWRITER_H
