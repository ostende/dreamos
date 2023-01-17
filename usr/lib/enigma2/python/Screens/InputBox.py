from __future__ import division
from __future__ import print_function
from enigma import getPrevAsciiCode
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import NumberActionMap
from Components.Label import Label
from Components.Input import Input
from Tools.BoundFunction import boundFunction
from time import time

class InputBox(Screen):
	IS_DIALOG = True
	def __init__(self, session, title = "", windowTitle = _("Input"), useableChars = None, **kwargs):
		Screen.__init__(self, session, windowTitle=windowTitle)

		self["text"] = Label(title)
		self["input"] = Input(**kwargs)
		self["input"].onInputUpdate.append(self._onInputUpdate)

		if useableChars is not None:
			self["input"].setUseableChars(useableChars)

		self["actions"] = NumberActionMap(["WizardActions", "InputBoxActions", "InputAsciiActions", "KeyboardInputActions"], 
		{
			"gotAsciiCode": self.gotAsciiCode,
			"ok": self.go,
			"back": self.cancel,
			"left": self.keyLeft,
			"right": self.keyRight,
			"home": self.keyHome,
			"end": self.keyEnd,
			"deleteForward": self.keyDelete,
			"deleteBackward": self.keyBackspace,
			"tab": self.keyTab,
			"toggleOverwrite": self.keyInsert,
			"1": self.keyNumberGlobal,
			"2": self.keyNumberGlobal,
			"3": self.keyNumberGlobal,
			"4": self.keyNumberGlobal,
			"5": self.keyNumberGlobal,
			"6": self.keyNumberGlobal,
			"7": self.keyNumberGlobal,
			"8": self.keyNumberGlobal,
			"9": self.keyNumberGlobal,
			"0": self.keyNumberGlobal
		}, -1)

		self._help_window = None

		if self["input"].type == Input.TEXT:
			self.onExecBegin.append(self.setKeyboardModeAscii)
		else:
			self.onExecBegin.append(self.setKeyboardModeNone)

		self.onClose.append(self.__onClose)
		self.onShow.append(self.__onShow)
		self.onHide.append(self.__onHide)

	def __onShow(self):
		self._showHelpWindow()

	def __onHide(self):
		self._closeHelpWindow()

	def __onClose(self):
		self._closeHelpWindow()

	def _onInputUpdate(self):
		if self._help_window:
			self._help_window.update(self["input"])

	def gotAsciiCode(self):
		self["input"].handleAscii(getPrevAsciiCode())

	def keyLeft(self):
		self["input"].left()

	def keyRight(self):
		self["input"].right()

	def keyNumberGlobal(self, number):
		self["input"].number(number)

	def keyDelete(self):
		self["input"].delete()

	def go(self):
		self.close(self["input"].getText())

	def cancel(self):
		self.close(None)

	def keyHome(self):
		self["input"].home()

	def keyEnd(self):
		self["input"].end()

	def keyBackspace(self):
		self["input"].deleteBackward()

	def keyTab(self):
		self["input"].tab()

	def keyInsert(self):
		self["input"].toggleOverwrite()

	def _showHelpWindow(self):
		from Screens.NumericalTextInputHelpDialog import NumericalTextInputHelpDialog
		if self._help_window is None:
			self._help_window = self.session.instantiateDialog(NumericalTextInputHelpDialog, self["input"], zPosition=5000)
			self._help_window.neverAnimate()
		self._help_window.show()
		self._onInputUpdate()

	def _closeHelpWindow(self):
		if self._help_window is not None:
			self.session.deleteDialog(self._help_window)
			self._help_window = None


class PinInput(InputBox):
	def __init__(self, session, service = "", triesEntry = None, pinList = [], *args, **kwargs):
		InputBox.__init__(self, session = session, text="    ", maxSize=True, type=Input.PIN, *args, **kwargs)
		
		self.waitTime = 15
		
		self.triesEntry = triesEntry
		
		self.pinList = pinList
		self["service"] = Label(service)
		
		if self.getTries() == 0:
			if (self.triesEntry.time.value + (self.waitTime * 60)) > time():
				remaining = (self.triesEntry.time.value + (self.waitTime * 60)) - time()
				remainingMinutes = int(remaining // 60)
				remainingSeconds = int(remaining % 60)
				self.onFirstExecBegin.append(boundFunction(self.session.openWithCallback, self.closePinCancel, MessageBox, _("You have to wait %s!") % (str(remainingMinutes) + " " + _("minutes") + ", " + str(remainingSeconds) + " " + _("seconds")), MessageBox.TYPE_ERROR))
			else:
				self.setTries(3)

		self["tries"] = Label("")
		self.onShown.append(self.showTries)

	def _showHelpWindow(self):
		pass

	def _closeHelpWindow(self):
		pass

	def gotAsciiCode(self):
		if self["input"].currPos == len(self["input"]) - 1:
			InputBox.gotAsciiCode(self)
			self.go()
		else:
			InputBox.gotAsciiCode(self)

	def keyNumberGlobal(self, number):
		if self["input"].currPos == len(self["input"]) - 1:
			InputBox.keyNumberGlobal(self, number)
			self.go()
		else:
			InputBox.keyNumberGlobal(self, number)
		
	def checkPin(self, pin):
		if pin is not None and pin.find(" ") == -1 and int(pin) in self.pinList:
			return True
		return False
		
	def go(self):
		self.triesEntry.time.value = int(time())
		self.triesEntry.time.save()
		if self.checkPin(self["input"].getText()):
			self.setTries(3)
			self.closePinCorrect()
		else:
			self.keyHome()
			self.decTries()
			if self.getTries() == 0:
				self.closePinWrong()
			else:
				pass
	
	def closePinWrong(self, *args):
		print("args:", args)
		self.close(False)
		
	def closePinCorrect(self, *args):
		self.close(True)
		
	def closePinCancel(self, *args):
		self.close(None)
			
	def cancel(self):
		self.closePinCancel()
		
	def getTries(self):
		return self.triesEntry.tries.value

	def decTries(self):
		self.setTries(self.triesEntry.tries.value - 1)
		self.showTries()
		
	def setTries(self, tries):
		self.triesEntry.tries.value = tries
		self.triesEntry.tries.save()
				
	def showTries(self):
		self["tries"].setText(_("Tries left:") + " " + str(self.getTries()))
