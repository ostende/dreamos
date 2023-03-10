from __future__ import absolute_import

from enigma import eInputDeviceManager
from Components.config import config
from Components.ActionMap import ActionMap
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Components.Label import Label
from Screens.InputDeviceSetup import AdvancedInputDeviceSetup
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.SetupGuide import SetupGuide
from Tools.DreamboxHardware import getFPVersion
from Tools.Log import Log

from twisted.internet import reactor

from .InputDeviceAdapterFlasher import InputDeviceAdapterFlasher, InputDeviceUpdateChecker
from .InputDeviceUpdateHandlerBase import InputDeviceUpdateHandlerBase
from .InputDeviceIRProg import InputDeviceIRProg

#from .InputDeviceDfuUpdate import InputDeviceDfuUpdate

class InputDeviceManagementBase(object):
	def __init__(self):
		try:
			self["pin"] = StaticText() #unused dummy
		except:
			pass
		self._devices = []
		self._list = List([], enableWrapAround=True, buildfunc=self._inputDeviceBuildFunc)

		self._dm = eInputDeviceManager.getInstance()

		self.__highlightDevice = None
		self._listFeedbackDisabled = False

		self.__deviceListChanged_conn = self._dm.deviceListChanged.connect(self._devicesChanged)
		self.__deviceStateChanged_conn = self._dm.deviceStateChanged.connect(self._devicesChanged)
		self.__unboundRemoteKeyPressed_conn = self._dm.unboundRemoteKeyPressed.connect(self._onUnboundRemoteKeyPressed)
		self._refresh()

	def _disableListFeedback(self):
		if config.inputDevices.settings.listboxFeedback.value:
			config.inputDevices.settings.listboxFeedback.value = False
			self._listFeedbackDisabled = True

	def _restoreListFeedback(self):
		if self._listFeedbackDisabled:
			config.inputDevices.settings.listboxFeedback.value = True
			self._listFeedbackDisabled = False

	def responding(self):
		return self._dm.responding()

	def available(self):
		return self._dm.available()

	def _getCurrentInputDevice(self):
		return self._list.getCurrent() and self._list.getCurrent()[1]

	_currentInputDevice = property(_getCurrentInputDevice)

	def _reload(self):
		index = self._list.index
		if index < 0:
			index = 0
		self._devices = self._getInputDevices()
		self._list.list = self._devices
		if self._getInputDevicesCount() > index:
			self._list.index = index

	def _refresh(self):
		self._dm.refresh()

	def _getInputDevicesCount(self):
		return len(self._devices)

	def _getInputDevices(self):
		items = self._dm.getAvailableDevices()
		devices = []
		for d in items:
			devices.append((d.address(),d))
		return devices

	def _inputDeviceBuildFunc(self, title, device):
		bound = ""
		if device.bound():
			bound = _("bound")
		# A device may be connected but not yet bound right after binding has started!
		elif device.connected():
			bound = _("...")
		name = device.name() or device.shortName()
		name = _(name) if name else _("DM Remote")
		return (
			name,
			"%s dBm" %(int(device.rssi()),),
			device.address(),
			bound,
			_("connected") if device.connected() else _("disconnected")
		)

	def _devicesChanged(self, *args):
		pass

	def _connectDevice(self, device):
		if not device:
			return
		self.session.toastManager.showToast(_("Connecting to %s") %(device.address(),))
		self._dm.connectDevice(device)

	def _disconnectDevice(self, device):
		if device and device.connected():
			self._dm.disconnectDevice(device)

	def _onUnboundRemoteKeyPressed(self, address, key):
		pass

	def _highlight(self):
		d = self._currentInputDevice
		if d:
			if not self.__highlightDevice or d.address() != self.__highlightDevice.address():
				d.vibrate()
				reactor.callLater(0.4, d.vibrate)

				col = int(config.inputDevices.settings.connectedColor.value, 0)
				contrast = 0xffffff - col

				d.setLedColor(contrast)
				reactor.callLater(0.8, d.setLedColor, col)
				self.__highlightDevice = d
		else:
			self.__highlightDevice = None

