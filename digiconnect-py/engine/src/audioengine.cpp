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

#include "audioengine.h"
#include <QDebug>
#include <QTimer>
#include <cmath>

#if defined (Q_OS_MACOS) || defined(Q_OS_IOS)
#define MACHAK 1
#else
#define MACHAK 0
#endif

#if defined(Q_OS_IOS)
void configureiOSAudioSession();
#endif

AudioEngine::AudioEngine(QString in, QString out) :
	m_outputdevice(out),
	m_inputdevice(in),
	m_out(nullptr),
	m_in(nullptr),
	m_srm(1)
{
	m_audio_out_temp_buf_p = m_audio_out_temp_buf;
	memset(m_aout_max_buf, 0, sizeof(float) * 200);
	m_aout_max_buf_p = m_aout_max_buf;
	m_aout_max_buf_idx = 0;
	m_aout_gain = 100;
	m_volume = 1.0f;
}

AudioEngine::~AudioEngine()
{
}

QStringList AudioEngine::discover_audio_devices(uint8_t d)
{
	QStringList list;
	QList<QAudioDevice> devices;

	if(d){
		devices = QMediaDevices::audioOutputs();
	}
	else{
		devices = QMediaDevices::audioInputs();
	}

	for (QList<QAudioDevice>::ConstIterator it = devices.constBegin(); it != devices.constEnd(); ++it ) {
		//fprintf(stderr, "Playback device name = %s\n", (*it).deviceName().toStdString().c_str());fflush(stderr);
		list.append((*it).description());
	}

	return list;
}

void AudioEngine::init()
{
	QAudioFormat format;
    format.setSampleRate(8000);
	format.setChannelCount(1);
	format.setSampleFormat(QAudioFormat::Int16);

	m_agc = true;

	QList<QAudioDevice> devices = QMediaDevices::audioOutputs();
	if(devices.size() == 0){
        qDebug() << "No audio playback hardware found";
	}
	else{
		QAudioDevice device(QMediaDevices::defaultAudioOutput());
		for (QList<QAudioDevice>::ConstIterator it = devices.constBegin(); it != devices.constEnd(); ++it ) {

            //qDebug() << "Playback device name = " << (*it).description();
            //qDebug() << (*it).supportedSampleFormats();
            //qDebug() << (*it).preferredFormat();
            //qDebug() << (*it).minimumSampleRate();
            //qDebug() << (*it).maximumSampleRate();


			if((*it).description() == m_outputdevice){
				device = *it;
			}
		}
		if (!device.isFormatSupported(format)) {
            qWarning() << "Current audio format not supported by playback device";
        }

        try{
            m_out = new QAudioSink(device, format, this);
            m_out->setBufferSize(1280);
            //connect(m_out, SIGNAL(stateChanged(QAudio::State)), this, SLOT(handleStateChanged(QAudio::State)));
        }
        catch (const std::exception& e) {
            qDebug() << "Exception in constructor:" << e.what();
        }

        qDebug() << "Playback device: " << device.description() << "SR: " << format.sampleRate();
	}

	devices = QMediaDevices::audioInputs();

    if(devices.size() == 0){
        qDebug() <<  "No audio capture hardware found";
	}
	else{
		QAudioDevice device(QMediaDevices::defaultAudioInput());
		for (QList<QAudioDevice>::ConstIterator it = devices.constBegin(); it != devices.constEnd(); ++it ) {
            //qDebug() << "Capture device name = " << (*it).description();
            //qDebug() << (*it).supportedSampleFormats();
            //qDebug() << (*it).preferredFormat();
            //qDebug() << (*it).minimumSampleRate();
            //qDebug() << (*it).maximumSampleRate();

			if((*it).description() == m_inputdevice){
				device = *it;
			}
		}
		// Choose a format the microphone really delivers. 8 kHz mono 16-bit is what the vocoders want, but many Windows
		// devices only offer their own mix format: then capture in that format and convert here (never stay silent).
		QAudioFormat use = format;
		if(MACHAK || !device.isFormatSupported(format)){
			QAudioFormat pf = device.preferredFormat();
			QAudioFormat f2 = format; f2.setSampleRate(pf.sampleRate());
			if(!MACHAK && device.isFormatSupported(f2)){ use = f2; }
			else { use = pf; }
		}
		m_srm = (float)use.sampleRate() / 8000.0f;
		m_inchan = use.channelCount() > 0 ? use.channelCount() : 1;
		m_infmt = use.sampleFormat();
		m_rs_acc = 0; m_rs_pos = 0; m_rs_n = 0;
		int sr = use.sampleRate();
		m_in = new QAudioSource(device, use, this);
		{ int bps = (use.sampleFormat() == QAudioFormat::UInt8) ? 1 : ((use.sampleFormat() == QAudioFormat::Int16) ? 2 : 4); m_in->setBufferSize(sr * m_inchan * bps / 10); }   // ~100 ms
		m_inname = device.description();
        qDebug() << "Capture device: " <<  device.description() << " SR: " << sr << " ch: " << m_inchan << " fmt: " << (int)m_infmt << " resample factor: " << m_srm;

	}
}

