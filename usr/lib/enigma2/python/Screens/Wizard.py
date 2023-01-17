from __future__ import print_function
from __future__ import absolute_import
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.config import ConfigText, ConfigPassword, KEY_LEFT, KEY_RIGHT, KEY_0, KEY_DELETE, KEY_BACKSPACE, KEY_ASCII,\
	ConfigSelection, ConfigBoolean

from Components.Label import Label
from Components.Sources.StaticText import StaticText
from Components.Slider import Slider
from Components.ActionMap import NumberActionMap
from Components.ConfigList import ConfigList
from Components.Sources.List import List
from Components.config import config
from enigma import eTimer, eEnv

from Tools.BoundFunction import boundFunction
from Tools.Log import Log

from xml.sax import make_parser
from xml.sax.handler import ContentHandler

class WizardSummary(Screen):
	def __init__(self, session, parent):
		Screen.__init__(self, session, parent)
		self["text"] = StaticText("")
		self.onShow.append(self.setCallback)
		
	def setCallback(self):
		self.parent.setLCDTextCallback(self.setText)

	def setText(self, text):
		pass

	def setTitle(self, title):
		Log.i(title)
		self["text"].setText(title)

class Wizard(Screen):
	def createSummary(self):
			print("WizardCreateSummary")
			return WizardSummary

	class parseWizard(ContentHandler):
		def __init__(self, wizard, parentWizard = None):
			self.isPointsElement, self.isReboundsElement = 0, 0
			self.wizard = wizard
			self.parentWizard = parentWizard
			self.currContent = ""
			self.lastStep = 0	

		def startElement(self, name, attrs):
			#print "startElement", name
			self.currContent = name
			if (name == "step"):
				self.lastStep += 1
				if 'id' in attrs:
					id = str(attrs.get('id'))
				else:
					id = ""
				#print "id:", id
				if 'nextstep' in attrs:
					nextstep = str(attrs.get('nextstep'))
				else:
					nextstep = None
				if 'timeout' in attrs:
					timeout = int(attrs.get('timeout'))
				else:
					timeout = None
				if 'timeoutaction' in attrs:
					timeoutaction = str(attrs.get('timeoutaction'))
				else:
					timeoutaction = 'nextpage'

				if 'timeoutstep' in attrs:
					timeoutstep = str(attrs.get('timeoutstep'))
				else:
					timeoutstep = ''
				self.wizard[self.lastStep] = {"id": id, "condition": "", "text": "", "timeout": timeout, "timeoutaction": timeoutaction, "timeoutstep": timeoutstep, "list": [], "config": {"screen": None, "args": None, "type": "" }, "code": "", "codeafter": "", "code_async": "", "codeafter_async": "", "nextstep": nextstep}
				if 'laststep' in attrs:
					self.wizard[self.lastStep]["laststep"] = str(attrs.get('laststep'))
			elif (name == "text"):
				if "dynamictext" in attrs:
					self.wizard[self.lastStep]["dynamictext"] = str(attrs.get('dynamictext'))
				else:
					self.wizard[self.lastStep]["text"] = str(attrs.get('value')).replace("\\n", "\n")
			elif name == "displaytext" or name =="short_title":
				self.wizard[self.lastStep]["short_title"] = str(attrs.get('value')).replace("\\n", "\n")
			elif (name == "list"):
				if ('type' in attrs):
					if attrs["type"] == "dynamic":
						self.wizard[self.lastStep]["dynamiclist"] = attrs.get("source")
					if attrs["type"] == "config":
						self.wizard[self.lastStep]["configelement"] = attrs.get("configelement")
				if ("evaluation" in attrs):
					self.wizard[self.lastStep]["listevaluation"] = attrs.get("evaluation")
				if ("onselect" in attrs):
					self.wizard[self.lastStep]["onselect"] = attrs.get("onselect")
				if ('style' in attrs):
					self.wizard[self.lastStep]["liststyle"] = str(attrs.get('style'))
				if ('buildfunction' in attrs):
					self.wizard[self.lastStep]["listbuildfunction"] = str(attrs.get('buildfunction'))
			elif (name == "multicontentlist"):
				if ('type' in attrs):
					if attrs["type"] == "dynamic":
						self.wizard[self.lastStep]["dynamicmulticontentlist"] = attrs.get("setfunction")
				if ("onselect" in attrs):
					self.wizard[self.lastStep]["onselect"] = attrs.get("onselect")
				if ("evaluation" in attrs):
					self.wizard[self.lastStep]["evaluation"] = attrs.get("evaluation")
			elif (name == "listentry"):
				self.wizard[self.lastStep]["list"].append((str(attrs.get('caption')), str(attrs.get('step'))))
			elif (name == "config"):
				type = str(attrs.get('type'))
				self.wizard[self.lastStep]["config"]["type"] = type
				if type == "ConfigList" or type == "standalone":
					try:
						exec("from Screens." + str(attrs.get('module')) + " import *")
					except:
						exec("from " + str(attrs.get('module')) + " import *")
				
					self.wizard[self.lastStep]["config"]["screen"] = eval(str(attrs.get('screen')))
					if ('args' in attrs):
						#print "has args"
						self.wizard[self.lastStep]["config"]["args"] = str(attrs.get('args'))
				elif type == "dynamic":
					self.wizard[self.lastStep]["config"]["source"] = str(attrs.get('source'))
					if ('evaluation' in attrs):
						self.wizard[self.lastStep]["config"]["evaluation"] = str(attrs.get('evaluation'))
			elif (name == "code"):
				self.async_code = 'async' in attrs and str(attrs.get('async')) == "yes"
				if 'pos' in attrs and str(attrs.get('pos')) == "after":
					self.codeafter = True
				else:
					self.codeafter = False
			elif (name == "condition"):
				pass
			elif (name == "wizard"):
				if self.parentWizard is not None:
					if ('nextstepanimation' in attrs):
						self.parentWizard.setAnimation(self.parentWizard.NEXT_STEP_ANIMATION, str(attrs.get('nextstepanimation')))
					if ('previousstepanimation' in attrs):
						self.parentWizard.setAnimation(self.parentWizard.PREVIOUS_STEP_ANIMATION, str(attrs.get('previousstepanimation')))						

		def endElement(self, name):
			self.currContent = ""
			if name == 'code':
				if self.async_code:
					if self.codeafter:
						self.wizard[self.lastStep]["codeafter_async"] = self.wizard[self.lastStep]["codeafter_async"].strip()
					else:
						self.wizard[self.lastStep]["code_async"] = self.wizard[self.lastStep]["code_async"].strip()
				else:
					if self.codeafter:
						self.wizard[self.lastStep]["codeafter"] = self.wizard[self.lastStep]["codeafter"].strip()
					else:
						self.wizard[self.lastStep]["code"] = self.wizard[self.lastStep]["code"].strip()
			elif name == 'condition':
				self.wizard[self.lastStep]["condition"] = self.wizard[self.lastStep]["condition"].strip()
			elif name == 'step':
				#print "Step number", self.lastStep, ":", self.wizard[self.lastStep]
				pass
								
		def characters(self, ch):
			if self.currContent == "code":
				if self.async_code:
					if self.codeafter:
						self.wizard[self.lastStep]["codeafter_async"] = self.wizard[self.lastStep]["codeafter_async"] + ch
					else:
						self.wizard[self.lastStep]["code_async"] = self.wizard[self.lastStep]["code_async"] + ch
				else:
					if self.codeafter:
						self.wizard[self.lastStep]["codeafter"] = self.wizard[self.lastStep]["codeafter"] + ch
					else:
						self.wizard[self.lastStep]["code"] = self.wizard[self.lastStep]["code"] + ch
			elif self.currContent == "condition":
				 self.wizard[self.lastStep]["condition"] = self.wizard[self.lastStep]["condition"] + ch
	
	def __init__(self, session, showSteps = True, showStepSlider = True, showList = True, showConfig = True, showMulticontentList = False):
		Screen.__init__(self, session)
		
		self.isLastWizard = False # can be used to skip a "goodbye"-screen in a wizard

		self.stepHistory = []
		self.__nextStepAnimation = Wizard.NEXT_STEP_ANIMATION_KEY
		self.__previousStepAnimation = Wizard.PREVIOUS_STEP_ANIMATION_KEY

		self.wizard = {}
		parser = make_parser()
		if not isinstance(self.xmlfile, list):
			self.xmlfile = [self.xmlfile]
		print("Reading ", self.xmlfile)
		wizardHandler = self.parseWizard(self.wizard, self)
		parser.setContentHandler(wizardHandler)
		for xmlfile in self.xmlfile:
			if xmlfile[0] != '/':
				parser.parse(eEnv.resolve('${datadir}/enigma2/') + xmlfile)
			else:
				parser.parse(xmlfile)

		self.showSteps = showSteps
		self.showStepSlider = showStepSlider
		self.showList = showList
		self.showConfig = showConfig
		self.showMulticontentList = showMulticontentList

		self.numSteps = len(self.wizard)
		self.currStep = self.getStepWithID("start") + 1
		
		self.timeoutTimer = eTimer()
		self.timeoutTimer_conn = self.timeoutTimer.timeout.connect(self.timeoutCounterFired)

		self["text"] = Label()

		if showConfig:
			self["config"] = ConfigList([], session = session)
		self["configEntry"] = StaticText("")
		self["configValue"] = StaticText("")

		if self.showSteps:
			self["step"] = Label()
		
		if self.showStepSlider:
			self["stepslider"] = Slider(1, self.numSteps)
		
		if self.showMulticontentList:
			self.multicontentlist = []
			self["multicontentlist"] = List(self.multicontentlist)
			self["multicontentlist"].onSelectionChanged.append(self.selChanged)

		if self.showList:
			self.list = []
			self["list"] = List(self.list, enableWrapAround = True)
			self["list"].onSelectionChanged.append(self.selChanged)
			#self["list"] = MenuList(self.list, enableWrapAround = True)

		self.onShown.append(self.updateValues)
		self.onShow.append(self._setTitle)

		self.configInstance = None
		self.currentConfigIndex = None
		
		self.lcdCallbacks = []
		
		self.disableKeys = False
		
		self["actions"] = NumberActionMap(["WizardActions", "NumberActions", "ColorActions", "SetupActions", "InputAsciiActions", "KeyboardInputActions"],
		{
			"gotAsciiCode": self.keyGotAscii,
			"ok": self.ok,
			"back": self.back,
			"left": self.left,
			"right": self.right,
			"up": self.up,
			"down": self.down,
			"red": self.red,
			"green": self.green,
			"yellow": self.yellow,
			"blue":self.blue,
			"deleteBackward": self.deleteBackward,
			"deleteForward": self.deleteForward,
			"video": self.setNoAnimations,
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

		self.__title = None

		self["VirtualKB"] = NumberActionMap(["VirtualKeyboardActions"],
		{
			"showVirtualKeyboard": self.KeyText,
		}, -2)
		
		self["VirtualKB"].setEnabled(False)
		
		self.onHideFinished.append(self.__hideFinished)
		self.onFirstExecBegin.append(self._initAnimation)

	def close(self, *retval):
		self.onHideFinished.remove(self.__hideFinished)
		Screen.close(self, *retval)

	def _setTitle(self):
		if self.__title:
			self.setTitle(self.__title.replace("\n", " - "))
			self.summaries.setTitle(self.__title)

	NEXT_STEP_ANIMATION = 0
	PREVIOUS_STEP_ANIMATION = 1
	NEXT_STEP_ANIMATION_KEY = "wizard_next"
	PREVIOUS_STEP_ANIMATION_KEY = "wizard_previous"
	def setAnimation(self, type, animation):
		if type == self.NEXT_STEP_ANIMATION:
			self.__nextStepAnimation = animation
		elif type == self.PREVIOUS_STEP_ANIMATION:
			self.__previousStepAnimation = animation

	def setNoAnimations(self):
		key = ""
		Wizard.NEXT_STEP_ANIMATION_KEY = key
		Wizard.PREVIOUS_STEP_ANIMATION_KEY = key
		self.setAnimation(self.NEXT_STEP_ANIMATION, key)
		self.setAnimation(self.PREVIOUS_STEP_ANIMATION, key)

	def _initAnimation(self):
		import Screens.AnimationSetup # needed to initialize config.osd.window_animation_default
		if config.osd.window_animation_default.value == "_-disabled-_":
			from enigma import eWindowAnimationManager
			eWindowAnimationManager.setDefault() #disable animations after wizard
			self.setNoAnimations() #disable animations in wizard
		self.setShowHideAnimation(self.__nextStepAnimation)

	def openScreen(self, *args, **kwargs):
		self.onHideFinished.remove(self.__hideFinished)
		self.session.openWithCallback(self.__foreignScreenInstanceFinished, *args, **kwargs)

	def red(self):
		print("red")
		pass

	def green(self):
		print("green")
		pass
	
	def yellow(self):
		print("yellow")
		pass
	
	def blue(self):
		print("blue")
		pass

	def deleteForward(self):
		self.resetCounter()
		if (self.wizard[self.currStep]["config"]["screen"] != None):
			self.configInstance.keyDelete()
		elif (self.wizard[self.currStep]["config"]["type"] == "dynamic"):
			self["config"].handleKey(KEY_DELETE)
		print("deleteForward")

	def deleteBackward(self):
		self.resetCounter()
		if (self.wizard[self.currStep]["config"]["screen"] != None):
			self.configInstance.keyBackspace()
		elif (self.wizard[self.currStep]["config"]["type"] == "dynamic"):
			self["config"].handleKey(KEY_BACKSPACE)
		print("deleteBackward")
	
	def setLCDTextCallback(self, callback):
		self.lcdCallbacks.append(callback)

	def back(self):
		self.instance.setShowHideAnimation(self.__previousStepAnimation)
		if self.disableKeys:
			return
		print("getting back...")
		print("stepHistory:", self.stepHistory)
		if len(self.stepHistory) > 1:
			self.currStep = self.stepHistory[-2]
			self.stepHistory = self.stepHistory[:-2]
			self.hide()
			self.updateValues()
		else:
			self.session.openWithCallback(self.exitWizardQuestion, MessageBox, (_("Are you sure you want to exit this wizard?") ) )
		if self.currStep < 1:
			self.currStep = 1
		print("currStep:", self.currStep)
		print("new stepHistory:", self.stepHistory)
		print("after updateValues stepHistory:", self.stepHistory)
		
	def exitWizardQuestion(self, ret = False):
		if (ret):
			self.markDone()
			self.close()
		
	def markDone(self):
		pass
	
	def getStepWithID(self, id):
		print("getStepWithID:", id)
		count = 0
		for x in self.wizard.keys():
			if self.wizard[x]["id"] == id:
				print("result:", count)
				return count
			count += 1
		print("result: nothing")
		return 0

	def isCurrentStepID(self, id):
		return self.currStep == self.getStepWithID(id) + 1

	def finished(self, gotoStep = None, *args, **kwargs):
		self.hide()

		print("finished")
		currStep = self.currStep

		if self.updateValues not in self.onShown:
			self.onShown.append(self.updateValues)
			
		if self.showConfig:
			if self.wizard[currStep]["config"]["type"] == "dynamic":
				eval("self." + self.wizard[currStep]["config"]["evaluation"])()

		if self.showList:
			if (len(self.wizard[currStep].get("evaluatedlist", [])) > 0):
				print("current:", self["list"].current)
				nextStep = self["list"].current[1]
				if ("listevaluation" in self.wizard[currStep]):
					exec("self." + self.wizard[self.currStep]["listevaluation"] + "('" + nextStep + "')")
				elif ("configelement" in self.wizard[currStep]):
						configelement = self.wizard[currStep]["configelement"]
						element = eval(configelement)
						element.value = self["list"].current[1]
						element.save()
				else:
					self.currStep = self.getStepWithID(nextStep)

		if self.showMulticontentList:
			if (len(self.wizard[currStep].get("evaluatedmulticontentlist", [])) > 0):
				if ("evaluation" in self.wizard[currStep]):
					exec("self." + self.wizard[self.currStep]["evaluation"] + "('" + self["multicontentlist"].current[0] + "')")

		print_now = True
		if ((currStep == self.numSteps and self.wizard[currStep]["nextstep"] is None) or self.wizard[currStep]["id"] == "end"): # wizard finished
			print("wizard finished")
			self.markDone()
			self.close()
		else:
			self.codeafter = True
			self.runCode(self.wizard[currStep]["codeafter"])
			self.prevStep = currStep
			self.gotoStep = gotoStep
			if not self.runCode(self.wizard[currStep]["codeafter_async"]):
				self.afterAsyncCode()
			else:
				if self.updateValues in self.onShown:
					self.onShown.remove(self.updateValues)

		if print_now:
			print("Now: " + str(self.currStep))

	def __hideFinished(self):
		self.show()

	def ok(self):
		print("OK")
		self.instance.setShowHideAnimation(self.__nextStepAnimation)
		if self.disableKeys:
			return
		currStep = self.currStep
		
		if self.showConfig:
			if (self.wizard[currStep]["config"]["screen"] != None):
				# TODO: don't die, if no run() is available
				# there was a try/except here, but i can't see a reason
				# for this. If there is one, please do a more specific check
				# and/or a comment in which situation there is no run()
				if callable(getattr(self.configInstance, "runAsync", None)):
					self._foreignScreenInstancePrepare()
					self.configInstance.runAsync(self.__foreignScreenInstanceFinished)
					return
				else:
					self.configInstance.run()
		self.finished()

	def _foreignScreenInstancePrepare(self):
		if self.updateValues in self.onShown:
			self.onShown.remove(self.updateValues)
		# we need to remove the callback so it doesn't show the wizard screen after hiding it. the onHideFinished is
		# fired glpbally, not just for our own Screen
		if self.__hideFinished in self.onHideFinished:
			self.onHideFinished.remove(self.__hideFinished)

	def _foreignScreenInstanceFinished(self, *args, **kwargs):
		self.__foreignScreenInstanceFinished()

	def __foreignScreenInstanceFinished(self, *args, **kwargs):
		# re-register the callback for the next wizard steps
		self.onHideFinished.append(self.__hideFinished)

		# we need to show the wizard Screen again. we don't call show() to prevent future features in __hideFinished()
		self.__hideFinished()
		self.finished()

	def keyNumberGlobal(self, number):
		if (self.wizard[self.currStep]["config"]["screen"] != None):
			self.configInstance.keyNumberGlobal(number)
		elif (self.wizard[self.currStep]["config"]["type"] == "dynamic"):
			self["config"].handleKey(KEY_0 + number)

	def keyGotAscii(self):
		if (self.wizard[self.currStep]["config"]["screen"] != None):
			self["config"].handleKey(KEY_ASCII)
		elif (self.wizard[self.currStep]["config"]["type"] == "dynamic"):
			self["config"].handleKey(KEY_ASCII)

	def left(self):
		self.resetCounter()
		if (self.wizard[self.currStep]["config"]["screen"] != None):
			self.configInstance.keyLeft()
		elif (self.wizard[self.currStep]["config"]["type"] == "dynamic"):
			self["config"].handleKey(KEY_LEFT)
		print("left")

	def right(self):
		self.resetCounter()
		if (self.wizard[self.currStep]["config"]["screen"] != None):
			self.configInstance.keyRight()
		elif (self.wizard[self.currStep]["config"]["type"] == "dynamic"):
			self["config"].handleKey(KEY_RIGHT)	
		print("right")

	def up(self):
		self.resetCounter()
		if (self.showConfig and self.wizard[self.currStep]["config"]["screen"] != None  or self.wizard[self.currStep]["config"]["type"] == "dynamic"):
			self["config"].instance.moveSelection(self["config"].instance.moveUp)
			self.handleInputHelpers()
		elif (self.showList and len(self.wizard[self.currStep]["evaluatedlist"]) > 0):
			self["list"].selectPrevious()
			if "onselect" in self.wizard[self.currStep]:
				print("current:", self["list"].current)
				self.selection = self["list"].current[-1]
				#self.selection = self.wizard[self.currStep]["evaluatedlist"][self["list"].l.getCurrentSelectionIndex()][1]
				exec("self." + self.wizard[self.currStep]["onselect"] + "()")
		elif (self.showMulticontentList and len(self.wizard[self.currStep]["evaluatedmulticontentlist"]) > 0):
			self["multicontentlist"].selectPrevious()
			if "onselect" in self.wizard[self.currStep]:
				self.selection = self["multicontentlist"].current
				exec("self." + self.wizard[self.currStep]["onselect"] + "()")
		print("up")

	def down(self):
		self.resetCounter()
		if (self.showConfig and self.wizard[self.currStep]["config"]["screen"] != None  or self.wizard[self.currStep]["config"]["type"] == "dynamic"):
			self["config"].instance.moveSelection(self["config"].instance.moveDown)
			self.handleInputHelpers()
		elif (self.showList and len(self.wizard[self.currStep]["evaluatedlist"]) > 0):
			#self["list"].instance.moveSelection(self["list"].instance.moveDown)
			self["list"].selectNext()
			if "onselect" in self.wizard[self.currStep]:
				print("current:", self["list"].current)
				#self.selection = self.wizard[self.currStep]["evaluatedlist"][self["list"].l.getCurrentSelectionIndex()][1]
				#exec("self." + self.wizard[self.currStep]["onselect"] + "()")
				self.selection = self["list"].current[-1]
				#self.selection = self.wizard[self.currStep]["evaluatedlist"][self["list"].l.getCurrentSelectionIndex()][1]
				exec("self." + self.wizard[self.currStep]["onselect"] + "()")
		elif (self.showMulticontentList and len(self.wizard[self.currStep]["evaluatedmulticontentlist"]) > 0):
			self["multicontentlist"].selectNext()
			if "onselect" in self.wizard[self.currStep]:
				self.selection = self["multicontentlist"].current
				exec("self." + self.wizard[self.currStep]["onselect"] + "()")
		print("down")

	def selChanged(self):
		self.resetCounter()
		if (self.showConfig and self.wizard[self.currStep]["config"]["screen"] != None):
			self["config"].instance.moveSelection(self["config"].instance.moveUp)
		elif (self.showList and len(self.wizard[self.currStep].get("evaluatedlist", [])) > 0):
			if "onselect" in self.wizard[self.currStep]:
				self.selection = self["list"].current[-1]
				print("self.selection:", self.selection)
				exec("self." + self.wizard[self.currStep]["onselect"] + "()")

	def resetCounter(self):
		self.timeoutCounter = self.wizard[self.currStep]["timeout"]
		
	def runCode(self, code):
		if code != "":
			print("code", code)
			exec(code)
			return True
		return False

	def getTranslation(self, text):
		return _(text)
			
	def updateText(self, firstset = False):
		if "dynamictext" in self.wizard[self.currStep]:
			text = eval("self." + self.wizard[self.currStep]["dynamictext"] + "(\"" + self.wizard[self.currStep]["id"] + "\")")
		else:
			text = self.wizard[self.currStep]["text"]
		text = self.getTranslation(text)
		if text.find("[timeout]") != -1:
			text = text.replace("[timeout]", str(self.timeoutCounter))
			self["text"].setText(text)
		else:
			if firstset:
				self["text"].setText(text)

	def updateValues(self):
		print("Updating values in step " + str(self.currStep))
		# calling a step which doesn't exist can only happen if the condition in the last step is not fulfilled
		# if a non-existing step is called, end the wizard 
		if self.currStep > len(self.wizard):
			self.markDone()
			self.close()
			return

		self.timeoutTimer.stop()
		if self.configInstance is not None:
			# remove callbacks
			self.configInstance["config"].onSelectionChanged = []
			del self.configInstance["config"]
			self.session.deleteDialog(self.configInstance)
			self.configInstance = None

		self.condition = True
		exec (self.wizard[self.currStep]["condition"])
		if not self.condition:
			print("keys*******************:", list(self.wizard[self.currStep].keys()))
			if "laststep" in self.wizard[self.currStep]: # exit wizard, if condition of laststep doesn't hold
				self.markDone()
				self.close()
				return
			else:
				self.currStep += 1
				self.updateValues()
		else:
			if len(self.stepHistory) == 0 or self.stepHistory[-1] != self.currStep:
				self.stepHistory.append(self.currStep)
			print("wizard step:", self.wizard[self.currStep])
			
			if self.showSteps:
				self["step"].setText(self.getTranslation("Step ") + str(self.currStep) + "/" + str(self.numSteps))
			if self.showStepSlider:
				self["stepslider"].setValue(self.currStep)
		
			if self.wizard[self.currStep]["timeout"] is not None:
				self.resetCounter() 
				self.timeoutTimer.start(1000)
			
			print("wizard text", self.getTranslation(self.wizard[self.currStep]["text"]))
			self.updateText(firstset = True)
			if "short_title" in self.wizard[self.currStep]:
				short_title = _(self.wizard[self.currStep]["short_title"])
				print("set Title")
				self.__title = short_title

			self.codeafter=False
			self.runCode(self.wizard[self.currStep]["code"])
			if self.runCode(self.wizard[self.currStep]["code_async"]):
				if self.updateValues in self.onShown:
					self.onShown.remove(self.updateValues)
			else:
				self.afterAsyncCode()

	def showHideList(self, name, show = True):
		for renderer in self.renderer:
			rootrenderer = renderer
			while renderer.source is not None:
				if renderer.source is self[name]:
					if show:
						rootrenderer.instance.setZPosition(1)
						rootrenderer.instance.show()
					else:
						rootrenderer.instance.setZPosition(0)
						rootrenderer.instance.hide()

				renderer = renderer.source

	def defaultBuildFunction(self, *args, **kwargs):
		return args

	def afterAsyncCode(self):
		if not self.updateValues in self.onShown:
			self.onShown.append(self.updateValues)

		if self.codeafter:
			if self.wizard[self.prevStep]["nextstep"] is not None:
				self.currStep = self.getStepWithID(self.wizard[self.prevStep]["nextstep"])
			if self.gotoStep is not None:
				self.currStep = self.getStepWithID(self.gotoStep)
			self.currStep += 1
			self.updateValues()
			print("Now: " + str(self.currStep))
		else:
			if self.showList:
				print("showing list,", self.currStep)
				index = 0
				self.showHideList("list", show = True)
				liststyle = "default"
				listbuildfunc = None

				self.list = []
				if ("dynamiclist" in self.wizard[self.currStep]):
					dynamiclist = self.wizard[self.currStep]["dynamiclist"]
					print("dynamic list, calling", dynamiclist)
					newlist = eval("self." + self.wizard[self.currStep]["dynamiclist"] + "()")
					if ("liststyle" in self.wizard[self.currStep]):
						liststyle = self.wizard[self.currStep]["liststyle"]

					if ("listbuildfunction" in self.wizard[self.currStep]):
						listbuildfunc = eval("self." + self.wizard[self.currStep]["listbuildfunction"])

					for entry in newlist:
						self.list.append(entry)

				if ("configelement" in self.wizard[self.currStep]):
					configelement = self.wizard[self.currStep]["configelement"]
					print("configelement:", configelement)
					element = eval(configelement)
					
					if isinstance(element, ConfigSelection):
						for choice in element.choices.choices:
							print("choice:", choice)
							self.list.append((choice[1], choice[0]))
						index = element.getIndex()
					elif isinstance(element, ConfigBoolean):
						self.list.append((_(element.descriptions[True]), True))
						self.list.append((_(element.descriptions[False]), False))
						index = 1
						if element.value:
							index = 0
				if (len(self.wizard[self.currStep]["list"]) > 0):
					for x in self.wizard[self.currStep]["list"]:
						self.list.append((self.getTranslation(x[0]), x[1]))
				self.wizard[self.currStep]["evaluatedlist"] = self.list
				self["list"].setStyle(liststyle)
				self["list"].buildfunc = listbuildfunc
				self["list"].list = self.list
				self["list"].index = index
				if not self.list:
					self.showHideList("list", show = False)
				
			if self.showMulticontentList:
				print("showing multi content list")
				self.multicontentlist = []
				if ("dynamicmulticontentlist" in self.wizard[self.currStep]):
					self.showHideList("multicontentlist", show = True)
					dynamiclist = self.wizard[self.currStep]["dynamicmulticontentlist"]
					exec("self." + self.wizard[self.currStep]["dynamicmulticontentlist"] + "()")
				else:
					self.showHideList("multicontentlist", show = False)
				self.wizard[self.currStep]["evaluatedmulticontentlist"] = self.multicontentlist

			if self.showConfig:
				print("showing config")
# 				self["config"].instance.setZPosition(1)
				if self.wizard[self.currStep]["config"]["type"] == "dynamic":
						print("config type is dynamic")
						self["config"].instance.setZPosition(2)
						self["config"].l.setList(eval("self." + self.wizard[self.currStep]["config"]["source"])())
						if not self._configSelChanged in self["config"].onSelectionChanged:
							self["config"].onSelectionChanged.append(self._configSelChanged)
				elif (self.wizard[self.currStep]["config"]["screen"] != None):
					if self.wizard[self.currStep]["config"]["type"] == "standalone":
						print("Type is standalone")
						self.session.openWithCallback(self.ok, self.wizard[self.currStep]["config"]["screen"])
					else:
						self["config"].instance.setZPosition(2)
						print("wizard screen", self.wizard[self.currStep]["config"]["screen"])
						if self.wizard[self.currStep]["config"]["args"] == None:
							self.configInstance = self.session.instantiateDialog(self.wizard[self.currStep]["config"]["screen"])
						else:
							self.configInstance = self.session.instantiateDialog(self.wizard[self.currStep]["config"]["screen"], eval(self.wizard[self.currStep]["config"]["args"]))
						self["config"].l.setList(self.configInstance["config"].list)
						callbacks = self.configInstance["config"].onSelectionChanged
						self.configInstance["config"].destroy()
						print("clearConfigList", self.configInstance["config"], self["config"])
						self.configInstance["config"] = self["config"]
						if not self._configSelChanged in callbacks:
							callbacks.append(self._configSelChanged)
						self.configInstance["config"].onSelectionChanged = callbacks
						print("clearConfigList", self.configInstance["config"], self["config"])
				else:
					self["config"].l.setList([])
					self.handleInputHelpers()
			else:
				if "config" in self:
					self["config"].hide()
			self._configSelChanged()

	def timeoutCounterFired(self):
		self.timeoutCounter -= 1
		print("timeoutCounter:", self.timeoutCounter)
		if self.timeoutCounter == 0:
			if self.wizard[self.currStep]["timeoutaction"] == "selectnext":
				print("selection next item")
				self.down()
			else:
				if self.wizard[self.currStep]["timeoutaction"] == "changestep":
					self.finished(gotoStep = self.wizard[self.currStep]["timeoutstep"])
		self.updateText()

	def _getCurrentConfigEntry(self):
		current = self["config"].getCurrent()
		return current and current[0] or ""

	def _getCurrentConfigValue(self):
		current = self["config"].getCurrent()
		return current and str(current[1].getText()) or ""

	def _configSelChanged(self):
		if self.showConfig and self["config"].getCurrent() is not None:
			self["configEntry"].text = _(self._getCurrentConfigEntry())
			self["configValue"].text = _(self._getCurrentConfigValue())
		else:
			self["configEntry"].text = ""
			self["configValue"].text = ""

	def handleInputHelpers(self):
		if self["config"].getCurrent() is not None:
			if isinstance(self["config"].getCurrent()[1], ConfigText) or isinstance(self["config"].getCurrent()[1], ConfigPassword):
				if "VKeyIcon" in self:
					self["VirtualKB"].setEnabled(True)
					self["VKeyIcon"].boolean = True
				if "HelpWindow" in self:
					if self["config"].getCurrent()[1].help_window.instance is not None:
						helpwindowpos = self["HelpWindow"].getPosition()
						from enigma import ePoint
						self["config"].getCurrent()[1].help_window.instance.move(ePoint(helpwindowpos[0],helpwindowpos[1]))
			else:
				if "VKeyIcon" in self:
					self["VirtualKB"].setEnabled(False)
					self["VKeyIcon"].boolean = False
		else:
			if "VKeyIcon" in self:
				self["VirtualKB"].setEnabled(False)
				self["VKeyIcon"].boolean = False

	def KeyText(self):
		from Screens.VirtualKeyBoard import VirtualKeyBoard
		self.currentConfigIndex = self["config"].getCurrentIndex()
		self.session.openWithCallback(self.VirtualKeyBoardCallback, VirtualKeyBoard, title = self["config"].getCurrent()[0], text = self["config"].getCurrent()[1].getValue())

	def VirtualKeyBoardCallback(self, callback = None):
		if callback is not None and len(callback):
			if isinstance(self["config"].getCurrent()[1], ConfigText) or isinstance(self["config"].getCurrent()[1], ConfigPassword):
				if "HelpWindow" in self:
					if self["config"].getCurrent()[1].help_window.instance is not None:
						helpwindowpos = self["HelpWindow"].getPosition()
						from enigma import ePoint
						self["config"].getCurrent()[1].help_window.instance.move(ePoint(helpwindowpos[0],helpwindowpos[1]))
			self["config"].instance.moveSelectionTo(self.currentConfigIndex)
			self["config"].setCurrentIndex(self.currentConfigIndex)
			self["config"].getCurrent()[1].setValue(callback)
			self["config"].invalidate(self["config"].getCurrent())

class WizardManager:
	def __init__(self):
		self.wizards = []
	
	def registerWizard(self, wizard, precondition, priority = 0):
		self.wizards.append((wizard, precondition, priority))
	
	def getWizards(self):
		# x[1] is precondition
		for wizard in self.wizards:
			wizard[0].isLastWizard = False
		if len(self.wizards) > 0:
			self.wizards[-1][0].isLastWizard = True
		return [(x[2], x[0]) for x in self.wizards if x[1] == 1]

wizardManager = WizardManager()
