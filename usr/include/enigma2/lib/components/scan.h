#ifndef __lib_components_scan_h
#define __lib_components_scan_h

#include <lib/base/object.h>
#include <lib/base/esignal.h>
#include <lib/dvb/idvb.h>

class eDVBScan;

class eComponentScan: public sigc::trackable, public iObject
{
	DECLARE_REF(eComponentScan);
#ifndef SWIG
	void scanEvent(int event);
	ePtr<eConnection> m_scan_event_connection;
	ePtr<eDVBScan> m_scan;
	
	int m_done, m_failed;
	eSmartPtrList<iDVBFrontendParameters> m_initial;
#endif
public:
	eComponentScan();
	~eComponentScan();
	
	eSignal0<void> statusChanged;
	eSignal0<void> newService;
	
		/* progress between 0 and 100 */
	int getProgress();
	
		/* get number of services */
	int getNumServices();
	
		/* true when done or error */
	int isDone();
	
		/* get last added service */
	void getLastServiceName(std::string &SWIG_OUTPUT);
	
	int getError();
	
	void clear();
	void addInitial(const eDVBFrontendParametersSatellite &p);
	void addInitial(const eDVBFrontendParametersCable &p);
	void addInitial(const eDVBFrontendParametersTerrestrial &p);
	
		/* please keep the flags in sync with lib/dvb/scan.h ! */
	enum { scanNetworkSearch=1, scanRemoveServices=4, scanDontRemoveFeeds=8, scanDontRemoveUnscanned=16, clearToScanOnFirstNIT = 32, scanOnlyFree = 64, scanDontSkipEmptyTransponders = 128, scanOtherSDT = 256 };

	int start(int feid, int flags=0 );
	void setAdditionalTsidOnidCheckFunc( eSlot3<int,int,int,int> &func );
	SWIG_VOID(RESULT) getFrontend(ePtr<iDVBFrontend> &SWIG_OUTPUT);
	SWIG_VOID(RESULT) getCurrentTransponder(ePtr<iDVBFrontendParameters> &SWIG_OUTPUT);
};

#endif