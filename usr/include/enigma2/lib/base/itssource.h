#ifndef __lib_base_idatasource_h
#define __lib_base_idatasource_h

#include <lib/base/connection.h>
#include <lib/base/esignal.h>
#include <lib/base/object.h>

class iTsSource: public iObject
{
protected:
	eSignal2<void, int, std::string> m_sourceEvent;
public:
	 /* NOTE: should only be used to get current position or filelength */
	virtual int64_t lseek(int64_t offset, int whence) = 0;
	
	/* NOTE: you must be able to handle short reads! */
	virtual ssize_t read(int64_t offset, void *buf, size_t count)=0; /* NOTE: this is what you in normal case have to use!! */

	virtual uint64_t length() const = 0;
	virtual bool valid() const = 0;

	virtual RESULT connectSourceEvent(const sigc::slot2<void,int,std::string> &sourceEventChange, ePtr<eConnection> &connection){ return -1; };
};

#endif
