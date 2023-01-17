#ifndef __lib_dvb_frontendparms_h
#define __lib_dvb_frontendparms_h

#include <lib/python/swig.h>

class SatelliteDeliverySystemDescriptor;
class CableDeliverySystemDescriptor;
class TerrestrialDeliverySystemDescriptor;
class S2SatelliteDeliverySystemDescriptor;
class T2DeliverySystemDescriptor;

struct eDVBFrontendParametersSatellite
{
#ifndef SWIG
	void set(const SatelliteDeliverySystemDescriptor &);
	void set(const S2SatelliteDeliverySystemDescriptor &);
#endif
	enum {
		Polarisation_Horizontal, Polarisation_Vertical, Polarisation_CircularLeft, Polarisation_CircularRight
	};

	enum {
		Inversion_Off, Inversion_On, Inversion_Unknown
	};

	enum {
		FEC_Auto, FEC_1_2, FEC_2_3, FEC_3_4, FEC_5_6, FEC_7_8, FEC_8_9, FEC_3_5, FEC_4_5, FEC_9_10, FEC_6_7, FEC_None=15
	};

	enum {
		System_DVB_S, System_DVB_S2, System_DVB_S_S2
	};

	enum {
		Modulation_Auto, Modulation_QPSK, Modulation_8PSK, Modulation_QAM16, Modulation_16APSK, Modulation_32APSK
	};

	// dvb-s2
	enum {
		RollOff_alpha_0_35, RollOff_alpha_0_25, RollOff_alpha_0_20
	};

	enum {
		Pilot_Off, Pilot_On, Pilot_Unknown
	};

	enum {
		PLS_Root, PLS_Gold, PLS_Combo, PLS_Unknown
	};

	bool no_rotor_command_on_tune;
	unsigned int frequency, symbol_rate;
	int polarisation, fec, inversion, orbital_position, system, modulation, rolloff, pilot, is_id, pls_mode, pls_code;
};
SWIG_ALLOW_OUTPUT_SIMPLE(eDVBFrontendParametersSatellite);

struct eDVBFrontendParametersCable
{
#ifndef SWIG
	void set(const CableDeliverySystemDescriptor  &);
#endif
	enum {
		Inversion_Off, Inversion_On, Inversion_Unknown
	};

	enum {
		FEC_Auto, FEC_1_2, FEC_2_3, FEC_3_4, FEC_5_6, FEC_7_8, FEC_8_9, FEC_None=15
	};

	enum {
		Modulation_Auto, Modulation_QAM16, Modulation_QAM32, Modulation_QAM64, Modulation_QAM128, Modulation_QAM256
	};

	unsigned int frequency, symbol_rate;
	int modulation, inversion, fec_inner;
};
SWIG_ALLOW_OUTPUT_SIMPLE(eDVBFrontendParametersCable);

struct eDVBFrontendParametersTerrestrial
{
#ifndef SWIG
	eDVBFrontendParametersTerrestrial();
	void set(const TerrestrialDeliverySystemDescriptor  &);
	void set(const T2DeliverySystemDescriptor &, unsigned int freq);
#endif
	enum {
		Bandwidth_8MHz, Bandwidth_7MHz, Bandwidth_6MHz, Bandwidth_Auto, Bandwidth_5MHz, Bandwidth_1_712MHz, Bandwidth_10MHz
	};

	enum {
		FEC_1_2, FEC_2_3, FEC_3_4, FEC_5_6, FEC_7_8, FEC_Auto, FEC_6_7, FEC_8_9, FEC_3_5, FEC_4_5
	};

	enum {
		TransmissionMode_2k, TransmissionMode_8k, TransmissionMode_Auto, TransmissionMode_4k, TransmissionMode_1k, TransmissionMode_16k, TransmissionMode_32k
	};

	enum {
		GuardInterval_1_32, GuardInterval_1_16, GuardInterval_1_8, GuardInterval_1_4, GuardInterval_Auto, GuardInterval_1_128, GuardInterval_19_128, GuardInterval_19_256
	};

	enum {
		Hierarchy_None, Hierarchy_1, Hierarchy_2, Hierarchy_4, Hierarchy_Auto
	};

	enum {
		Modulation_QPSK, Modulation_QAM16, Modulation_QAM64, Modulation_Auto, Modulation_QAM256
	};

	enum {
		Inversion_Off, Inversion_On, Inversion_Unknown
	};

	enum {
		System_DVB_T, System_DVB_T2, System_DVB_T_T2
	};

	unsigned int frequency;
	int bandwidth;
	int code_rate_HP; // DVB-T only
	int code_rate_LP; // DVB-T2 fec_inner!
	int modulation;
	int transmission_mode;
	int guard_interval;
	int hierarchy;
	int inversion;
	int system;
	int plp_id; // DVB-T2 only
};
SWIG_ALLOW_OUTPUT_SIMPLE(eDVBFrontendParametersTerrestrial);

#endif
