from __future__ import division
from __future__ import print_function
from Components.Converter.Converter import Converter
from Components.Element import cached
from enigma import iDVBFrontend

feSatellite = iDVBFrontend.feSatellite
feCable = iDVBFrontend.feCable
feTerrestrial = iDVBFrontend.feTerrestrial

class FrontendInfo(Converter, object):
	BER = 0
	SNR = 1
	AGC = 2
	LOCK = 3
	SNRdB = 4
	SLOT_NUMBER = 5
	TUNER_TYPE = 6
	INPUT_NUMBER = 7

	def __init__(self, type):
		Converter.__init__(self, type)
		self.isAnimated = False
		if type == "BER":
			self.type = self.BER
		elif type == "SNR":
			self.type = self.SNR
		elif type == "SNRdB":
			self.type = self.SNRdB
		elif type == "AGC":
			self.type = self.AGC
		elif type == "NUMBER":
			self.type = self.SLOT_NUMBER
		elif type == "INPUT":
			self.type = self.INPUT_NUMBER
		elif type == "TYPE":
			self.type = self.TUNER_TYPE
		else:
			self.type = self.LOCK

	@cached
	def getText(self):
		assert self.type not in (self.LOCK, self.SLOT_NUMBER, self.INPUT_NUMBER), "the text output of FrontendInfo cannot be used for lock info"
		percent = None
		if self.type == self.BER: # as count
			count = self.source.ber
			if count is not None:
				return str(count)
			else:
				return "N/A"
		elif self.type == self.AGC:
			percent = self.source.agc
		elif self.type == self.SNR:
			percent = self.source.snr
		elif self.type == self.SNRdB:
			if self.source.snr_db is not None:
				return "%3.02f dB" % (self.source.snr_db / 100.0)
			elif self.source.snr is not None: #fallback to normal SNR...
				percent = self.source.snr
		elif self.type == self.TUNER_TYPE:
			frontend_type = self.source.frontend_type
			if frontend_type is None:
				return "Unknown"
			elif frontend_type == feSatellite:
				return 'DVB-S'
			elif frontend_type == feCable:
				return 'DVB-C'
			elif frontend_type == feTerrestrial:
				return 'DVB-T'
			return "Unknown"
		if percent is None:
			return "N/A"
		return "%d %%" % (percent * 100 // 65536)

	@cached
	def getBool(self):
		assert self.type in (self.LOCK, self.BER), "the boolean output of FrontendInfo can only be used for lock or BER info"
		if self.type == self.LOCK:
			lock = self.source.lock
			if lock is None:
				lock = False
			return lock
		else:
			ber = self.source.ber
			if ber is None:
				ber = 0
			return ber > 0

	text = property(getText)

	boolean = property(getBool)

	@cached
	def getValue(self):
		assert self.type != self.LOCK, "the value/range output of FrontendInfo can not be used for lock info"
		if self.type == self.AGC:
			return self.source.agc or 0
		elif self.type == self.SNR:
			return self.source.snr or 0
		elif self.type == self.BER:
			if self.BER < self.range:
				return self.BER or 0
			else:
				return self.range
		elif self.type == self.TUNER_TYPE:
			# convert for skin compatibility reasons
			frontend_type = self.source.frontend_type
			if frontend_type == feSatellite:
				return 0
			elif frontend_type == feCable:
				return 1
			elif frontend_type == feTerrestrial:
				return 2
			print("FIXMEE unknown frontend type in FrontendInfo getValue Converter return 0 (SAT)", frontend_type)
			return 0
		elif self.type == self.SLOT_NUMBER:
			num = self.source.slot_number
			return num is None and -1 or num
		elif self.type == self.INPUT_NUMBER:
			num = self.source.input_number
			return num is None and -1 or num

	range = 65536
	value = property(getValue)