void AudioEngine::start_capture()
{
#if defined(Q_OS_IOS)
    configureiOSAudioSession();
#endif
    // Standard Qt pull-model capture: start() returns a QIODevice, read samples on readyRead.
    if(m_in == nullptr){
        qWarning() << "DCWARN: no microphone found - nothing can be transmitted";
        return;
    }
    m_inbytes = 0; m_rs_acc = 0; m_rs_pos = 0; m_rs_n = 0;
    if(m_indev != nullptr){ disconnect(m_indev, nullptr, this, nullptr); m_indev = nullptr; }
    m_indev = m_in->start();
    if(m_indev != nullptr){
        connect(m_indev, &QIODevice::readyRead, this, &AudioEngine::input_data_received);
    }
    else{
        qWarning() << "DCWARN: the microphone could not be opened (" << m_inname << ") error" << (int)m_in->error();
    }
    // If no sound arrives, say so (instead of staying silent for the whole transmission).
    QTimer::singleShot(1500, this, [this]{
        if(m_in != nullptr && m_in->state() != QAudio::StoppedState && m_inbytes == 0){
            qWarning() << "DCWARN: the microphone" << m_inname << "delivers no sound (state" << (int)m_in->state() << "error" << (int)m_in->error()
                       << ") - choose another microphone, or allow microphone access in Windows Settings > Privacy > Microphone";
        }
    });
}

void AudioEngine::input_data_received()
{
    if(m_indev == nullptr) return;
    const QByteArray data = m_indev->readAll();
    if(data.isEmpty()) return;
    m_inbytes += data.size();
    const char *p = data.constData();
    int bps = 2;
    switch(m_infmt){ case QAudioFormat::UInt8: bps = 1; break; case QAudioFormat::Int16: bps = 2; break; case QAudioFormat::Int32: case QAudioFormat::Float: bps = 4; break; default: bps = 2; }
    const int ch = m_inchan > 0 ? m_inchan : 1;
    const int frames = static_cast<int>(data.size() / (bps * ch));
    for(int f = 0; f < frames; ++f){
        float acc = 0;
        for(int c = 0; c < ch; ++c){                     // average the channels to mono
            const char *s = p + (static_cast<qsizetype>(f) * ch + c) * bps;
            float v = 0;
            switch(m_infmt){
            case QAudioFormat::UInt8: v = ((float)(uint8_t)s[0] - 128.0f) * 256.0f; break;
            case QAudioFormat::Int32: { int32_t x; memcpy(&x, s, 4); v = (float)(x / 65536); break; }
            case QAudioFormat::Float: { float x; memcpy(&x, s, 4); v = x * 32767.0f; break; }
            default: { int16_t x; memcpy(&x, s, 2); v = (float)x; break; }
            }
            acc += v;
        }
        acc /= (float)ch;
        // resample to 8 kHz by averaging (m_srm = 1: pass through)
        m_rs_acc += acc; m_rs_n++; m_rs_pos += 1.0f;
        if(m_rs_pos >= m_srm - 0.0001f){
            m_rs_pos -= m_srm;
            if(m_rs_pos < 0) m_rs_pos = 0;
            float o = (m_rs_acc / (float)m_rs_n) * m_ingain;
            m_rs_acc = 0; m_rs_n = 0;
            if(o > 32767.0f) o = 32767.0f; else if(o < -32768.0f) o = -32768.0f;
            m_audioinq.enqueue(static_cast<int16_t>(o));
        }
    }
    while(m_audioinq.size() > 8000) m_audioinq.dequeue();    // never let a stalled consumer build up seconds of delay
}