class InputDeviceManagement(Screen, InputDeviceManagementBase, InputDeviceUpdateHandlerBase):
	def __init__(self, session):
		Screen.__init__(self, session, windowTitle=_("Input devices"))
		InputDeviceManagementBase.__init__(self)
		InputDeviceUpdateHandlerBase.__init__(self)
		self["description"] = StaticText("")
		self["list"] = self._list
		self["inputActions"] = ActionMap(["OkCancelActions", "ColorActions"],
		actions={
			"ok" : self._onOk,
			"cancel" : self.close,
			"red" : self._dfu,
			"green" : self._irProg,
			"yellow" : self._dm.rescan,
			"blue" : self._advanced,
		})

		self["key_red"] = Label()
		self["key_green"] = Label()
		self["key_yellow"] = Label(_("Rescan"))
		self["key_blue"] = Label(_("Advanced"))
		self._updateChecker = InputDeviceUpdateChecker()
		self._updateChecker.onUpdateAvailable.append(self._onUpdateAvailable)
		self._updateChecker.check()
		self._list.onSelectionChanged.append(self.__onSelectionChanged)
		self._devices = []
		self._reload()
		self.onShow.append(self._onShow)
		self.onHide.append(self._restoreListFeedback)
		self.onFirstExecBegin.append(self._checkAdapter)
		self.onLayoutFinish.append(self.__onSelectionChanged)

	def _onShow(self):
		self._disableListFeedback()
		self._refresh()

	def _dfu(self):
		if not self._dm.hasFeature(eInputDeviceManager.FEATURE_DFU_UPDATE):
			return
		from .Dfu.DfuGuide import DfuWelcomeStep, DfuUpdateStep, DfuFinishStep
		steps = [{
			10 : DfuWelcomeStep,
			20 : DfuUpdateStep,
			30 : DfuFinishStep,
		}]
		self.session.open(SetupGuide, steps=steps)

	def _updateButtons(self):
		device = self._currentInputDevice
		if device and device.connected() and device.checkVersion(1,3) >= 0:
			self["key_green"].setText(_("IR-Setup"))
		else:
			self["key_green"].setText("")

		if self._dm.hasFeature(eInputDeviceManager.FEATURE_DFU_UPDATE):
			self["key_red"].setText(_("Update"))
		else:
			self["key_red"].setText("")

	def _irProg(self):
		device = self._currentInputDevice
		if not device or not device.connected() or device.checkVersion(1,3) < 0:
			return
		self.session.open(InputDeviceIRProg, device)

	def _advanced(self):
		self.session.open(AdvancedInputDeviceSetup)

	def _onUpdateAvailable(self):
		text = self._fpUpdateText()
		self.session.openWithCallback(
			self._onUpdateAnswer,
			MessageBox,
			text,
			type=MessageBox.TYPE_YESNO,
			windowTitle=_("Update Bluetooth Receiver Firmware?"))


	def _checkAdapter(self):
		if self.available() and not self.responding():
			self.session.openWithCallback(
				self._onUpdateAnswer,
				MessageBox,
				_("Your Dreambox bluetooth receiver has no firmware installed.\nInstall the latest firmware now?"),
				type=MessageBox.TYPE_YESNO,
				windowTitle=_("Flash Bluetooth Receiver Firmware?"))
			return

	def __onSelectionChanged(self):
		self._highlight()
		self._updateButtons()
		if not self.available():
			self["description"].text = _("No dreambox bluetooth receiver detected! Sorry!")
			return
		text = ""
		if self._currentInputDevice and self._currentInputDevice.connected():
			text = _("Press OK to disconnect")
		elif self._currentInputDevice:
			text = _("Press OK to connect the selected remote control.")
			if self._dm.hasFeature(eInputDeviceManager.FEATURE_UNCONNECTED_KEYPRESS) and len(self._devices) > 1:
				text = "%s\n%s" %(("Please pickup the remote control you want to connect and press any number key on it to select it in the list.\n"), text)
		if text != self["description"].text:
			self["description"].text = text

	def _devicesChanged(self, *args):
		self._reload()
		self.__onSelectionChanged()

	def _onOk(self):
		device = self._currentInputDevice
		if not device:
			return
		name = device.shortName() or "Dream RCU"
		if device.connected():
			self.session.openWithCallback(self._onDisconnectResult, MessageBox, _("Really disconnect %s (%s)?") %(name, device.address()), windowTitle=_("Disconnect paired remote?"))
		else:
			self.session.openWithCallback(self._onConnectResult, MessageBox, _("Do you really want to connect %s (%s) ") %(name, device.address()), windowTitle=_("Connect new remote?"))

	def _onDisconnectResult(self, result):
		if result:
			self._disconnectDevice(self._currentInputDevice)

	def _onConnectResult(self, result):
		if result:
			self._connectDevice(self._currentInputDevice)

	def _onUnboundRemoteKeyPressed(self, address, key):
		index = 0
		for d in self._devices:
			if d[1].address() == address:
				self._list.index = index
				break
			index += 1
