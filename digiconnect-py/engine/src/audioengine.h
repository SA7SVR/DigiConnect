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

#ifndef AUDIOENGINE_H
#define AUDIOENGINE_H

#include <QObject>
#if QT_VERSION < QT_VERSION_CHECK(6, 3, 0)
#include <QAudio>
#include <QAudioFormat>
#include <QAudioInput>
#else
#include <QAudioDevice>
#include <QAudioSink>
#include <QAudioSource>
#include <QMediaDevices>
#endif
#include <QAudioOutput>
#include <QQueue>

#define AUDIO_OUT 1
#define AUDIO_IN  0

class AudioEngine : public QObject
{
	Q_OBJECT
public:
	//explicit AudioEngine(QObject *parent = nullptr);
	AudioEngine(QString in, QString out);
	~AudioEngine();
	static QStringList discover_audio_devices(uint8_t d);
	void init();
	void start_capture();
	void stop_capture();
	void start_playback();
	void stop_playback();
	void write(int16_t *, size_t, float fade_from = 1.0f, float fade_to = 1.0f);
	bool playback_drained();
	void set_output_buffer_size(uint32_t b) { if(m_out != nullptr) m_out->setBufferSize(b); }
	void set_input_buffer_size(uint32_t) { /* kept for compatibility: the capture buffer is sized from the device format in init() */ }
	// Playback level (0..1) is applied to the samples here, not through the audio backend: the backend's own volume was ignored on some systems
	// (and lost again after the stream was restarted), so the slider and mute did nothing.
	void set_output_volume(qreal v){ m_outvol = (float)(v < 0 ? 0 : (v > 1 ? 1 : v)); if(m_out != nullptr) m_out->setVolume(1.0); }
	// Microphone level: 0..1 goes to the device (session) volume; above 1 is applied as software gain (clipped), so a quiet microphone can be raised.
	void set_input_volume(qreal v){ if(v < 0) v = 0; m_ingain = (float)(v > 1.0 ? v : 1.0); if(m_in != nullptr) m_in->setVolume(v > 1.0 ? 1.0 : v); }
	void set_agc(bool agc) { m_agc = agc; }
	bool has_samples(int n) const { return m_audioinq.size() >= n; }
	bool frame_available() { return (m_audioinq.size() >= 320) ? true : false; }
	uint16_t read(int16_t *, int);
	uint16_t read(int16_t *);
	uint16_t level() { return m_maxlevel; }
	// diagnostics: bytes the sound card did not accept (lost playback sound) and microphone samples dropped because nobody read them in time
	uint32_t out_dropped_bytes() const { return m_out_dropped; }
	uint32_t in_dropped_samples() const { return m_in_dropped; }
	void reset_stats() { m_out_dropped = 0; m_in_dropped = 0; }
signals:

private slots:
	void input_data_received();   // standard Qt pull-model capture (replaces non-standard callback API)

private:
	QString m_outputdevice;
	QString m_inputdevice;
#if QT_VERSION < QT_VERSION_CHECK(6, 3, 0)
	QAudioOutput *m_out;
	QAudioInput *m_in;
#else
	QAudioSink *m_out;
	QAudioSource *m_in;
#endif
	QIODevice *m_outdev = nullptr;
	uint32_t m_out_dropped = 0, m_in_dropped = 0;
	QIODevice *m_indev = nullptr;
	QQueue<int16_t> m_audioinq;
	uint16_t m_maxlevel;
	bool m_agc;
	float m_srm; // capture sample rate / 8000 (1 = device runs at 8 kHz; otherwise the microphone is resampled here)
	float m_outvol = 1.0f;                                  // playback level set by the user (slider / mute / ducking)
	float m_ingain = 1.0f;                                  // software gain applied to the microphone
	int m_inchan = 1;                                       // channels delivered by the capture device
	QAudioFormat::SampleFormat m_infmt = QAudioFormat::Int16; // sample format delivered by the capture device
	float m_rs_acc = 0, m_rs_pos = 0; int m_rs_n = 0;       // resampler state (box average)
	QString m_inname;
	qint64 m_inbytes = 0;                                   // bytes received from the microphone (diagnostics)

	float m_audio_out_temp_buf[320];   //!< output of decoder
	float *m_audio_out_temp_buf_p;

	//float m_audio_out_float_buf[1120]; //!< output of upsampler - 1 frame of 160 samples upampled up to 7 times
	//float *m_audio_out_float_buf_p;

	float m_aout_max_buf[200];
	float *m_aout_max_buf_p;
	int m_aout_max_buf_idx;

	//short m_audio_out_buf[2*48000];    //!< final result - 1s of L+R S16LE samples
	//short *m_audio_out_buf_p;
	//int   m_audio_out_nb_samples;
	//int   m_audio_out_buf_size;
	//int   m_audio_out_idx;
	//int   m_audio_out_idx2;

	float m_aout_gain;
	float m_volume;

private slots:
	void process_audio(int16_t *pcm, size_t s);
	void handleStateChanged(QAudio::State newState);
};

#endif // AUDIOENGINE_H