void AudioEngine::stop_capture()
{
	if(m_in != nullptr){
        m_in->reset();
	}
}

void AudioEngine::start_playback()
{
    // Only start if stopped or suspended - IdleState and ActiveState mean already started
    if (m_out == nullptr) {
        return;   // no playback hardware
    }
    if (m_out->state() == QAudio::StoppedState || m_out->state() == QAudio::SuspendedState) {
        m_outdev = m_out->start();
	}
}

void AudioEngine::stop_playback()
{
	if (m_out) {
		m_out->reset();
	}
}

bool AudioEngine::playback_drained()
{
	if((m_out == nullptr) || (m_out->state() == QAudio::StoppedState)){
		return true;
	}
	return m_out->bytesFree() >= m_out->bufferSize();
}

void AudioEngine::write(int16_t *pcm, size_t s, float fade_from, float fade_to)
{
	m_maxlevel = 0;
/*
	fprintf(stderr, "AUDIOOUT: ");
	for(int i = 0; i < s; ++i){
		fprintf(stderr, "%04x ", (uint16_t)pcm[i]);
	}
	fprintf(stderr, "\n");
	fflush(stderr);
*/
	if(m_agc){
		process_audio(pcm, s);
	}

	// Optional linear fade, applied after AGC so the AGC cannot undo it.
	if((fade_from != 1.0f) || (fade_to != 1.0f)){
		for(size_t i = 0; i < s; ++i){
			const float g = fade_from + (fade_to - fade_from) * (float)(i + 1) / (float)s;
			pcm[i] = static_cast<int16_t>(pcm[i] * g);
		}
	}

	if(m_outvol != 1.0f){
		for(size_t i = 0; i < s; ++i){
			pcm[i] = static_cast<int16_t>(pcm[i] * m_outvol);
		}
	}

    if(m_outdev != nullptr){
        size_t l = m_outdev->write((const char *) pcm, sizeof(int16_t) * s);
        if (l*2 < s){
            qDebug() << "AudioEngine::write() " << s << ":" << l << ":" << (int)m_out->bytesFree() << ":" << m_out->bufferSize() << ":" << m_out->error();
        }
    }

	for(uint32_t i = 0; i < s; ++i){
		if(pcm[i] > m_maxlevel){
			m_maxlevel = pcm[i];
		}
	}
}

uint16_t AudioEngine::read(int16_t *pcm, int s)
{
	m_maxlevel = 0;

	if(m_audioinq.size() >= s){
		for(int i = 0; i < s; ++i){
			pcm[i] = m_audioinq.dequeue();
			if(pcm[i] > m_maxlevel){
				m_maxlevel = pcm[i];
			}
		}
		return 1;
	}
	else if(m_in == nullptr){
		memset(pcm, 0, sizeof(int16_t) * s);
		return 1;
	}
	else{
		return 0;
	}
}

