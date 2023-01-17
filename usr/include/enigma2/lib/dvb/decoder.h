#ifndef __decoder_h
#define __decoder_h

class eSocketNotifier;

#include <lib/base/object.h>
#include <lib/dvb/demux.h>

class eDVBAudio: public iObject
{
	E_DECLARE_PRIVATE(eDVBAudio)

	DECLARE_REF(eDVBAudio);
private:
	ePtr<iDVBDemux> m_demux;
	int m_fd, m_fd_demux, m_dev;
public:
	enum { aMPEG, aAC3, aDTS, aAAC, aAACHE, aLPCM, aDTSHD, aDDP };
	eDVBAudio(iDVBDemux *demux, int dev);
	enum { aMonoLeft, aStereo, aMonoRight };
	void setChannel(int channel);
	void stop();
	int startPid(int pid, int type);
	void flush();
	void freeze();
	void unfreeze();
	int getPTS(pts_t &now);
	virtual ~eDVBAudio();
	void setSTCValidState(int state);
};

class eDeviceEventManager;

class eDVBVideo: public iObject, public sigc::trackable
{
	E_DECLARE_PRIVATE(eDVBVideo)

	DECLARE_REF(eDVBVideo);
private:
	ePtr<iDVBDemux> m_demux;
	int m_fd, m_fd_demux, m_dev;
	ePtr<eSocketNotifier> m_sn;
	void video_event(int what);
#if defined(__aarch64__)
	int m_fd_amvideoPoll;
	ePtr<eSocketNotifier> m_sn_amvideoPoll;
	void amvideo_event(int);

	eDeviceEventManager *m_evtMgr;
	void udev_event(stringMap msg);
#endif
	sigc::signal1<void, struct iTSMPEGDecoder::videoEvent> m_event;
	int m_width, m_height, m_framerate, m_aspect, m_progressive;
	std::string m_eotf;
public:
	enum { MPEG2, MPEG4_H264, MPEG1, MPEG4_Part2, VC1, VC1_SM, H265 };
	eDVBVideo(iDVBDemux *demux, int dev);
	void stop();
	int startPid(int pid, int type=MPEG2);
	void flush();
	void freeze();
	int setSlowMotion(int repeat);
	int setFastForward(int skip);
	void unfreeze();
	int getPTS(pts_t &now);
	virtual ~eDVBVideo();
	RESULT connectEvent(const sigc::slot1<void, struct iTSMPEGDecoder::videoEvent> &event, ePtr<eConnection> &conn);
	int getWidth();
	int getHeight();
	int getProgressive();
	int getFrameRate();
	int getAspect();
	const char* getEotf();
};

class eDVBPCR: public iObject
{
	DECLARE_REF(eDVBPCR);
private:
	ePtr<iDVBDemux> m_demux;
	int m_fd_demux, m_dev;
public:
	eDVBPCR(iDVBDemux *demux, int dev);
	int startPid(int pid);
	void stop();
	void restart();
	virtual ~eDVBPCR();
};

class eDVBTText: public iObject
{
	DECLARE_REF(eDVBTText);
private:
	ePtr<iDVBDemux> m_demux;
	int m_fd_demux, m_dev;
public:
	eDVBTText(iDVBDemux *demux, int dev);
	int startPid(int pid);
	void stop();
	virtual ~eDVBTText();
};

class eTSMPEGDecoder: public sigc::trackable, public iTSMPEGDecoder
{
	DECLARE_REF(eTSMPEGDecoder);
private:
	static int m_pcm_delay;
	static int m_ac3_delay;
	static int m_audio_channel;
	std::string m_radio_pic;
	ePtr<iDVBDemux> m_demux;
	ePtr<eDVBAudio> m_audio;
	ePtr<eDVBVideo> m_video;
	ePtr<eDVBPCR> m_pcr;
	ePtr<eDVBTText> m_text;
	int m_vpid, m_vtype, m_apid, m_atype, m_pcrpid, m_textpid;
	enum
	{
		changeVideo = 1,
		changeAudio = 2,
		changePCR   = 4,
		changeText  = 8,
		changeState = 16,
	};
	int m_changed, m_decoder;
	int m_state;
	int m_ff_sm_ratio;
	int setState();
	ePtr<eConnection> m_demux_event_conn;
	ePtr<eConnection> m_video_event_conn;

	void demux_event(int event);
	void video_event(struct videoEvent);
	sigc::signal1<void, struct videoEvent> m_video_event;
	sigc::signal1<void, int> m_state_event;
	int m_video_clip_fd;
	ePtr<eTimer> m_showSinglePicTimer;
	void finishShowSinglePic(); // called by timer
public:
	enum { pidNone = -1 };
	eTSMPEGDecoder(iDVBDemux *demux, int decoder);
	virtual ~eTSMPEGDecoder();
	RESULT setVideoPID(int vpid, int type);
	RESULT setAudioPID(int apid, int type);
	RESULT setAudioChannel(int channel);
	int getAudioChannel();
	RESULT setPCMDelay(int delay);
	int getPCMDelay() { return m_pcm_delay; }
	RESULT setAC3Delay(int delay);
	int getAC3Delay() { return m_ac3_delay; }
	RESULT setSyncPCR(int pcrpid);
	RESULT setTextPID(int textpid);

		/*
		The following states exist:

		 - stop: data source closed, no playback
		 - pause: data source active, decoder paused
		 - play: data source active, decoder consuming
		 - decoder fast forward: data source linear, decoder drops frames
		 - trickmode, highspeed reverse: data source fast forwards / reverses, decoder just displays frames as fast as it can
		 - slow motion: decoder displays frames multiple times
		*/
	enum {
		stateStop,
		statePause,
		statePlay,
		stateDecoderFastForward,
		stateTrickmode,
		stateSlowMotion
	};
	RESULT set(); /* just apply settings, keep state */
	RESULT play(); /* -> play */
	RESULT pause(); /* -> pause */
	RESULT setFastForward(int frames_to_skip); /* -> decoder fast forward */
	RESULT setSlowMotion(int repeat); /* -> slow motion **/
	RESULT setTrickmode(); /* -> highspeed fast forward */

	RESULT flush();
	RESULT showSinglePic(const char *filename);
	RESULT setRadioPic(const std::string &filename);
		/* what 0=auto, 1=video, 2=audio. */
	RESULT getPTS(int what, pts_t &pts);
	RESULT connectVideoEvent(const sigc::slot1<void, struct videoEvent> &event, ePtr<eConnection> &connection);
	RESULT connectStateEvent(const sigc::slot1<void, int> &event, ePtr<eConnection> &connection);
	int getVideoDecoderId();
	int getVideoWidth();
	int getVideoHeight();
	int getVideoProgressive();
	int getVideoFrameRate();
	int getVideoAspect();
	int getState();
	const char* getEotf();
	static RESULT setHwPCMDelay(int delay);
	static RESULT setHwAC3Delay(int delay);
};

#endif
