#ifndef __include_lib_dvb_pvrparse_h
#define __include_lib_dvb_pvrparse_h

#include <lib/components/file_monitor.h>
#include <lib/dvb/idvb.h>
#include <map>
#include <set>

	/* This module parses TS data and collects valuable information  */
	/* about it, like PTS<->offset correlations and sequence starts. */

class eFileWatch;

	/* At first, we define the collector class: */
class eMPEGStreamInformation
{
	void fileWatchEventCB(eFileWatch *fw, eFileEvent evt);
public:
	eMPEGStreamInformation();
	~eMPEGStreamInformation();

	void closeWrite();
	void closeRead();
		/* we order by uint64_t here, since the timestamp may */
		/* wrap around. */
		/* we only record sequence start's pts values here. */
	std::map<uint64_t, pts_t> m_access_points;
		/* timestampDelta is in fact the difference between */
		/* the PTS in the stream and a real PTS from 0..max */
	std::map<uint64_t, pts_t> m_timestamp_deltas;

		/* these are non-fixed up pts value (like m_access_points), just used to accelerate stuff. */
	std::multimap<pts_t, uint64_t> m_pts_to_offset; 

	int startSave(const char *filename);
	int stopSave(void);
	int load(const char *filename);
	
		/* recalculates timestampDeltas */
	void fixupDiscontinuties();
	
		/* get delta at specific offset */
	pts_t getDelta(uint64_t offset);
	
		/* fixup timestamp near offset, i.e. convert to zero-based */
	int fixupPTS(const uint64_t &offset, pts_t &ts);

		/* get PTS before offset */	
	int getPTS(uint64_t &offset, pts_t &pts);
	
		/* inter/extrapolate timestamp from offset */
	pts_t getInterpolated(uint64_t offset);
	
	uint64_t getAccessPoint(pts_t ts, int marg=0);
	
	int getNextAccessPoint(pts_t &ts, const pts_t &start, int direction);

	bool AccessPointsAvail();
	bool StructureCacheAvail();
	
	typedef unsigned long long structure_data;
		/* this is usually:
			sc | (other_information << 8)
			but is really specific to the used video encoder.
		*/
	void writeStructureEntry(uint64_t offset, structure_data data);

		/* get a structure entry at given offset (or previous one, if no exact match was found).
		   optionally, return next element. Offset will be returned. this allows you to easily
		   get previous and next structure elements. */
	int getStructureEntry(uint64_t &offset, uint64_t &data, int get_next);
	int update_structure_cache(uint64_t offset);

	std::string m_filename;

	/* used for read */
	int m_structure_cache_entries;
	int m_structure_read_fd;
	uint64_t *m_structure_read_mem;
	off_t m_structure_read_size;
	int m_structure_read_prev_result; // prev returned entry used for accel next search
	eFileWatch *m_structure_file_watch;
	bool m_structure_file_changed;

	/* used for write */
	int m_structure_wp;
	int m_structure_write_fd;
	uint64_t *m_structure_write_mem;
};

	/* Now we define the parser's state: */
class eMPEGStreamParserTS
{
public:
	eMPEGStreamParserTS(eMPEGStreamInformation &streaminfo);
	void parseData(uint64_t offset, const void *data, unsigned int len);
	void setPid(int pid, int streamtype);
	int getLastPTS(pts_t &last_pts);
	void setAccessPoints(bool on);
private:
	eMPEGStreamInformation &m_streaminfo;
	unsigned char m_pkt[188];
	int m_pktptr;
	int processPacket(const unsigned char *pkt, uint64_t offset);
	inline int wantPacket(const unsigned char *hdr) const;
	int m_pid, m_streamtype;
	int m_need_next_packet;
	int m_last_pts_valid;
	pts_t m_last_pts;
	bool m_collect_accesspoints;
	unsigned char m_pkt2[188*2];
	uint64_t m_last_sc_offset;
	int m_last_sc_offset_valid;
};

#endif