uint16_t AudioEngine::read(int16_t *pcm)
{
	int s;
	m_maxlevel = 0;

	if(m_audioinq.size() >= 160){
		s = 160;
	}
	else{
		s = m_audioinq.size();
	}

	for(int i = 0; i < s; ++i){
		pcm[i] = m_audioinq.dequeue();
		if(pcm[i] > m_maxlevel){
			m_maxlevel = pcm[i];
		}
	}

	return s;
}

// process_audio() based on code from DSD https://github.com/szechyjs/dsd
void AudioEngine::process_audio(int16_t *pcm, size_t s)
{
	float aout_abs, max, gainfactor, gaindelta, maxbuf;

	for(size_t i = 0; i < s; ++i){
		m_audio_out_temp_buf[i] = static_cast<float>(pcm[i]);
	}

	// detect max level
	max = 0;
	m_audio_out_temp_buf_p = m_audio_out_temp_buf;

	for (size_t i = 0; i < s; i++){
		aout_abs = fabsf(*m_audio_out_temp_buf_p);

		if (aout_abs > max){
			max = aout_abs;
		}

		m_audio_out_temp_buf_p++;
	}

	*m_aout_max_buf_p = max;
	m_aout_max_buf_p++;
	m_aout_max_buf_idx++;

	if (m_aout_max_buf_idx > 24){
		m_aout_max_buf_idx = 0;
		m_aout_max_buf_p = m_aout_max_buf;
	}

	// lookup max history
	for (size_t i = 0; i < 25; i++){
		maxbuf = m_aout_max_buf[i];

		if (maxbuf > max){
			max = maxbuf;
		}
	}

	// determine optimal gain level
	if (max > static_cast<float>(0)){
		gainfactor = (static_cast<float>(30000) / max);
	}
	else{
		gainfactor = static_cast<float>(50);
	}

	if (gainfactor < m_aout_gain){
		m_aout_gain = gainfactor;
		gaindelta = static_cast<float>(0);
	}
	else{
		if (gainfactor > static_cast<float>(50)){
			gainfactor = static_cast<float>(50);
		}

		gaindelta = gainfactor - m_aout_gain;

		if (gaindelta > (static_cast<float>(0.05) * m_aout_gain)){
			gaindelta = (static_cast<float>(0.05) * m_aout_gain);
		}
	}

	gaindelta /= static_cast<float>(s); //160

	// adjust output gain
	m_audio_out_temp_buf_p = m_audio_out_temp_buf;

	for (size_t i = 0; i < s; i++){
		*m_audio_out_temp_buf_p = (m_aout_gain + (static_cast<float>(i) * gaindelta)) * (*m_audio_out_temp_buf_p);
		m_audio_out_temp_buf_p++;
	}

	m_aout_gain += (static_cast<float>(s) * gaindelta);
	m_audio_out_temp_buf_p = m_audio_out_temp_buf;

	for (size_t i = 0; i < s; i++){
		*m_audio_out_temp_buf_p *= m_volume;
		if (*m_audio_out_temp_buf_p > static_cast<float>(32760)){
			*m_audio_out_temp_buf_p = static_cast<float>(32760);
		}
		else if (*m_audio_out_temp_buf_p < static_cast<float>(-32760)){
			*m_audio_out_temp_buf_p = static_cast<float>(-32760);
		}
		pcm[i] = static_cast<int16_t>(*m_audio_out_temp_buf_p);
		m_audio_out_temp_buf_p++;
	}
}

void AudioEngine::handleStateChanged(QAudio::State newState)
{
	switch (newState) {
	case QAudio::ActiveState:
        //qDebug() << "AudioOut state active";
		break;
	case QAudio::SuspendedState:
        //qDebug() << "AudioOut state suspended";
		break;
	case QAudio::IdleState:
        //qDebug() << "AudioOut state idle";
		break;
	case QAudio::StoppedState:
        //qDebug() << "AudioOut state stopped";
		break;
	default:
		break;
	}
}
