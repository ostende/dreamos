from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Plugins.Plugin import PluginDescriptor

from Components.ConfigList import ConfigListScreen
from Components.ActionMap import ActionMap
from Components.config import config
from Components.NimManager import nimmanager as nimmgr

class SecParameterSetup(Screen, ConfigListScreen):
	skin = """
		<screen position="center,120" size="820,520" title="Satellite Equipment Setup">
			<widget enableWrapAround="1" name="config" position="10,5" scrollbarMode="showOnDemand" size="800,510" />
		</screen>"""

	def __init__(self, session):
		self.skin = SecParameterSetup.skin

		self["actions"] = ActionMap(["SetupActions"],
		{
			"ok": self.keySave,
			"cancel": self.keyCancel,
		}, -2)

		Screen.__init__(self, session)
		list = [
			("Delay after diseqc reset command (default: 50)", config.sec.delay_after_diseqc_reset_cmd),
			("Delay after diseqc peripherial poweron command (default: 150)", config.sec.delay_after_diseqc_peripherial_poweron_cmd),
			("Delay after continuous tone disable before diseqc (default: 25)", config.sec.delay_after_continuous_tone_disable_before_diseqc),
			("Delay after final continuous tone change (default: 10)", config.sec.delay_after_final_continuous_tone_change),
			("Delay after final voltage change (default: 10)", config.sec.delay_after_final_voltage_change),
			("Delay between diseqc repeat commands (default: 120)", config.sec.delay_between_diseqc_repeats),
			("Delay after last diseqc command (default: 50)", config.sec.delay_after_last_diseqc_command),
			("Delay after toneburst (default: 50)", config.sec.delay_after_toneburst),
			("Delay after change voltage before switch command (default: 20)", config.sec.delay_after_change_voltage_before_switch_command),
			("Delay after enable voltage before switch command (default: 1000)", config.sec.delay_after_enable_voltage_before_switch_command),
			("Delay after change voltage before unicable command (default: 10)", config.sec.delay_after_voltage_change_before_unicable_cmd),
			("Delay after unicable command (default: 5)", config.sec.delay_after_unicable_cmd),
			("Delay after unicable final voltage change (default: 10)", config.sec.delay_after_unicable_final_voltage_change),
			("Delay after set voltage before measure motor power (default: 500)", config.sec.delay_after_voltage_change_before_measure_idle_inputpower),
			("Delay after enable voltage before motor command (default: 900)", config.sec.delay_after_enable_voltage_before_motor_command),
			("Delay after motor stop command (default: 500)", config.sec.delay_after_motor_stop_command),
			("Delay after voltage change before motor command (default: 500)", config.sec.delay_after_voltage_change_before_motor_command),
			("Delay before sequence repeat (default: 70)", config.sec.delay_before_sequence_repeat),
			("Motor running timeout (default: 360)", config.sec.motor_running_timeout),
			("Motor command retries (default: 1)", config.sec.motor_command_retries) ]
		ConfigListScreen.__init__(self, list)

session = None

def confirmed(answer):
	global session
	if answer:
		session.open(SecParameterSetup)

def SecSetupMain(Session, **kwargs):
	global session
	session = Session
	session.openWithCallback(confirmed, MessageBox, _("Please do not change any values unless you know what you are doing!"), MessageBox.TYPE_INFO)

def SecSetupStart(menuid):
	# other menu than "scan"?
	if menuid != "scan": 
		return [ ]

	# only show if DVB-S frontends are available
	for slot in nimmgr.nim_slots:
		if slot.isEnabled("DVB-S"):
			return [(_("Satellite Equipment Setup"), SecSetupMain, "satellite_equipment_setup", None)]

	return [ ]

def Plugins(**kwargs):
	if (nimmgr.hasNimType("DVB-S")):
		return PluginDescriptor(name=_("Satellite Equipment Setup"), description=_("Setup your satellite equipment"), where = PluginDescriptor.WHERE_MENU, needsRestart = False, fnc=SecSetupStart)
	else:
		return []
