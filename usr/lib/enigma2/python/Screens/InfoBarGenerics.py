from __future__ import division
from __future__ import print_function
from __future__ import absolute_import
from Screens.ChannelSelection import ChannelSelection, BouquetSelector, SilentBouquetSelector

from Components.ActionMap import ActionMap, HelpableActionMap
from Components.ActionMap import NumberActionMap
from Components.Harddisk import harddiskmanager
from Components.Input import Input
from Components.Label import Label
from Components.PluginComponent import plugins
from Components.ServiceEventTracker import ServiceEventTracker
from Components.Sources.Boolean import Boolean
from Tools.Log import Log
from six.moves import range

try:
	from Components.Sources.HbbtvApplication import HbbtvApplication
	haveHbbtvApplication = True
except:
	haveHbbtvApplication = False
from Components.config import config, ConfigBoolean, ConfigClock
from Components.SystemInfo import SystemInfo
from Components.UsageConfig import preferredInstantRecordPath, defaultMoviePath, defaultStorageDevice
from Screens.EpgSelection import EPGSelection, OutdatedEPGSelection
from Plugins.Plugin import PluginDescriptor

from Screens.Screen import Screen
from Screens.ChoiceBox import ChoiceBox
from Screens.Dish import Dish
from Screens.EventView import EventViewEPGSelect, EventViewSimple
from Screens.InputBox import InputBox
from Screens.MessageBox import MessageBox
from Screens.MinuteInput import MinuteInput
from Screens.TimerSelection import TimerSelection
from Screens.PictureInPicture import PictureInPicture
from Screens.SubtitleDisplay import SubtitleDisplay
from Screens.RdsDisplay import RdsInfoDisplay
from Screens.TimeDateInput import TimeDateInput
from Screens.UnhandledKey import UnhandledKey
from ServiceReference import ServiceReference

from Tools import Notifications
from Tools.Directories import fileExists

from enigma import eTimer, eServiceCenter, eDVBServicePMTHandler, iServiceInformation, \
	iPlayableService, eServiceReference, eEPGCache, eActionMap, eServiceMP3, eSize

from time import time, localtime, strftime
from bisect import insort

from RecordTimer import RecordTimerEntry
import Screens.Standby

# hack alert!
from Screens.Menu import MainMenu, mdom

class InfoBarDish:
	def __init__(self):
		self.dishDialog = self.session.instantiateDialog(Dish,zPosition=10000)
		self.dishDialog.neverAnimate()

class InfoBarUnhandledKey:
	def __init__(self):
		self.unhandledKeyDialog = self.session.instantiateDialog(UnhandledKey,zPosition=10000)
		self.unhandledKeyDialog.neverAnimate()

		self.hideUnhandledKeySymbolTimer = eTimer()
		self.hideUnhandledKeySymbolTimer_conn = self.hideUnhandledKeySymbolTimer.timeout.connect(self.unhandledKeyDialog.hide)
		self.checkUnusedTimer = eTimer()
		self.checkUnusedTimer_conn = self.checkUnusedTimer.timeout.connect(self.checkUnused)
		self.onLayoutFinish.append(self.unhandledKeyDialog.hide)
		self.actionASlot = eActionMap.getInstance().bindAction('', -0x7FFFFFFF, self.actionA) #highest prio
		self.actionBSlot = eActionMap.getInstance().bindAction('', 0x7FFFFFFF, self.actionB) #lowest prio
		self.flags = (1<<1);
		self.uflags = 0;

	#this function is called on every keypress!
	def actionA(self, key, flag):
		if flag != 4:
			if self.flags & (1<<1):
				self.flags = self.uflags = 0
			self.flags |= (1<<flag)
			if flag == 1: # break
				self.checkUnusedTimer.start(0, True)
		return 0

	#this function is only called when no other action has handled this key
	def actionB(self, key, flag):
		if flag != 4:
			self.uflags |= (1<<flag)
		return 1

	def checkUnused(self):
		if self.flags == self.uflags:
			self.unhandledKeyDialog.show()
			self.hideUnhandledKeySymbolTimer.start(2000, True)

class InfoBarAutoSleepTimer:
	def __init__(self):
		self.inactivityTimer = eTimer()
		self.inactivityTimer_conn = self.inactivityTimer.timeout.connect(self.inactive)
		self.keypress(None, 1)
		self.highPrioActionSlot = eActionMap.getInstance().bindAction('', -0x7FFFFFFF, self.keypress) #highest prio
		if not config.usage.inactivity_shutdown_initialized.value:
			choicelist = [ (x[1],x[0]) for x in config.usage.inactivity_shutdown.getChoices() ] #we actually need to switch key/value for the choicebox
			Notifications.AddNotificationWithCallback(
				self._initialAutoSleepValueSet,
				ChoiceBox,
				list = choicelist,
				selection=3,
				title=_("Please specify the amount of time the device has to be inactive (e.g. no button pressed) before shutting down automatically"),
				titlebartext=_("Inactivity shutdown"))

	def _initialAutoSleepValueSet(self, answer):
		config.usage.inactivity_shutdown_initialized.value = True
		config.usage.inactivity_shutdown_initialized.save()
		if answer != None:
			config.usage.inactivity_shutdown.value = answer[1]
			config.usage.inactivity_shutdown.save()

	#this function is called on every keypress!
	def keypress(self, key, flag):
		if flag == 1: # break code
			hours = config.usage.inactivity_shutdown.value
			if hours != "never":
				self.inactivityTimer.startLongTimer(int(hours)*60*60)
			else:
				self.inactivityTimer.stop()
		return 0

	def inactive(self):
		print("[InfoBarAutoSleepTimer].inactive")
		if Screens.Standby.inStandby == None:
			self.session.openWithCallback(self.shutdown, MessageBox, _("The device will shutdown due to inactivity.\nDo you want to abort the shutdown?"), MessageBox.TYPE_YESNO, timeout=120, default=False, title=_("Inactivity shutdown"))
		else:
			self.shutdown(False)
			return

	def shutdown(self, aborted):
		print("[InfoBarAutoSleepTimer].shutdown")
		if aborted or Screens.Standby.inTryQuitMainloop:
			print("aborted")
			self.keypress(None, 1) #restart the timer
			return

		if Screens.Standby.inStandby != None:
			print("RecordTimer.TryQuitMainloop")
			RecordTimerEntry.TryQuitMainloop(True)
		else:
			print("Screens.Standby.TryQuitMainloop")
			self.session.open(Screens.Standby.TryQuitMainloop, 1)

class InfoBarShowHide:
	""" InfoBar show/hide control, accepts toggleShow and hide actions, might start
	fancy animations. """
	STATE_HIDDEN = 0
	STATE_HIDING = 1
	STATE_SHOWING = 2
	STATE_SHOWN = 3

	def __init__(self):
		self["ShowHideActions"] = ActionMap( ["InfobarShowHideActions"] ,
			{
				"toggleShow": self.toggleShow,
				"hide": self.hide,
			}, 1) # lower prio to make it possible to override ok and cancel..

		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evStart: self.serviceStarted,
			})

		self.__state = self.STATE_SHOWN
		self.__locked = 0

		self.hideTimer = eTimer()
		self.hideTimer_conn = self.hideTimer.timeout.connect(self.doTimerHide)
		self.hideTimer.start(5000, True)

		self.onShow.append(self.__onShow)
		self.onHide.append(self.__onHide)

	def serviceStarted(self):
		if self.execing:
			if config.usage.show_infobar_on_zap.value:
				self.doShow()

	def __onShow(self):
		self.__state = self.STATE_SHOWN
		self.startHideTimer()

	def startHideTimer(self):
		if self.__state == self.STATE_SHOWN and not self.__locked:
			idx = config.usage.infobar_timeout.index
			if idx:
				self.hideTimer.start(idx*1000, True)

	def __onHide(self):
		self.__state = self.STATE_HIDDEN

	def doShow(self):
		self.show()
		self.startHideTimer()

	def doTimerHide(self):
		self.hideTimer.stop()
		if self.__state == self.STATE_SHOWN:
			self.hide()

	def toggleShow(self):
		if self.__state == self.STATE_SHOWN:
			self.hide()
			self.hideTimer.stop()
		elif self.__state == self.STATE_HIDDEN:
			self.show()

	def lockShow(self):
		self.__locked = self.__locked + 1
		if self.execing:
			self.show()
			self.hideTimer.stop()

	def unlockShow(self):
		self.__locked = self.__locked - 1
		if self.execing:
			self.startHideTimer()

#	def startShow(self):
#		self.instance.m_animation.startMoveAnimation(ePoint(0, 600), ePoint(0, 380), 100)
#		self.__state = self.STATE_SHOWN
#
#	def startHide(self):
#		self.instance.m_animation.startMoveAnimation(ePoint(0, 380), ePoint(0, 600), 100)
#		self.__state = self.STATE_HIDDEN

class NumberZap(Screen):
	def quit(self):
		self.Timer.stop()
		self.close(0)

	def keyOK(self):
		self.Timer.stop()
		self.close(int(self["number"].getText()))

	def keyNumberGlobal(self, number):
		self.Timer.start(3000, True)		#reset timer
		self.field = self.field + str(number)
		self["number"].setText(self.field)
		if len(self.field) >= 4:
			self.keyOK()

	def __init__(self, session, number):
		Screen.__init__(self, session)
		self.field = str(number)

		self["channel"] = Label(_("Channel:"))

		self["number"] = Label(self.field)

		self["actions"] = NumberActionMap( [ "SetupActions" ],
			{
				"cancel": self.quit,
				"ok": self.keyOK,
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
			})

		self.Timer = eTimer()
		self.Timer_conn = self.Timer.timeout.connect(self.keyOK)
		self.Timer.start(3000, True)

class InfoBarNumberZap:
	""" Handles an initial number for NumberZapping """
	def __init__(self):
		self["NumberActions"] = NumberActionMap( [ "NumberActions"],
			{
				"1": self.keyNumberGlobal,
				"2": self.keyNumberGlobal,
				"3": self.keyNumberGlobal,
				"4": self.keyNumberGlobal,
				"5": self.keyNumberGlobal,
				"6": self.keyNumberGlobal,
				"7": self.keyNumberGlobal,
				"8": self.keyNumberGlobal,
				"9": self.keyNumberGlobal,
				"0": self.keyNumberGlobal,
			})

	def keyNumberGlobal(self, number):
#		print "You pressed number " + str(number)
		if number == 0:
			if isinstance(self, InfoBarPiP) and self.pipHandles0Action():
				self.pipDoHandle0Action()
			else:
				self.servicelist.recallPrevService()
		else:
			if "TimeshiftActions" in self and not self.timeshift_enabled:
				self.session.openWithCallback(self.numberEntered, NumberZap, number)

	def numberEntered(self, retval):
#		print self.servicelist
		if retval > 0:
			self.zapToNumber(retval)

	def searchNumberHelper(self, serviceHandler, num, bouquet):
		servicelist = serviceHandler.list(bouquet)
		if not servicelist is None:
			while num:
				serviceIterator = servicelist.getNext()
				if not serviceIterator.valid(): #check end of list
					break
				playable = not (serviceIterator.flags & (eServiceReference.isMarker|eServiceReference.isDirectory))
				if playable:
					num -= 1;
			if not num: #found service with searched number ?
				return serviceIterator, 0
		return None, num

	def zapToNumber(self, number):
		bouquet = self.servicelist.bouquet_root
		service = None
		serviceHandler = eServiceCenter.getInstance()
		if not config.usage.multibouquet.value:
			service, number = self.searchNumberHelper(serviceHandler, number, bouquet)
		else:
			bouquetlist = serviceHandler.list(bouquet)
			if not bouquetlist is None:
				while number:
					bouquet = bouquetlist.getNext()
					if not bouquet.valid(): #check end of list
						break
					if bouquet.flags & eServiceReference.isDirectory:
						service, number = self.searchNumberHelper(serviceHandler, number, bouquet)
		if not service is None:
			if self.servicelist.getRoot() != bouquet: #already in correct bouquet?
				self.servicelist.clearPath()
				if self.servicelist.bouquet_root != bouquet:
					self.servicelist.enterPath(self.servicelist.bouquet_root)
				self.servicelist.enterPath(bouquet)
			self.servicelist.setCurrentSelection(service) #select the service in servicelist
			self.servicelist.zap()

config.misc.initialchannelselection = ConfigBoolean(default = True)

class InfoBarChannelSelection:
	""" ChannelSelection - handles the channelSelection dialog and the initial
	channelChange actions which open the channelSelection dialog """
	def __init__(self):
		#instantiate forever
		self.servicelist = self.session.instantiateDialog(ChannelSelection, zPosition=0)
		self.servicelist.onRootChanged.append(self.__onServiceListRootChanged)

		if config.misc.initialchannelselection.value:
			self.onShown.append(self.firstRun)

		self["ChannelSelectActions"] = HelpableActionMap(self, "InfobarChannelSelection",
			{
				"switchChannelUp": (self.switchChannelUp, _("open servicelist(up)")),
				"switchChannelDown": (self.switchChannelDown, _("open servicelist(down)")),
				"zapUp": (self.zapUp, _("previous channel")),
				"zapDown": (self.zapDown, _("next channel")),
				"historyBack": (self.historyBack, _("previous channel in history")),
				"historyNext": (self.historyNext, _("next channel in history")),
				"openServiceList": (self.openServiceList, _("open servicelist")),
			})

		self.onServiceListRootChanged = []
		self.onClose.append(self.__delChannelSelectionScreen)

	def __delChannelSelectionScreen(self):
		self.session.deleteDialog(self.servicelist)
		self.servicelist = None

	def __onServiceListRootChanged(self, ref):
		for fnc in self.onServiceListRootChanged:
			fnc(ref)

	def showTvChannelList(self, zap=False):
		self.servicelist.setModeTv()
		if zap:
			self.servicelist.zap()
		self.session.execDialog(self.servicelist)

	def showRadioChannelList(self, zap=False):
		self.servicelist.setModeRadio()
		if zap:
			self.servicelist.zap()
		self.session.execDialog(self.servicelist)

	def firstRun(self):
		self.onShown.remove(self.firstRun)
		config.misc.initialchannelselection.value = False
		config.misc.initialchannelselection.save()
		self.switchChannelDown()

	def historyBack(self):
		self.servicelist.historyBack()

	def historyNext(self):
		self.servicelist.historyNext()

	def switchChannelUp(self):
		self.servicelist.moveUp()
		self.session.execDialog(self.servicelist)

	def switchChannelDown(self):
		self.servicelist.moveDown()
		self.session.execDialog(self.servicelist)

	def openServiceList(self):
		self.session.execDialog(self.servicelist)

	def zapUp(self):
		if self.servicelist.inBouquet():
			prev = self.servicelist.getCurrentSelection()
			if prev:
				prev = prev.toString()
				while True:
					if config.usage.quickzap_bouquet_change.value:
						if self.servicelist.atBegin():
							self.servicelist.prevBouquet()
					self.servicelist.moveUp()
					cur = self.servicelist.getCurrentSelection()
					if not cur or (not (cur.flags & 64)) or cur.toString() == prev:
						break
		else:
			self.servicelist.moveUp()
		self.servicelist.zap()

	def zapDown(self):
		if self.servicelist.inBouquet():
			prev = self.servicelist.getCurrentSelection()
			if prev:
				prev = prev.toString()
				while True:
					if config.usage.quickzap_bouquet_change.value and self.servicelist.atEnd():
						self.servicelist.nextBouquet()
					else:
						self.servicelist.moveDown()
					cur = self.servicelist.getCurrentSelection()
					if not cur or (not (cur.flags & 64)) or cur.toString() == prev:
						break
		else:
			self.servicelist.moveDown()
		self.servicelist.zap()

	def getNextService(self, currentService):
		services = self.servicelist.servicelist.getRootServices()
		isRelevant = False
		ref = currentService.toString()
		for service in services:
			if isRelevant:
				cur = eServiceReference(service)
				print("getNextService {0} / {1}".format(service, ref))
				if not cur or (not (cur.flags & 64)):
					return cur
			if service == ref:
				isRelevant = True
		return currentService

	def getPrevService(self, currentService):
		services = self.servicelist.servicelist.getRootServices()
		previous = []
		ref = currentService.toString()
		for service in services:
			if service == ref:
				for svc in previous:
					cur = eServiceReference(svc)
					print("getPrevService {0} / {1}".format(svc, ref))
					if not cur or (not (cur.flags & 64)):
						return cur
			else:
				previous.append(service)
		return currentService

class InfoBarMenu:
	""" Handles a menu action, to open the (main) menu """
	def __init__(self):
		self["MenuActions"] = HelpableActionMap(self, "InfobarMenuActions",
			{
				"mainMenu": (self.mainMenu, _("Enter main menu...")),
			})
		self.session.infobar = None

	def mainMenu(self):
		print("loading mainmenu XML...")
		menu = mdom.getroot()
		assert menu.tag == "menu", "root element in menu must be 'menu'!"

		self.session.infobar = self
		# so we can access the currently active infobar from screens opened from within the mainmenu
		# at the moment used from the SubserviceSelection

		self.session.openWithCallback(self.mainMenuClosed, MainMenu, menu)

	def mainMenuClosed(self, *val):
		self.session.infobar = None

#yet used in MoviePlayer.. not normal Infobar ... look at InfoBarEPG!
class InfoBarSimpleEventView:
	""" Opens the Eventview for now/next """
	def __init__(self):
		self.first_call = True
		config.misc.rcused.addNotifier(self.__rcUsedChanged, True, False, True)
		self.onClose.append(self.__onClose)

	def __onClose(self):
		config.misc.rcused.removeNotifier(self.__rcUsedChanged)

	def __rcUsedChanged(self, configElement):
		if self.first_call:
			if configElement.value == 0:
				self["EPGActions"] = HelpableActionMap(self, "InfobarEPGActions",
					{
						"showEventInfo": (self.openEventView, _("show event details")),
						"showInfobarOrEpgWhenInfobarAlreadyVisible": self.showEventInfoWhenNotVisible,
						"showEventList": (self.audioSelection, _("Audio Options...")),
					})
			else:
				self["EPGActions"] = HelpableActionMap(self, "InfobarEPGActions",
					{
						"showEventInfo": (self.openEventView, _("show event details")),
						"showInfobarOrEpgWhenInfobarAlreadyVisible": self.showEventInfoWhenNotVisible,
					})
			self.first_call = False
		elif configElement.value == 0:
			self["EPGActions"].update(self, "InfobarEPGActions",
				{
					"showEventInfo": (self.openEventView, _("show event details")),
					"showInfobarOrEpgWhenInfobarAlreadyVisible": self.showEventInfoWhenNotVisible,
					"showEventList": (self.audioSelection, _("Audio Options...")),
				})
		else:
			self["EPGActions"].update(self, "InfobarEPGActions",
				{
					"showEventInfo": (self.openEventView, _("show event details")),
					"showInfobarOrEpgWhenInfobarAlreadyVisible": self.showEventInfoWhenNotVisible,
				})

	def showEventInfoWhenNotVisible(self):
		if self.shown:
			self.openEventView()
		else:
			self.toggleShow()
			return 1

	def openEventView(self):
		epglist = [ ]
		self.epglist = epglist
		service = self.session.nav.getCurrentService()
		ref = self.session.nav.getCurrentlyPlayingServiceReference()
		info = service.info()
		ptr=info.getEvent(0)
		if ptr:
			epglist.append(ptr)
		ptr=info.getEvent(1)
		if ptr:
			epglist.append(ptr)
		if epglist:
			self.session.open(EventViewSimple, epglist[0], ServiceReference(ref), self.eventViewCallback)

	def eventViewCallback(self, setEvent, setService, val): #used for now/next displaying
		epglist = self.epglist
		if len(epglist) > 1:
			tmp = epglist[0]
			epglist[0] = epglist[1]
			epglist[1] = tmp
			setEvent(epglist[0])

class SimpleServicelist:
	def __init__(self, services):
		self.services = services
		self.length = len(services)
		self.current = 0

	def selectService(self, service):
		if not self.length:
			self.current = -1
			return False
		else:
			self.current = 0
			while self.services[self.current].ref != service:
				self.current += 1
				if self.current >= self.length:
					return False
		return True

	def nextService(self):
		if not self.length:
			return
		if self.current+1 < self.length:
			self.current += 1
		else:
			self.current = 0

	def prevService(self):
		if not self.length:
			return
		if self.current-1 > -1:
			self.current -= 1
		else:
			self.current = self.length - 1

	def currentService(self):
		if not self.length or self.current >= self.length:
			return None
		return self.services[self.current]

class InfoBarEPG:
	""" EPG - Opens an EPG list when the showEPGList action fires """
	def __init__(self):
		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evUpdatedEventInfo: self.__evEventInfoChanged,
			})

		self.is_now_next = False
		self.dlg_stack = [ ]
		self.bouquetSel = None
		self.eventView = None
		self.first_call = True
		config.misc.rcused.addNotifier(self.__rcUsedChanged, True, False, True)
		self.onClose.append(self.__onClose)

	def __onClose(self):
		config.misc.rcused.removeNotifier(self.__rcUsedChanged)

	def __rcUsedChanged(self, configElement):
		yellow = (self.openSingleServiceEPG, _("show single service EPG..."))
		if configElement.value == 0:
			yellow = (self.audioSelection, _("Audio Options..."))
		elif configElement.value == 1:
			yellow = (self.startTimeshift, _("start timeshift"))

		if self.first_call:
			self["EPGActions"] = HelpableActionMap(self, "InfobarEPGActions",
				{
					"showEventInfo": (self.openEventView, _("show EPG...")),
					"showEventInfoPlugin": (self.showEventInfoPlugins, _("list of EPG views...")),
					"showInfobarOrEpgWhenInfobarAlreadyVisible": self.showEventInfoWhenNotVisible,
					"showEventList": yellow
				})
			self.first_call = False
		else:
			self["EPGActions"].update(self, "InfobarEPGActions",
				{
					"showEventInfo": (self.openEventView, _("show EPG...")),
					"showEventInfoPlugin": (self.showEventInfoPlugins, _("list of EPG views...")),
					"showInfobarOrEpgWhenInfobarAlreadyVisible": self.showEventInfoWhenNotVisible,
					"showEventList": yellow
				})

	def showEventInfoWhenNotVisible(self):
		if self.shown:
			self.openEventView()
		else:
			self.toggleShow()
			return 1

	def zapToService(self, service):
		if not service is None:
			if self.servicelist.getRoot() != self.epg_bouquet: #already in correct bouquet?
				self.servicelist.clearPath()
				if self.servicelist.bouquet_root != self.epg_bouquet:
					self.servicelist.enterPath(self.servicelist.bouquet_root)
				self.servicelist.enterPath(self.epg_bouquet)
			self.servicelist.setCurrentSelection(service) #select the service in servicelist
			self.servicelist.zap()

	def getBouquetServices(self, bouquet):
		services = [ ]
		servicelist = eServiceCenter.getInstance().list(bouquet)
		if not servicelist is None:
			while True:
				service = servicelist.getNext()
				if not service.valid(): #check if end of list
					break
				if service.flags & (eServiceReference.isDirectory | eServiceReference.isMarker): #ignore non playable services
					continue
				services.append(ServiceReference(service))
		return services

	def openBouquetEPG(self, bouquet, withCallback=True):
		services = self.getBouquetServices(bouquet)
		if services:
			self.epg_bouquet = bouquet
			if withCallback:
				self.dlg_stack.append(self.session.openWithCallback(self.closed, EPGSelection, services, self.zapToService, None, self.changeBouquetCB))
			else:
				self.session.open(EPGSelection, services, self.zapToService, None, self.changeBouquetCB)

	def changeBouquetCB(self, direction, epg):
		if self.bouquetSel:
			if direction > 0:
				self.bouquetSel.down()
			else:
				self.bouquetSel.up()
			bouquet = self.bouquetSel.getCurrent()
			services = self.getBouquetServices(bouquet)
			if services:
				self.epg_bouquet = bouquet
				epg.setServices(services)

	def closed(self, ret=False):
		closedScreen = self.dlg_stack.pop()
		if closedScreen is self.bouquetSel:
			self.bouquetSel = None
		elif closedScreen is self.eventView:
			self.eventView = None
			self.is_now_next = False
		if ret:
			dlgs=len(self.dlg_stack)
			if dlgs > 0:
				self.dlg_stack[dlgs-1].close(dlgs > 1)

	def openMultiServiceEPG(self, withCallback=True):
		bouquets = self.servicelist.getBouquetList()
		if bouquets is None:
			cnt = 0
		else:
			cnt = len(bouquets)
		if config.usage.multiepg_ask_bouquet.value:
			self.openMultiServiceEPGAskBouquet(bouquets, cnt, withCallback)
		else:
			self.openMultiServiceEPGSilent(bouquets, cnt, withCallback)

	def openMultiServiceEPGAskBouquet(self, bouquets, cnt, withCallback):
		if cnt > 1: # show bouquet list
			if withCallback:
				self.bouquetSel = self.session.openWithCallback(self.closed, BouquetSelector, bouquets, self.openBouquetEPG, enableWrapAround=True)
				self.dlg_stack.append(self.bouquetSel)
			else:
				self.bouquetSel = self.session.open(BouquetSelector, bouquets, self.openBouquetEPG, enableWrapAround=True)
		elif cnt == 1:
			self.openBouquetEPG(bouquets[0][1], withCallback)

	def openMultiServiceEPGSilent(self, bouquets, cnt, withCallback):
		root = self.servicelist.getRoot()
		rootstr = root.toCompareString()
		current = 0
		for bouquet in bouquets:
			if bouquet[1].toCompareString() == rootstr:
				break
			current += 1
		if current >= cnt:
			current = 0
		if cnt > 1: # create bouquet list for bouq+/-
			self.bouquetSel = SilentBouquetSelector(bouquets, True, self.servicelist.getBouquetNumOffset(root))
		if cnt >= 1:
			self.openBouquetEPG(root, withCallback)

	def changeServiceCB(self, direction, epg):
		if self.serviceSel:
			if direction > 0:
				self.serviceSel.nextService()
			else:
				self.serviceSel.prevService()
			epg.setService(self.serviceSel.currentService())

	def SingleServiceEPGClosed(self, ret=False):
		self.serviceSel = None

	def openSingleServiceEPG(self):
		ref=self.session.nav.getCurrentlyPlayingServiceReference()
		if ref:
			if self.servicelist.getMutableList() is not None: # bouquet in channellist
				current_path = self.servicelist.getRoot()
				services = self.getBouquetServices(current_path)
				self.serviceSel = SimpleServicelist(services)
				if self.serviceSel.selectService(ref):
					self.session.openWithCallback(self.SingleServiceEPGClosed, EPGSelection, ref, serviceChangeCB = self.changeServiceCB)
				else:
					self.session.openWithCallback(self.SingleServiceEPGClosed, EPGSelection, ref)
			else:
				self.session.open(EPGSelection, ref)

	def openOutdatedSingleServiceEPG(self):
		ref=self.session.nav.getCurrentlyPlayingServiceReference()
		if ref:
			if self.servicelist.getMutableList() is not None: # bouquet in channellist
				current_path = self.servicelist.getRoot()
				services = self.getBouquetServices(current_path)
				self.serviceSel = SimpleServicelist(services)
				if self.serviceSel.selectService(ref):
					self.session.openWithCallback(self.SingleServiceEPGClosed, OutdatedEPGSelection, ref, serviceChangeCB = self.changeServiceCB)
				else:
					self.session.openWithCallback(self.SingleServiceEPGClosed, OutdatedEPGSelection, ref)
			else:
				self.session.open(OutdatedEPGSelection, ref)

	def showEventInfoPlugins(self):
		list = [(p.name, boundFunction(self.runPlugin, p)) for p in plugins.getPlugins(where = PluginDescriptor.WHERE_EVENTINFO)]

		if list:
			list.append((_("show single service EPG..."), self.openSingleServiceEPG))
			if config.misc.epgcache_outdated_timespan.value:
				list.append((_("show outdated service EPG..."), self.openOutdatedSingleServiceEPG))
			list.append((_("Multi EPG"), self.openMultiServiceEPG))
			self.session.openWithCallback(self.EventInfoPluginChosen, ChoiceBox, title=_("Please choose an extension..."), list = list, skin_name = "EPGExtensionsList")
		else:
			self.openSingleServiceEPG()

	def runPlugin(self, plugin):
		plugin(session = self.session, servicelist = self.servicelist)

	def EventInfoPluginChosen(self, answer):
		if answer is not None:
			answer[1]()

	def openSimilarList(self, eventid, refstr):
		self.session.open(EPGSelection, refstr, None, eventid)

	def getNowNext(self):
		epglist = [ ]
		service = self.session.nav.getCurrentService()
		info = service and service.info()
		ptr = info and info.getEvent(0)
		if ptr:
			epglist.append(ptr)
		ptr = info and info.getEvent(1)
		if ptr:
			epglist.append(ptr)
		self.epglist = epglist

	def __evEventInfoChanged(self):
		if self.is_now_next:
			self.getNowNext()
			if self.epglist:
				self.eventView.setEvent(self.epglist[0])

	def openEventView(self):
		ref = self.session.nav.getCurrentlyPlayingServiceReference()
		self.getNowNext()
		epglist = self.epglist
		if not epglist:
			epg = eEPGCache.getInstance()
			ptr = ref and ref.valid() and epg.lookupEventTime(ref, -1)
			if ptr:
				epglist.append(ptr)
				ptr = epg.lookupEventTime(ref, ptr.getBeginTime(), +1)
				if ptr:
					epglist.append(ptr)
		else:
			self.is_now_next = True
		if epglist:
			self.eventView = self.session.openWithCallback(self.closed, EventViewEPGSelect, self.epglist[0], ServiceReference(ref), self.eventViewCallback, self.openSingleServiceEPG, self.openMultiServiceEPG, self.openSimilarList)
			self.dlg_stack.append(self.eventView)
		else:
			print("no epg for the service avail.. so we show multiepg instead of eventinfo")
			self.openMultiServiceEPG(False)

	def eventViewCallback(self, setEvent, setService, val): #used for now/next displaying
		epglist = self.epglist
		if len(epglist) > 1:
			tmp = epglist[0]
			epglist[0]=epglist[1]
			epglist[1]=tmp
			setEvent(epglist[0])

class InfoBarRdsDecoder:
	"""provides RDS and Rass support/display"""
	def __init__(self):
		self.rds_display = self.session.instantiateDialog(RdsInfoDisplay)
		self.rds_display.neverAnimate()
		self.onClose.append(self.__delRdsInfoDisplayScreen)

	def __delRdsInfoDisplayScreen(self):
		self.session.deleteDialog(self.rds_display)
		self.rds_display = None

class PlayerBase:
	def __init__(self):
		self.lastservice = self.session.nav.getCurrentlyPlayingServiceReference()

		if not isinstance(self, InfoBarChannelSelection):
			self.onFirstExecBegin.append(self.__registerPlayer)

	def __registerPlayer(self):
		self.prev_player = self.session.current_player
		self.session.current_player = self
		self.onClose.append(self.__unRegisterPlayer)

	def __unRegisterPlayer(self):
		self.session.current_player = self.prev_player
		self.session.nav.playService(self.lastservice)

# Since we dont want to change any existing player class, here we assume that each player inherits from InfoBarSeek.
# If this is not the case the player explicitely have to inherit from PlayerBase and must call the init function!
class InfoBarSeek(PlayerBase):
	"""handles actions like seeking, pause"""

	SEEK_STATE_PLAY = (0, 0, 0, ">")
	SEEK_STATE_PAUSE = (1, 0, 0, "||")
	SEEK_STATE_EOF = (1, 0, 0, "END")
	SEEK_STATE_STOP = (0, 0, 0, "STOP")

	def __init__(self, actionmap = "InfobarSeekActions"):
		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evSeekableStatusChanged: self.__seekableStatusChanged,
				iPlayableService.evStart: self.__serviceStarted,

				iPlayableService.evEOF: self.__evEOF,
				iPlayableService.evSOF: self.__evSOF
			})
		self.fast_winding_hint_message_showed = False

		class InfoBarSeekActionMap(HelpableActionMap):
			def __init__(self, screen, *args, **kwargs):
				HelpableActionMap.__init__(self, screen, *args, **kwargs)
				self.screen = screen

			def action(self, contexts, action):
				print("action:", action)
				if action[:5] == "seek:":
					time = int(action[5:])
					self.screen.doSeekRelative(time * 90000)
					return 1
				elif action[:8] == "seekdef:":
					key = int(action[8:])
					time = (-config.seek.selfdefined_13.value, False, config.seek.selfdefined_13.value,
						-config.seek.selfdefined_46.value, False, config.seek.selfdefined_46.value,
						-config.seek.selfdefined_79.value, False, config.seek.selfdefined_79.value)[key-1]
					self.screen.doSeekRelative(time * 90000)
					return 1
				else:
					return HelpableActionMap.action(self, contexts, action)

		self["SeekActions"] = InfoBarSeekActionMap(self, actionmap,
			{
				"playpauseService": self.playpauseService,
				"pauseService": (self.pauseService, _("pause")),
				"unPauseService": (self.unPauseService, _("continue")),

				"seekFwd": (self.seekFwd, _("skip forward")),
				"seekFwdManual": (self.seekFwdManual, _("skip forward (enter time)")),
				"seekBack": (self.seekBack, _("skip backward")),
				"seekBackManual": (self.seekBackManual, _("skip backward (enter time)"))
			}, prio=-1)
			# give them a little more priority to win over color buttons

		self["SeekActions"].setEnabled(False)

		self.seekstate = self.SEEK_STATE_STOP
		self.lastseekstate = self.SEEK_STATE_STOP

		self.onPlayStateChanged = [ ]

		self.lockedBecauseOfSkipping = False

		self.__seekableStatusChanged()

		PlayerBase.__init__(self)

	def makeStateForward(self, n):
		return (0, n, 0, ">> %dx" % n)

	def makeStateBackward(self, n):
		return (0, -n, 0, "<< %dx" % n)

	def makeStateSlowMotion(self, n):
		return (0, 0, n, "/%d" % n)

	def isStateForward(self, state):
		return state[1] > 1

	def isStateBackward(self, state):
		return state[1] < 0

	def isStateSlowMotion(self, state):
		return state[1] == 0 and state[2] > 1

	def getHigher(self, n, lst):
		for x in lst:
			if x > n:
				return x
		return False

	def getLower(self, n, lst):
		lst = lst[:]
		lst.reverse()
		for x in lst:
			if x < n:
				return x
		return False

	def showAfterSeek(self):
		if isinstance(self, InfoBarShowHide):
			self.doShow()

	def up(self):
		pass

	def down(self):
		pass

	def getSeek(self):
		service = self.session.nav.getCurrentService()
		if service is None:
			return None

		seek = service.seek()

		if seek is None or not seek.isCurrentlySeekable():
			return None

		return seek

	def isSeekable(self):
		import Screens.InfoBar

		if self.getSeek() is None or (isinstance(self, Screens.InfoBar.InfoBar) and not self.timeshift_enabled):
			return False
		return True

	def __seekableStatusChanged(self):
#		print "seekable status changed!"
		if not self.isSeekable():
			self["SeekActions"].setEnabled(False)
#			print "not seekable, return to play"
			self.setSeekState(self.SEEK_STATE_PLAY)
		else:
			self["SeekActions"].setEnabled(True)
#			print "seekable"

	def __serviceStarted(self):
		self.fast_winding_hint_message_showed = False
		self.setSeekState(self.SEEK_STATE_PLAY, True)
		self.__seekableStatusChanged()

	def setSeekState(self, state, onlyGUI = False):
		service = self.session.nav.getCurrentService()
		ret = 0

		if service is None:
			return False

		if not onlyGUI and state != self.SEEK_STATE_STOP:
			if not self.isSeekable():
				if state not in (self.SEEK_STATE_PLAY, self.SEEK_STATE_PAUSE):
					state = self.SEEK_STATE_PLAY

			pauseable = service.pause()

			if pauseable is None:
				print("not pauseable.")
				state = self.SEEK_STATE_PLAY

			if pauseable is not None:
				if state[0]:
					ret = pauseable.pause()
					print("resolved to PAUSE", ret)
				elif state[1]:
					ret = pauseable.setFastForward(state[1])
					print("resolved to FAST FORWARD", ret)
				elif state[2]:
					ret = pauseable.setSlowMotion(state[2])
					print("resolved to SLOW MOTION", ret)
				else:
					ret = pauseable.unpause()
					print("resolved to PLAY", ret)

		if ret == 0:
			self.seekstate = state
			for c in self.onPlayStateChanged:
				c(self.seekstate)

		self.checkSkipShowHideLock()

		return (ret == 0)

	def playpauseService(self):
		if self.seekstate != self.SEEK_STATE_PLAY:
			self.unPauseService()
		else:
			self.pauseService()

	def pauseService(self):
		if self.seekstate == self.SEEK_STATE_PAUSE:
			if config.seek.on_pause.value == "play":
				self.unPauseService()
			elif config.seek.on_pause.value == "step":
				self.doSeekRelative(1)
			elif config.seek.on_pause.value == "last":
				self.setSeekState(self.lastseekstate)
				self.lastseekstate = self.SEEK_STATE_PLAY
		else:
			if self.seekstate != self.SEEK_STATE_EOF:
				self.lastseekstate = self.seekstate
			self.setSeekState(self.SEEK_STATE_PAUSE);

	def unPauseService(self):
		print("unpause")
		if self.seekstate == self.SEEK_STATE_PLAY:
			return 0
		self.setSeekState(self.SEEK_STATE_PLAY)

	def doSeek(self, pts):
		seekable = self.getSeek()
		if seekable is None:
			return
		seekable.seekTo(pts)

	def doSeekRelative(self, pts):
		seekable = self.getSeek()
		if seekable is None:
			return
		prevstate = self.seekstate

		if self.seekstate == self.SEEK_STATE_EOF:
			if prevstate == self.SEEK_STATE_PAUSE:
				self.setSeekState(self.SEEK_STATE_PAUSE)
			else:
				self.setSeekState(self.SEEK_STATE_PLAY)
		seekable.seekRelative(pts<0 and -1 or 1, abs(pts))
		if abs(pts) > 100 and config.usage.show_infobar_on_skip.value:
			self.showAfterSeek()

	def seekFwd(self):
		seek = self.getSeek()
		if seek and not (seek.isCurrentlySeekable() & 2):
			if not self.fast_winding_hint_message_showed and (seek.isCurrentlySeekable() & 1):
				self.session.open(MessageBox, _("No fast winding possible yet.. but you can use the number buttons to skip forward/backward!"), MessageBox.TYPE_INFO, timeout=10)
				self.fast_winding_hint_message_showed = True
				return
			return 0 # trade as unhandled action
		if self.seekstate == self.SEEK_STATE_PLAY:
			self.setSeekState(self.makeStateForward(int(config.seek.enter_forward.value)))
		elif self.seekstate == self.SEEK_STATE_PAUSE:
			if len(config.seek.speeds_slowmotion.value):
				self.setSeekState(self.makeStateSlowMotion(config.seek.speeds_slowmotion.value[-1]))
			else:
				self.setSeekState(self.makeStateForward(int(config.seek.enter_forward.value)))
		elif self.seekstate == self.SEEK_STATE_EOF:
			pass
		elif self.isStateForward(self.seekstate):
			speed = self.seekstate[1]
			if self.seekstate[2]:
				speed /= self.seekstate[2]
			speed = self.getHigher(speed, config.seek.speeds_forward.value) or config.seek.speeds_forward.value[-1]
			self.setSeekState(self.makeStateForward(speed))
		elif self.isStateBackward(self.seekstate):
			speed = -self.seekstate[1]
			if self.seekstate[2]:
				speed /= self.seekstate[2]
			speed = self.getLower(speed, config.seek.speeds_backward.value)
			if speed:
				self.setSeekState(self.makeStateBackward(speed))
			else:
				self.setSeekState(self.SEEK_STATE_PLAY)
		elif self.isStateSlowMotion(self.seekstate):
			speed = self.getLower(self.seekstate[2], config.seek.speeds_slowmotion.value) or config.seek.speeds_slowmotion.value[0]
			self.setSeekState(self.makeStateSlowMotion(speed))

	def seekBack(self):
		seek = self.getSeek()
		if seek and not (seek.isCurrentlySeekable() & 2):
			if not self.fast_winding_hint_message_showed and (seek.isCurrentlySeekable() & 1):
				self.session.open(MessageBox, _("No fast winding possible yet.. but you can use the number buttons to skip forward/backward!"), MessageBox.TYPE_INFO, timeout=10)
				self.fast_winding_hint_message_showed = True
				return
			return 0 # trade as unhandled action
		seekstate = self.seekstate
		if seekstate == self.SEEK_STATE_PLAY:
			self.setSeekState(self.makeStateBackward(int(config.seek.enter_backward.value)))
		elif seekstate == self.SEEK_STATE_EOF:
			self.setSeekState(self.makeStateBackward(int(config.seek.enter_backward.value)))
			self.doSeekRelative(-6)
		elif seekstate == self.SEEK_STATE_PAUSE:
			self.doSeekRelative(-1)
		elif self.isStateForward(seekstate):
			speed = seekstate[1]
			if seekstate[2]:
				speed /= seekstate[2]
			speed = self.getLower(speed, config.seek.speeds_forward.value)
			if speed:
				self.setSeekState(self.makeStateForward(speed))
			else:
				self.setSeekState(self.SEEK_STATE_PLAY)
		elif self.isStateBackward(seekstate):
			speed = -seekstate[1]
			if seekstate[2]:
				speed /= seekstate[2]
			speed = self.getHigher(speed, config.seek.speeds_backward.value) or config.seek.speeds_backward.value[-1]
			self.setSeekState(self.makeStateBackward(speed))
		elif self.isStateSlowMotion(seekstate):
			speed = self.getHigher(seekstate[2], config.seek.speeds_slowmotion.value)
			if speed:
				self.setSeekState(self.makeStateSlowMotion(speed))
			else:
				self.setSeekState(self.SEEK_STATE_PAUSE)

	def seekFwdManual(self):
		self.session.openWithCallback(self.fwdSeekTo, MinuteInput)

	def fwdSeekTo(self, minutes):
		print("Seek", minutes, "minutes forward")
		self.doSeekRelative(minutes * 60 * 90000)

	def seekBackManual(self):
		self.session.openWithCallback(self.rwdSeekTo, MinuteInput)

	def rwdSeekTo(self, minutes):
		print("rwdSeekTo")
		self.doSeekRelative(-minutes * 60 * 90000)

	def checkSkipShowHideLock(self):
		wantlock = self.seekstate != self.SEEK_STATE_PLAY

		if config.usage.show_infobar_on_skip.value:
			if self.lockedBecauseOfSkipping and not wantlock:
				self.unlockShow()
				self.lockedBecauseOfSkipping = False

			if wantlock and not self.lockedBecauseOfSkipping:
				self.lockShow()
				self.lockedBecauseOfSkipping = True

	def calcRemainingTime(self):
		seekable = self.getSeek()
		if seekable is not None:
			len = seekable.getLength()
			try:
				tmp = self.cueGetEndCutPosition()
				if tmp:
					len = [False, tmp]
			except:
				pass
			pos = seekable.getPlayPosition()
			speednom = self.seekstate[1] or 1
			speedden = self.seekstate[2] or 1
			if not len[0] and not pos[0]:
				if len[1] <= pos[1]:
					return 0
				time = (len[1] - pos[1])*speedden//(90*speednom)
				return time
		return False

	def __evEOF(self):
		if self.seekstate == self.SEEK_STATE_EOF:
			return

		# if we are seeking forward, we try to end up ~1s before the end, and pause there.
		seekstate = self.seekstate
		if self.seekstate != self.SEEK_STATE_PAUSE:
			self.setSeekState(self.SEEK_STATE_EOF)

		if seekstate not in (self.SEEK_STATE_PLAY, self.SEEK_STATE_PAUSE): # if we are seeking
			seekable = self.getSeek()
			if seekable is not None:
				seekable.seekTo(-1)
		if seekstate == self.SEEK_STATE_PLAY: # regular EOF
			self.doEofInternal(True)
		else:
			self.doEofInternal(False)

	def doEofInternal(self, playing):
		pass		# Defined in subclasses

	def __evSOF(self):
		self.setSeekState(self.SEEK_STATE_PLAY)
		self.doSeek(0)

from Screens.PVRState import PVRState, TimeshiftState

class InfoBarPVRState:
	def __init__(self, screen=PVRState, force_show = False):
		self.onPlayStateChanged.append(self.__playStateChanged)
		self.pvrStateDialog = self.session.instantiateDialog(screen)
		self.pvrStateDialog.neverAnimate()
		self.onShow.append(self._mayShow)
		self.onHide.append(self.pvrStateDialog.hide)
		self.onClose.append(self.__delPvrState)
		self.force_show = force_show

	def __delPvrState(self):
		self.session.deleteDialog(self.pvrStateDialog)
		self.pvrStateDialog = None

	def _mayShow(self):
		if self.execing and self.seekstate != self.SEEK_STATE_PLAY:
			self.pvrStateDialog.show()

	def __playStateChanged(self, state):
		playstateString = state[3]
		self.pvrStateDialog["state"].setText(playstateString)

		# if we return into "PLAY" state, ensure that the dialog gets hidden if there will be no infobar displayed
		# also hide if service stopped and returning into MovieList
		if not config.usage.show_infobar_on_skip.value and self.seekstate in (self.SEEK_STATE_PLAY, self.SEEK_STATE_STOP) and not self.force_show:
			self.pvrStateDialog.hide()
		else:
			self._mayShow()

class InfoBarTimeshiftState(InfoBarPVRState):
	def __init__(self):
		InfoBarPVRState.__init__(self, screen=TimeshiftState, force_show = True)
		self.__hideTimer = eTimer()
		self.__hideTimer_conn = self.__hideTimer.timeout.connect(self.__hideTimeshiftState)

	def _mayShow(self):
		if self.execing and self.timeshift_enabled:
			self.pvrStateDialog.show()
			if self.seekstate == self.SEEK_STATE_PLAY and not self.shown:
				self.__hideTimer.start(5*1000, True)

	def __hideTimeshiftState(self):
		self.pvrStateDialog.hide()

class InfoBarShowMovies:

	# i don't really like this class.
	# it calls a not further specified "movie list" on up/down/movieList,
	# so this is not more than an action map
	def __init__(self):
		self["MovieListActions"] = HelpableActionMap(self, "InfobarMovieListActions",
			{
				"movieList": (self.showMovies, _("movie list")),
				"up": (self.showMovies, _("movie list")),
				"down": (self.showMovies, _("movie list"))
			})

# InfoBarTimeshift requires InfoBarSeek, instantiated BEFORE!

# Hrmf.
#
# Timeshift works the following way:
#                                         demux0   demux1                    "TimeshiftActions" "TimeshiftActivateActions" "SeekActions"
# - normal playback                       TUNER    unused      PLAY               enable                disable              disable
# - user presses "yellow" button.         FILE     record      PAUSE              enable                disable              enable
# - user presess pause again              FILE     record      PLAY               enable                disable              enable
# - user fast forwards                    FILE     record      FF                 enable                disable              enable
# - end of timeshift buffer reached       TUNER    record      PLAY               enable                enable               disable
# - user backwards                        FILE     record      BACK  # !!         enable                disable              enable
#

# in other words:
# - when a service is playing, pressing the "timeshiftStart" button ("yellow") enables recording ("enables timeshift"),
# freezes the picture (to indicate timeshift), sets timeshiftMode ("activates timeshift")
# now, the service becomes seekable, so "SeekActions" are enabled, "TimeshiftEnableActions" are disabled.
# - the user can now PVR around
# - if it hits the end, the service goes into live mode ("deactivates timeshift", it's of course still "enabled")
# the service looses it's "seekable" state. It can still be paused, but just to activate timeshift right
# after!
# the seek actions will be disabled, but the timeshiftActivateActions will be enabled
# - if the user rewinds, or press pause, timeshift will be activated again

# note that a timeshift can be enabled ("recording") and
# activated (currently time-shifting).

class InfoBarTimeshift:
	def __init__(self):
		self["TimeshiftActions"] = HelpableActionMap(self, "InfobarTimeshiftActions",
			{
				"timeshiftStart": (self.startTimeshift, _("start timeshift")),  # the "yellow key"
				"timeshiftStop": (self.stopTimeshift, _("stop timeshift"))      # currently undefined :), probably 'TV'
			}, prio=1)
		self["TimeshiftActivateActions"] = ActionMap(["InfobarTimeshiftActivateActions"],
			{
				"timeshiftActivateEnd": self.activateTimeshiftEnd, # something like "rewind key"
				"timeshiftActivateEndAndPause": self.activateTimeshiftEndAndPause  # something like "pause key"
			}, prio=-1) # priority over record

		self.timeshift_enabled = 0
		self.timeshift_state = 0
		self.ts_rewind_timer = eTimer()
		self.ts_rewind_timer_conn = self.ts_rewind_timer.timeout.connect(self.rewindService)

		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evStart: self.__serviceStarted,
				iPlayableService.evSeekableStatusChanged: self.__seekableStatusChanged
			})

	def getTimeshift(self):
		service = self.session.nav.getCurrentService()
		return service and service.timeshift()

	def startTimeshift(self):
		print("enable timeshift")
		ts = self.getTimeshift()
		if ts is None:
			if harddiskmanager.HDDCount() and not harddiskmanager.HDDEnabledCount():
				self.session.open(MessageBox, _("Timeshift not possible!") + "\n" \
					+ _("Please make sure to set up your storage devices with the storage management in menu -> setup -> system -> storage devices."), MessageBox.TYPE_ERROR)
			elif harddiskmanager.HDDEnabledCount() and defaultStorageDevice() == "<undefined>":
				self.session.open(MessageBox, _("Timeshift not possible!") + "\n" \
					+ _("Please make sure to set up your default storage device in menu -> setup -> system -> recording paths."), MessageBox.TYPE_ERROR)
			elif harddiskmanager.HDDEnabledCount() and defaultStorageDevice() != "<undefined>":
				part = harddiskmanager.getDefaultStorageDevicebyUUID(defaultStorageDevice())
				if part is None:
					self.session.open(MessageBox, _("Timeshift not possible!") + "\n" \
						+ _("Please verify if your default storage device is attached or set up your default storage device in menu -> setup -> system -> recording paths."), MessageBox.TYPE_ERROR)
			else:
				self.session.open(MessageBox, _("Timeshift not possible!"), MessageBox.TYPE_ERROR)
				print("no ts interface")
			return 0

		if self.timeshift_enabled:
			print("hu, timeshift already enabled?")
		else:
			if not ts.startTimeshift():
				self.timeshift_enabled = 1

				# we remove the "relative time" for now.
				#self.pvrStateDialog["timeshift"].setRelative(time.time())

				# PAUSE.
				#self.setSeekState(self.SEEK_STATE_PAUSE)
				self.activateTimeshiftEnd(False)

				# enable the "TimeshiftEnableActions", which will override
				# the startTimeshift actions
				self.__seekableStatusChanged()
			else:
				print("timeshift failed")

	def stopTimeshift(self):
		if not self.timeshift_enabled:
			return 0
		print("disable timeshift")
		ts = self.getTimeshift()
		if ts is None:
			return 0
		self.session.openWithCallback(self.stopTimeshiftConfirmed, MessageBox, _("Stop Timeshift?"), MessageBox.TYPE_YESNO)

	def stopTimeshiftConfirmed(self, confirmed):
		if not confirmed:
			return

		ts = self.getTimeshift()
		if ts is None:
			return

		ts.stopTimeshift()
		self.timeshift_enabled = 0

		# disable actions
		self.__seekableStatusChanged()

	# activates timeshift, and seeks to (almost) the end
	def activateTimeshiftEnd(self, back = True):
		ts = self.getTimeshift()
		print("activateTimeshiftEnd")

		if ts is None:
			return

		if ts.isTimeshiftActive():
			print("!! activate timeshift called - but shouldn't this be a normal pause?")
			self.pauseService()
		else:
			print("play, ...")
			ts.activateTimeshift() # activate timeshift will automatically pause
			self.setSeekState(self.SEEK_STATE_PAUSE)

		if back:
			self.ts_rewind_timer.start(200, 1)

	def rewindService(self):
		self.setSeekState(self.makeStateBackward(int(config.seek.enter_backward.value)))

	# same as activateTimeshiftEnd, but pauses afterwards.
	def activateTimeshiftEndAndPause(self):
		print("activateTimeshiftEndAndPause")
		#state = self.seekstate
		self.activateTimeshiftEnd(False)

	def __seekableStatusChanged(self):
		enabled = False

#		print "self.isSeekable", self.isSeekable()
#		print "self.timeshift_enabled", self.timeshift_enabled

		# when this service is not seekable, but timeshift
		# is enabled, this means we can activate
		# the timeshift
		if not self.isSeekable() and self.timeshift_enabled:
			enabled = True

#		print "timeshift activate:", enabled
		self["TimeshiftActivateActions"].setEnabled(enabled)

	def __serviceStarted(self):
		self.timeshift_enabled = False
		self.__seekableStatusChanged()

from Screens.PiPSetup import PiPSetup

class InfoBarExtensions:
	EXTENSION_SINGLE = 0
	EXTENSION_LIST = 1

	def __init__(self):
		self.list = []

		self["InstantExtensionsActions"] = HelpableActionMap(self, "InfobarExtensions",
			{
				"extensions": (self.showExtensionSelection, _("view extensions...")),
			}, 1) # lower priority

	def addExtension(self, extension, key = None, type = EXTENSION_SINGLE):
		self.list.append((type, extension, key))

	def updateExtension(self, extension, key = None):
		self.extensionsList.append(extension)
		if key is not None:
			if key in self.extensionKeys:
				key = None

		if key is None:
			for x in self.availableKeys:
				if x not in self.extensionKeys:
					key = x
					break

		if key is not None:
			self.extensionKeys[key] = len(self.extensionsList) - 1

	def updateExtensions(self):
		self.extensionsList = []
		self.availableKeys = [ "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "red", "green", "yellow", "blue", "text" ]
		self.extensionKeys = {}
		for x in self.list:
			if x[0] == self.EXTENSION_SINGLE:
				self.updateExtension(x[1], x[2])
			else:
				for y in x[1]():
					self.updateExtension(y[0], y[1])


	def showExtensionSelection(self):
		self.updateExtensions()
		extensionsList = self.extensionsList[:]
		keys = []
		list = []
		for x in self.availableKeys:
			if x in self.extensionKeys:
				entry = self.extensionKeys[x]
				extension = self.extensionsList[entry]
				if extension[2]():
					list.append((extension[0](), extension))
					keys.append(x)
					extensionsList.remove(extension)
				else:
					extensionsList.remove(extension)
		list.extend([(x[0](), x) for x in extensionsList])

		keys += [""] * len(extensionsList)
		self.session.openWithCallback(self.extensionCallback, ChoiceBox, title=_("Please choose an extension..."), titlebartext=_("Extensions"), list = list, keys = keys, skin_name = "ExtensionsList", is_dialog=False)

	def extensionCallback(self, answer):
		if answer is not None:
			answer[1][1]()

from Tools.BoundFunction import boundFunction
import inspect

# depends on InfoBarExtensions

class InfoBarPlugins:
	def __init__(self):
		self.addExtension(extension = self.getPluginList, type = InfoBarExtensions.EXTENSION_LIST)

	def getPluginName(self, name):
		return name

	def getPluginList(self):
		l = []
		for p in plugins.getPlugins(where = PluginDescriptor.WHERE_EXTENSIONSMENU):
			args = inspect.getargspec(p.__call__)[0]
			if len(args) == 1 or len(args) == 2 and isinstance(self, InfoBarChannelSelection):
				l.append(((boundFunction(self.getPluginName, p.name), boundFunction(self.runPlugin, p), lambda: True), None, p.name))
		l.sort(key = lambda e: e[2]) # sort by name
		return l

	def runPlugin(self, plugin):
		if isinstance(self, InfoBarChannelSelection):
			plugin(session = self.session, servicelist = self.servicelist)
		else:
			plugin(session = self.session)

from Components.Task import job_manager
class InfoBarJobman:
	def __init__(self):
		self.addExtension(extension = self.getJobList, type = InfoBarExtensions.EXTENSION_LIST)

	def getJobList(self):
		return [((boundFunction(self.getJobName, job), boundFunction(self.showJobView, job), lambda: True), None) for job in job_manager.getPendingJobs()]

	def getJobName(self, job):
		return "%s: %s (%d%%)" % (job.getStatustext(), job.name, int(100*job.progress/float(job.end)))

	def showJobView(self, job):
		from Screens.TaskView import JobView
		job_manager.in_background = False
		self.session.openWithCallback(self.JobViewCB, JobView, job)

	def JobViewCB(self, in_background):
		job_manager.in_background = in_background

# depends on InfoBarExtensions
class InfoBarPiP:
	def __init__(self):
		try:
			self.session.pipshown
		except:
			self.session.pipshown = False
		if SystemInfo.get("NumVideoDecoders", 1) > 1:
			if (self.allowPiP):
				self.addExtension((self.getShowHideName, self.showPiP, lambda: True), "blue")
				self.addExtension((self.getMoveName, self.movePiP, self.pipShown), "green")
				self.addExtension((self.getSwapName, self.swapPiP, self.pipShown), "yellow")
			else:
				self.addExtension((self.getShowHideName, self.showPiP, self.pipShown), "blue")
				self.addExtension((self.getMoveName, self.movePiP, self.pipShown), "green")

	def pipShown(self):
		return self.session.pipshown

	def pipHandles0Action(self):
		return self.pipShown() and config.usage.pip_zero_button.value != "standard"

	def getShowHideName(self):
		if self.session.pipshown:
			return _("Disable Picture in Picture")
		else:
			return _("Activate Picture in Picture")

	def getSwapName(self):
		return _("Swap Services")

	def getMoveName(self):
		return _("Move Picture in Picture")

	def showPiP(self):
		if self.session.pipshown:
			print("pip currently shown.... pointer:", self.session.pip)
			self.session.deleteDialog(self.session.pip)
			del self.session.pip
			print('hasattr(self.session,"pip")', hasattr(self.session,"pip"))
			self.session.pipshown = False
		else:
			self.session.pip = self.session.instantiateDialog(PictureInPicture)
			self.session.pip.neverAnimate()
			self.session.pip.show()
			newservice = self.session.nav.getCurrentlyPlayingServiceReference()
			if self.session.pip.playService(newservice):
				self.session.pipshown = True
				self.session.pip.servicePath = self.servicelist.getCurrentServicePath()
			else:
				self.session.pipshown = False
				self.session.deleteDialog(self.session.pip)
				del self.session.pip
			self.session.nav.playService(newservice)

	def swapPiP(self):
		swapservice = self.session.nav.getCurrentlyPlayingServiceReference()
		if self.session.pip.servicePath:
			servicepath = self.servicelist.getCurrentServicePath()
			ref=servicepath[len(servicepath)-1]
			pipref=self.session.pip.getCurrentService()
			self.session.pip.playService(swapservice)
			self.servicelist.setCurrentServicePath(self.session.pip.servicePath)
			if pipref.toString() != ref.toString(): # is a subservice ?
				self.session.nav.stopService() # stop portal
				self.session.nav.playService(pipref) # start subservice
			self.session.pip.servicePath=servicepath

	def movePiP(self):
		self.session.open(PiPSetup, pip = self.session.pip)

	def pipDoHandle0Action(self):
		use = config.usage.pip_zero_button.value
		if "swap" == use:
			self.swapPiP()
		elif "swapstop" == use:
			self.swapPiP()
			self.showPiP()
		elif "stop" == use:
			self.showPiP()

from RecordTimer import parseEvent

class InfoBarInstantRecord:
	"""Instant Record - handles the instantRecord action in order to
	start/stop instant records"""
	def __init__(self):
		self["InstantRecordActions"] = HelpableActionMap(self, "InfobarInstantRecord",
			{
				"instantRecord": (self.instantRecord, _("Instant Record...")),
			})

		self.session.nav.RecordTimer.on_state_change.append(self.timerentryOnStateChange)
		self.recording = []

		self.stopOptionList = ((_("stop recording"), "stop"), \
			(_("add recording (stop after current event)"), "event"), \
			(_("add recording (indefinitely)"), "indefinitely"), \
			(_("add recording (enter recording duration)"), "manualduration"), \
			(_("add recording (enter recording endtime)"), "manualendtime"), \
			(_("change recording (duration)"), "changeduration"), \
			(_("change recording (endtime)"), "changeendtime"), \
			(_("do nothing"), "no"))

		self.startOptionList = ((_("add recording (stop after current event)"), "event"), \
			(_("add recording (indefinitely)"), "indefinitely"), \
			(_("add recording (enter recording duration)"), "manualduration"), \
			(_("add recording (enter recording endtime)"), "manualendtime"), \
			(_("don't record"), "no"))

	def timerentryOnStateChange(self, timer):
		# timer recording has been started, append to self.recording list
		if hasattr(self, "recording") and timer.isRunning():
			if not timer in self.recording: # only if timer is not in list already
				self.recording.append(timer)

	def stopCurrentRecording(self, entry = -1):
		if entry is not None and entry != -1:
			t = self.recording[entry]
			if t.repeated:	# do not delete repeated timer, ask user what to do
				choicelist = (
					(_("Stop current event but not coming events"), "stoponlycurrent"),
					(_("Stop current event and disable coming events"), "stopall")
				)
				self.session.openWithCallback(boundFunction(self.runningRepeatedTimerCallback, t), ChoiceBox, title=_("Repeating event currently recording... What do you want to do?"), list = choicelist)
			else:
				self.session.nav.RecordTimer.removeEntry(t)
				self.recording.remove(t)

	def runningRepeatedTimerCallback(self, t, result):
		if result is not None:
			if result[1] == "stoponlycurrent":
				t.enable()
				t.processRepeated(findRunningEvent = False)
				self.session.nav.RecordTimer.doActivate(t)
			elif result[1] == "stopall":
				t.disable()
			self.session.nav.RecordTimer.timeChanged(t)
			self.recording.remove(t)


	def startInstantRecording(self, limitEvent = False):
		serviceref = self.session.nav.getCurrentlyPlayingServiceReference()

		# try to get event info
		event = None
		try:
			service = self.session.nav.getCurrentService()
			epg = eEPGCache.getInstance()
			event = epg.lookupEventTime(serviceref, -1, 0)
			if event is None:
				info = service.info()
				ev = info.getEvent(0)
				event = ev
		except:
			pass

		begin = int(time())
		end = begin + 3600	# dummy
		name = "instant record"
		description = ""
		eventid = None

		if event is not None:
			curEvent = parseEvent(event)
			name = curEvent[2]
			description = curEvent[3]
			eventid = curEvent[4]
			if limitEvent:
				end = curEvent[1]
		else:
			if limitEvent:
				self.session.open(MessageBox, _("No event info found, recording indefinitely."), MessageBox.TYPE_INFO)

		if isinstance(serviceref, eServiceReference):
			serviceref = ServiceReference(serviceref)

		recording = RecordTimerEntry(serviceref, begin, end, name, description, eventid, dirname = preferredInstantRecordPath())
		recording.dontSave = True

		if event is None or limitEvent == False:
			recording.autoincrease = True
			recording.setAutoincreaseEnd()

		self.recording.append(recording)
		simulTimerList = self.session.nav.RecordTimer.record(recording)

		if simulTimerList is not None:
			if len(simulTimerList) > 1: # with other recording
				name = simulTimerList[1].name
				name_date = ' '.join((name, strftime('%c', localtime(simulTimerList[1].begin))))
				print("[TIMER] conflicts with", name_date)
				recording.autoincrease = True	# start with max available length, then increment
				if recording.setAutoincreaseEnd():
					self.session.nav.RecordTimer.record(recording)
					self.session.open(MessageBox, _("Record time limited due to conflicting timer %s") % name_date, MessageBox.TYPE_INFO)
				else:
					self.recording.remove(recording)
					self.session.open(MessageBox, _("Couldn't record due to conflicting timer %s") % name, MessageBox.TYPE_INFO)
			else:
				self.recording.remove(recording)
				self.session.open(MessageBox, _("Couldn't record due to invalid service %s") % serviceref, MessageBox.TYPE_INFO)
			recording.autoincrease = False

	def isInstantRecordRunning(self):
		print("self.recording:", self.recording)
		if self.recording:
			for x in self.recording:
				if x.isRunning():
					return True
		return False

	def recordQuestionCallback(self, answer):
		print("pre:\n", self.recording)

		if answer is None or answer[1] == "no":
			return
		list = []
		recording = self.recording[:]
		for x in recording:
			if not x in self.session.nav.RecordTimer.timer_list or not x.isRunning(): # check for isRunning because of repeated timer (there are still in the timerlist!)
				self.recording.remove(x)
			elif x.isRunning():
				list.append((x, False))

		if answer[1] == "changeduration":
			self.session.openWithCallback(self.changeDuration, TimerSelection, list)
		elif answer[1] == "changeendtime":
			self.session.openWithCallback(self.setEndtime, TimerSelection, list)
		elif answer[1] == "stop":
			self.session.openWithCallback(self.stopCurrentRecording, TimerSelection, list)
		elif answer[1] in ( "indefinitely" , "manualduration", "manualendtime", "event"):
			self.startInstantRecording(limitEvent = answer[1] in ("event", "manualendtime") or False)
			if answer[1] == "manualduration":
				self.changeDuration(len(self.recording)-1)
			elif answer[1] == "manualendtime":
				self.setEndtime(len(self.recording)-1)
		print("after:\n", self.recording)

	def setEndtime(self, entry):
		if entry is not None and entry >= 0:
			self.selectedEntry = entry
			self.endtime=ConfigClock(default = self.recording[self.selectedEntry].end)
			dlg = self.session.openWithCallback(self.TimeDateInputClosed, TimeDateInput, self.endtime)
			dlg.setTitle(_("Please change recording endtime"))

	def TimeDateInputClosed(self, ret):
		if len(ret) > 1:
			if ret[0]:
				localendtime = localtime(ret[1])
				print("stopping recording at", strftime("%c", localendtime))
				if self.recording[self.selectedEntry].end != ret[1]:
					self.recording[self.selectedEntry].autoincrease = False
				self.recording[self.selectedEntry].end = ret[1]
				self.session.nav.RecordTimer.timeChanged(self.recording[self.selectedEntry])

	def changeDuration(self, entry):
		if entry is not None and entry >= 0:
			self.selectedEntry = entry
			self.session.openWithCallback(self.inputCallback, InputBox, title=_("How many minutes do you want to record?"), text="5", maxSize=False, type=Input.NUMBER)

	def inputCallback(self, value):
		if value is not None:
			print("stopping recording after", int(value), "minutes.")
			entry = self.recording[self.selectedEntry]
			if int(value) != 0:
				entry.autoincrease = False
			entry.end = int(time()) + 60 * int(value)
			self.session.nav.RecordTimer.timeChanged(entry)

	def instantRecord(self):
		dir = preferredInstantRecordPath()
		if not dir or not fileExists(dir, 'w'):
			dir = defaultMoviePath()
		if not harddiskmanager.inside_mountpoint(dir):
			if harddiskmanager.HDDCount() and not harddiskmanager.HDDEnabledCount():
				self.session.open(MessageBox, _("Unconfigured storage devices found!") + "\n" \
					+ _("Please make sure to set up your storage devices with the storage management in menu -> setup -> system -> storage devices."), MessageBox.TYPE_ERROR)
				return
			elif harddiskmanager.HDDEnabledCount() and defaultStorageDevice() == "<undefined>":
				self.session.open(MessageBox, _("No default storage device found!") + "\n" \
					+ _("Please make sure to set up your default storage device in menu -> setup -> system -> recording paths."), MessageBox.TYPE_ERROR)
				return
			elif harddiskmanager.HDDEnabledCount() and defaultStorageDevice() != "<undefined>":
				part = harddiskmanager.getDefaultStorageDevicebyUUID(defaultStorageDevice())
				if part is None:
					self.session.open(MessageBox, _("Default storage device is not available!") + "\n" \
						+ _("Please verify if your default storage device is attached or set up your default storage device in menu -> setup -> system -> recording paths."), MessageBox.TYPE_ERROR)
					return
			else:
				# XXX: this message is a little odd as we might be recording to a remote device
				self.session.open(MessageBox, _("No HDD found or HDD not initialized!"), MessageBox.TYPE_ERROR)
				return

		if self.isInstantRecordRunning():
			self.session.openWithCallback(self.recordQuestionCallback, ChoiceBox, \
				title=_("A recording is currently running.\nWhat do you want to do?"), \
				list=self.stopOptionList)
		else:
			self.session.openWithCallback(self.recordQuestionCallback, ChoiceBox, \
				title=_("Start recording?"), \
				list=self.startOptionList)

class InfoBarAudioSelection:
	def __init__(self):
		self["AudioSelectionAction"] = HelpableActionMap(self, "InfobarAudioSelectionActions",
			{
				"audioSelection": (self.audioSelection, _("Audio Options...")),
			})

	def audioSelection(self):
		from Screens.AudioSelection import AudioSelection
		self.session.openWithCallback(self.audioSelected, AudioSelection, infobar=self)

	def audioSelected(self, ret=None):
		print("[infobar::audioSelected]", ret)

class InfoBarSubserviceSelection:
	def __init__(self):
		self["SubserviceSelectionAction"] = HelpableActionMap(self, "InfobarSubserviceSelectionActions",
			{
				"subserviceSelection": (self.subserviceSelection, _("Subservice list...")),
			})

		self["SubserviceQuickzapAction"] = HelpableActionMap(self, "InfobarSubserviceQuickzapActions",
			{
				"nextSubservice": (self.nextSubservice, _("Switch to next subservice")),
				"prevSubservice": (self.prevSubservice, _("Switch to previous subservice"))
			}, -1)
		self["SubserviceQuickzapAction"].setEnabled(False)

		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evUpdatedEventInfo: self.checkSubservicesAvail
			})

		self.bsel = None

	def checkSubservicesAvail(self):
		service = self.session.nav.getCurrentService()
		subservices = service and service.subServices()
		if not subservices or subservices.getNumberOfSubservices() == 0:
			self["SubserviceQuickzapAction"].setEnabled(False)

	def nextSubservice(self):
		self.changeSubservice(+1)

	def prevSubservice(self):
		self.changeSubservice(-1)

	def changeSubservice(self, direction):
		service = self.session.nav.getCurrentService()
		subservices = service and service.subServices()
		n = subservices and subservices.getNumberOfSubservices()
		if n and n > 0:
			selection = -1
			ref = self.session.nav.getCurrentlyPlayingServiceReference()
			idx = 0
			while idx < n:
				if subservices.getSubservice(idx).toString() == ref.toString():
					selection = idx
					break
				idx += 1
			if selection != -1:
				selection += direction
				if selection >= n:
					selection=0
				elif selection < 0:
					selection=n-1
				newservice = subservices.getSubservice(selection)
				if newservice.valid():
					del subservices
					del service
					self.playSubservice(newservice)

	def playSubservice(self, ref):
		if ref.getUnsignedData(6) == 0:
			ref.setName("")
		self.session.nav.playService(ref, False)

	def subserviceSelection(self):
		service = self.session.nav.getCurrentService()
		subservices = service and service.subServices()
		self.bouquets = self.servicelist.getBouquetList()
		n = subservices and subservices.getNumberOfSubservices()
		selection = 0
		if n and n > 0:
			ref = self.session.nav.getCurrentlyPlayingServiceReference()
			tlist = []
			idx = 0
			cnt_parent = 0
			while idx < n:
				i = subservices.getSubservice(idx)
				if i == ref:
					selection = idx
				tlist.append((i.getName(), i))
				if i.getUnsignedData(6):
					cnt_parent += 1
				idx += 1

			if cnt_parent and self.bouquets and len(self.bouquets):
				keys = ["red", "blue", "",  "0", "1", "2", "3", "4", "5", "6", "7", "8", "9" ] + [""] * n
				if config.usage.multibouquet.value:
					tlist = [(_("Quickzap"), "quickzap", service.subServices()), (_("Add to bouquet"), "CALLFUNC", self.addSubserviceToBouquetCallback), ("--", "")] + tlist
				else:
					tlist = [(_("Quickzap"), "quickzap", service.subServices()), (_("Add to favourites"), "CALLFUNC", self.addSubserviceToBouquetCallback), ("--", "")] + tlist
				selection += 3
			else:
				tlist = [(_("Quickzap"), "quickzap", service.subServices()), ("--", "")] + tlist
				keys = ["red", "",  "0", "1", "2", "3", "4", "5", "6", "7", "8", "9" ] + [""] * n
				selection += 2

			self.session.openWithCallback(self.subserviceSelected, ChoiceBox, title=_("Please select a subservice..."), list = tlist, selection = selection, keys = keys, skin_name = "SubserviceSelection")

	def subserviceSelected(self, service):
		del self.bouquets
		if not service is None:
			if isinstance(service[1], str):
				if service[1] == "quickzap":
					from Screens.SubservicesQuickzap import SubservicesQuickzap
					self.session.open(SubservicesQuickzap, service[2])
			else:
				self["SubserviceQuickzapAction"].setEnabled(True)
				self.playSubservice(service[1])

	def addSubserviceToBouquetCallback(self, service):
		if len(service) > 1 and isinstance(service[1], eServiceReference):
			self.selectedSubservice = service
			if self.bouquets is None:
				cnt = 0
			else:
				cnt = len(self.bouquets)
			if cnt > 1: # show bouquet list
				self.bsel = self.session.openWithCallback(self.bouquetSelClosed, BouquetSelector, self.bouquets, self.addSubserviceToBouquet)
			elif cnt == 1: # add to only one existing bouquet
				self.addSubserviceToBouquet(self.bouquets[0][1])
				self.session.open(MessageBox, _("Service has been added to the favourites."), MessageBox.TYPE_INFO)

	def bouquetSelClosed(self, confirmed):
		self.bsel = None
		del self.selectedSubservice
		if confirmed:
			self.session.open(MessageBox, _("Service has been added to the selected bouquet."), MessageBox.TYPE_INFO)

	def addSubserviceToBouquet(self, dest):
		self.servicelist.addServiceToBouquet(dest, self.selectedSubservice[1])
		if self.bsel:
			self.bsel.close(True)
		else:
			del self.selectedSubservice

class InfoBarAdditionalInfo:
	def __init__(self):
		self.first_call = True
		config.misc.rcused.addNotifier(self.__rcUsedChanged, True, False, True)
		harddiskmanager.delayed_device_Notifier.append(self.__HDDDetectedCB)
		self["ExtensionsAvailable"] = Boolean(fixed=1)
		self["PendingNotification"] = Boolean(fixed=0)
		self.onClose.append(self.__onClose)

	def __onClose(self):
		config.misc.rcused.removeNotifier(self.__rcUsedChanged)
		harddiskmanager.delayed_device_Notifier.remove(self.__HDDDetectedCB)

	def __HDDDetectedCB(self, dev, media_state):
		self["RecordingPossible"].boolean = harddiskmanager.HDDCount() > 0 and config.misc.rcused.value == 1

	def __rcUsedChanged(self, configElement):
		if self.first_call:
			self["RecordingPossible"] = Boolean(fixed=harddiskmanager.HDDCount() > 0 and configElement.value == 1)
			self["TimeshiftPossible"] = self["RecordingPossible"]
			self["ShowAudioOnYellow"] = Boolean(fixed=configElement.value == 0)
			self["ShowTimeshiftOnYellow"] = Boolean(fixed=configElement.value == 1)
			self["ShowEventListOnYellow"] = Boolean(fixed=configElement.value == 2)
			self["ShowRecordOnRed"] = Boolean(fixed=configElement.value == 1)
			self.first_call = False
		else:
			self["RecordingPossible"].boolean = harddiskmanager.HDDCount() > 0 and configElement.value == 1
			self["TimeshiftPossible"].boolean = self["RecordingPossible"].boolean
			self["ShowAudioOnYellow"].boolean = configElement.value == 0
			self["ShowTimeshiftOnYellow"].boolean = configElement.value == 1
			self["ShowEventListOnYellow"].boolean = configElement.value == 2
			self["ShowRecordOnRed"].boolean = configElement.value == 1

class InfoBarNotifications:
	def __init__(self):
		self.onExecBegin.append(self.checkNotifications)
		Notifications.notificationQueue.addedCB.append(self.checkNotificationsIfExecing)
		self.onClose.append(self.__removeNotification)
#		if isinstance(self, InfoBarExtensions):
#			self.addExtension((self.getEntryText, self.showNotificationQueueViewer, lambda: True), key = "text")

	def __removeNotification(self):
		Notifications.notificationQueue.addedCB.remove(self.checkNotificationsIfExecing)

	def checkNotificationsIfExecing(self):
		if self.execing:
			self.checkNotifications()

	def checkNotifications(self, immediate=False):
		def doCheck(self):
			if self.execing:
				Notifications.notificationQueue.popNotification(self)
		if immediate:
			doCheck(self)
		else:
			from twisted.internet import reactor
			reactor.callLater(0, doCheck, self)

	def getEntryText(self):
		numPending = len(Notifications.notificationQueue.getPending())
		text = _("Notification Queue")
		if numPending == 1:
			text += " (1 new event)"
		elif numPending > 1:
			text += " (%i new events)" % numPending
		return text

	def showNotificationQueueViewer(self):
		from Screens.NotificationQueueViewer import NotificationQueueViewer
		self.session.open(NotificationQueueViewer)

class InfoBarServiceNotifications:
	def __init__(self):
		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evEnd: self.serviceHasEnded
			})

	def serviceHasEnded(self):
		print("service end!")
		try:
			self.setSeekState(self.SEEK_STATE_STOP, True)
		except:
			pass

class InfoBarCueSheetSupport:
	CUT_TYPE_IN = 0
	CUT_TYPE_OUT = 1
	CUT_TYPE_MARK = 2
	CUT_TYPE_LAST = 3

	ENABLE_RESUME_SUPPORT = False

	def __init__(self, actionmap = "InfobarCueSheetActions"):
		self["CueSheetActions"] = HelpableActionMap(self, actionmap,
			{
				"jumpPreviousMark": (self.jumpPreviousMark, _("jump to previous marked position")),
				"jumpNextMark": (self.jumpNextMark, _("jump to next marked position")),
				"toggleMark": (self.toggleMark, _("toggle a cut mark at the current position"))
			}, prio=1)

		self.cut_list = [ ]
		self.is_closing = False
		self.length = [0,0]
		self._tryResume = False
		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evStart: self.__serviceStarted,
				iPlayableService.evSeekableStatusChanged: self.__onSeekableStatusChanged,
				iPlayableService.evCuesheetChanged: self.__downloadChangedCuesheet
			})

	def __serviceStarted(self):
		self._tryResume = False
		if self.is_closing:
			return
		print("new service started! trying to download cuts!")
		self.downloadCuesheet()

		if self.ENABLE_RESUME_SUPPORT:
			last = None

			for (pts, what) in self.cut_list:
				if what == self.CUT_TYPE_LAST:
					last = pts

			if last is not None:
				self.resume_point = last

				if (self.length[1] > 0) and abs(self.length[1] - last) < 4*90000: # if last playpos is within 4 seconds span to the length of this recording, assume it has been watched all the way to the end and don't resume
					return
				l = last // 90000
				if l < config.usage.resume_treshold.value:
					Log.w("Resume treshold not reached, starting from the beginning")
					return
				if config.usage.on_movie_start.value == "ask":
					Notifications.AddNotificationWithCallback(self.playLastCB, MessageBox, _("Do you want to resume this playback?") + "\n" + (_("Resume position at %s") % ("%d:%02d:%02d" % (l//3600, l%3600//60, l%60))), timeout=10, domain = "InfoBar")
				elif config.usage.on_movie_start.value == "resume":
# TRANSLATORS: The string "Resuming playback" flashes for a moment
# TRANSLATORS: at the start of a movie, when the user has selected
# TRANSLATORS: "Resume from last position" as start behavior.
# TRANSLATORS: The purpose is to notify the user that the movie starts
# TRANSLATORS: in the middle somewhere and not from the beginning.
# TRANSLATORS: (Some translators seem to have interpreted it as a
# TRANSLATORS: question or a choice, but it is a statement.)
					self.session.toastManager.showToast(_("Resuming playback"))
					if self.isSeekable():
						self.playLastCB(True)
					else:
						self._tryResume = True

	def __onSeekableStatusChanged(self):
		if self._tryResume and self.isSeekable():
			self._tryResume = False
			self.playLastCB(True)

	def playLastCB(self, answer):
		if answer == True:
			self.doSeek(self.resume_point)
		self.hideAfterResume()

	def hideAfterResume(self):
		if isinstance(self, InfoBarShowHide):
			self.hide()

	def __getSeekable(self):
		service = self.session.nav.getCurrentService()
		if service is None:
			return None
		return service.seek()

	def cueGetCurrentPosition(self):
		seek = self.__getSeekable()
		if seek is None:
			return None
		r = seek.getPlayPosition()
		if r[0]:
			return None
		return int(r[1])

	def cueGetEndCutPosition(self):
		ret = False
		isin = True
		for cp in self.cut_list:
			if cp[1] == self.CUT_TYPE_OUT:
				if isin:
					isin = False
					ret = cp[0]
			elif cp[1] == self.CUT_TYPE_IN:
				isin = True
		return ret

	def jumpPreviousNextMark(self, cmp, start=False):
		current_pos = self.cueGetCurrentPosition()
		if current_pos is None:
			return False
		mark = self.getNearestCutPoint(current_pos, cmp=cmp, start=start)
		if mark is not None:
			pts = mark[0]
		else:
			return False
		self.doSeek(pts)
		return True

	def jumpPreviousMark(self):
		# we add 5 seconds, so if the play position is <5s after
		# the mark, the mark before will be used
		self.jumpPreviousNextMark(lambda x: -x-5*90000, start=True)

	def jumpNextMark(self):
		if not self.jumpPreviousNextMark(lambda x: x-90000):
			self.doSeek(-1)

	def getNearestCutPoint(self, pts, cmp=abs, start=False):
		# can be optimized
		beforecut = True
		nearest = None
		bestdiff = -1
		instate = True
		if start:
			bestdiff = cmp(0 - pts)
			if bestdiff >= 0:
				nearest = [0, False]
		for cp in self.cut_list:
			if beforecut and cp[1] in (self.CUT_TYPE_IN, self.CUT_TYPE_OUT):
				beforecut = False
				if cp[1] == self.CUT_TYPE_IN:  # Start is here, disregard previous marks
					diff = cmp(cp[0] - pts)
					if start and diff >= 0:
						nearest = cp
						bestdiff = diff
					else:
						nearest = None
						bestdiff = -1
			if cp[1] == self.CUT_TYPE_IN:
				instate = True
			elif cp[1] == self.CUT_TYPE_OUT:
				instate = False
			elif cp[1] in (self.CUT_TYPE_MARK, self.CUT_TYPE_LAST):
				diff = cmp(cp[0] - pts)
				if instate and diff >= 0 and (nearest is None or bestdiff > diff):
					nearest = cp
					bestdiff = diff
		return nearest

	def toggleMark(self, onlyremove=False, onlyadd=False, tolerance=5*90000, onlyreturn=False):
		current_pos = self.cueGetCurrentPosition()
		if current_pos is None:
			print("not seekable")
			return

		nearest_cutpoint = self.getNearestCutPoint(current_pos)

		if nearest_cutpoint is not None and abs(nearest_cutpoint[0] - current_pos) < tolerance:
			if onlyreturn:
				return nearest_cutpoint
			if not onlyadd:
				self.removeMark(nearest_cutpoint)
		elif not onlyremove and not onlyreturn:
			self.addMark((current_pos, self.CUT_TYPE_MARK))

		if onlyreturn:
			return None

	def addMark(self, point):
		insort(self.cut_list, point)
		self.uploadCuesheet()
		self.showAfterCuesheetOperation()

	def removeMark(self, point):
		self.cut_list.remove(point)
		self.uploadCuesheet()
		self.showAfterCuesheetOperation()

	def showAfterCuesheetOperation(self):
		if isinstance(self, InfoBarShowHide):
			self.doShow()

	def __getCuesheet(self):
		service = self.session.nav.getCurrentService()
		if service is None:
			return None
		if self.__getSeekable():
			self.length = self.__getSeekable().getLength()
		return service.cueSheet()

	def uploadCuesheet(self):
		cue = self.__getCuesheet()

		if cue is None:
			print("upload failed, no cuesheet interface")
			return
		cue.setCutList(self.cut_list)

	def __downloadChangedCuesheet(self):
		self.downloadCuesheet()

	def downloadCuesheet(self):
		cue = self.__getCuesheet()

		if cue is None:
			print("download failed, no cuesheet interface")
			self.cut_list = [ ]
		else:
			self.cut_list = cue.getCutList()

class InfoBarSummary(Screen):
	skin = """
	<screen position="0,0" size="132,64">
		<widget source="global.CurrentTime" render="Label" position="62,46" size="82,18" font="Regular;16" >
			<convert type="ClockToText">WithSeconds</convert>
		</widget>
		<widget source="session.RecordState" render="FixedLabel" text=" " position="62,46" size="82,18" zPosition="1" >
			<convert type="ConfigEntryTest">config.usage.blinking_display_clock_during_recording,True,CheckSourceBoolean</convert>
			<convert type="ConditionalShowHide">Blink</convert>
		</widget>
		<widget source="session.CurrentService" render="Label" position="6,4" size="120,42" font="Regular;18" >
			<convert type="ServiceName">Name</convert>
		</widget>
		<widget source="session.Event_Now" render="Progress" position="6,46" size="46,18" borderWidth="1" >
			<convert type="EventTime">Progress</convert>
		</widget>
	</screen>"""

# for picon:  (path="piconlcd" will use LCD picons)
#		<widget source="session.CurrentService" render="Picon" position="6,0" size="120,64" path="piconlcd" >
#			<convert type="ServiceName">Reference</convert>
#		</widget>

class InfoBarSummarySupport:
	def __init__(self):
		pass

	def createSummary(self):
		return InfoBarSummary

class InfoBarMoviePlayerSummary(Screen):
	skin = """
	<screen position="0,0" size="132,64">
		<widget source="global.CurrentTime" render="Label" position="62,46" size="64,18" font="Regular;16" halign="right" >
			<convert type="ClockToText">WithSeconds</convert>
		</widget>
		<widget source="session.RecordState" render="FixedLabel" text=" " position="62,46" size="64,18" zPosition="1" >
			<convert type="ConfigEntryTest">config.usage.blinking_display_clock_during_recording,True,CheckSourceBoolean</convert>
			<convert type="ConditionalShowHide">Blink</convert>
		</widget>
		<widget source="session.CurrentService" render="Label" position="6,4" size="120,42" font="Regular;18" >
			<convert type="ServiceName">Name</convert>
		</widget>
		<widget source="session.CurrentService" render="Progress" position="6,46" size="56,18" borderWidth="1" >
			<convert type="ServicePosition">Position</convert>
		</widget>
	</screen>"""

class InfoBarMoviePlayerSummarySupport:
	def __init__(self):
		pass

	def createSummary(self):
		return InfoBarMoviePlayerSummary

class InfoBarTeletextPlugin:
	def __init__(self):
		self["TeletextActions"] = HelpableActionMap(self, "InfobarTeletextActions",
			{
				"startTeletext": (self.startTeletext, _("View teletext..."))
			})

	def startTeletext(self):
		teletext_plugins = plugins.getPlugins(PluginDescriptor.WHERE_TELETEXT)
		l = len(teletext_plugins)
		if l == 1:
			teletext_plugins[0](session=self.session, service=self.session.nav.getCurrentService())
		elif l > 1:
			list = []
			for p in teletext_plugins:
				list.append( (p.name, p) )
			self.session.openWithCallback(self.onTextSelected, ChoiceBox, title=_("Please select a Text application"), list = list)

	def onTextSelected(self, p):
		p = p and p[1]
		if p is not None:
			p(session=self.session, service=self.session.nav.getCurrentService())

class InfobarHbbtvPlugin:
	def __init__(self):
		self["HbbtvActions"] = HelpableActionMap(self, "InfobarHbbtvActions",
			{
				"hbbtvAutostart" : (self.startHbbtv, _("Start HbbTV..."))
			})
		self["HbbtvApplication"] = HbbtvApplication()
		config.misc.rcused.addNotifier(self.__rcUsedChanged, True, False, True)
		self.onClose.append(self.__onClose)

	def __onClose(self):
		config.misc.rcused.removeNotifier(self.__rcUsedChanged)

	def __rcUsedChanged(self, configElement):
		app = self["HbbtvApplication"]
		if not self["ShowRecordOnRed"].boolean and haveHbbtvApplication:
			self["HbbtvActions"].setEnabled(True)
			app.disabled = False
			app.changed((app.CHANGED_ALL,))
		else:
			self["HbbtvActions"].setEnabled(False)
			app.disabled = True
			app.changed((app.CHANGED_ALL,))

	def startHbbtv(self):
		hbbtv_plugin = None
		for p in plugins.getPlugins(PluginDescriptor.WHERE_HBBTV):
			hbbtv_plugin = p
		if hbbtv_plugin is not None:
			hbbtv_plugin(session=self.session)

class InfoBarSubtitleSupport(object):
	def __init__(self):
		object.__init__(self)
		self.subtitle_window = self.session.instantiateDialog(SubtitleDisplay, zPosition=-1)
		self.__subtitles_enabled = False

		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evSubtitleListChanged: self.__subtitlesChanged,
				iPlayableService.evEnd: self.__serviceStopped
			})
		self.cached_subtitle_checked = False
		self.__selected_subtitle = None

	def __serviceStopped(self):
		self.cached_subtitle_checked = False
		self.setSubtitlesEnable(False)

	def __subtitlesChanged(self):
		subtitle = self.getCurrentServiceSubtitle()
		sub_count = subtitle and subtitle.getNumberOfSubtitleTracks() or 0
		if self.cached_subtitle_checked != sub_count:
			self.cached_subtitle_checked = sub_count
			if 'TrackAutoselect' not in config.plugins.dict() or config.plugins.TrackAutoselect.subtitle_autoselect_enable.value:
				for idx in range(sub_count):
					info = subtitle.getSubtitleTrackInfo(idx)
					if info.isSaved():
						self.selected_subtitle = idx
						self.subtitles_enabled = True
						return

	def getCurrentServiceSubtitle(self):
		service = self.session.nav.getCurrentService()
		return service and service.subtitleTracks()

	def setSubtitlesEnable(self, enable=True):
		subtitle = self.getCurrentServiceSubtitle()
		if enable:
			if self.__selected_subtitle != None:
				if subtitle and (not self.__subtitles_enabled or self.__selected_subtitle != subtitle.getCurrentSubtitleTrack()):
					subtitle.enableSubtitles(self.subtitle_window.instance, self.__selected_subtitle)
					self.subtitle_window.show()
					self.__subtitles_enabled = True
		else:
			if subtitle:
				subtitle.disableSubtitles(self.subtitle_window.instance)
			self.__selected_subtitle = False
			self.__subtitles_enabled = False
			self.subtitle_window.hide()

	def setSelectedSubtitle(self, idx):
		if isinstance(idx, int):
			self.__selected_subtitle = idx

	subtitles_enabled = property(lambda self: self.__subtitles_enabled, setSubtitlesEnable)
	selected_subtitle = property(lambda self: self.__selected_subtitle, setSelectedSubtitle)

class InfoBarStateInfo(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self["state"] = Label()
		self["message"] = Label()
		self.onFirstExecBegin.append(self.__onFirstExecBegin)
		self._stateSizeDefault = eSize(590,40)
		self._stateSizeFull = eSize(590,130)
		self._stateOnly = False

	def __onFirstExecBegin(self):
		self._stateSizeDefault = self["state"].getSize()
		self._stateSizeFull = eSize( self._stateSizeDefault.width(), self.instance.size().height() - (2 * self["state"].position.x()) )
		self._resizeBoxes()

	def _resizeBoxes(self):
		if self._stateOnly:
			self["state"].resize(self._stateSizeFull)
			self["message"].hide();
		else:
			self["state"].resize(self._stateSizeDefault)
			self["message"].show();

	def setPlaybackState(self, state, message=""):
		self["state"].text = state
		self["message"].text = message
		self._stateOnly = False if message else True
		#self._resizeBoxes()

	def current(self):
		return (self["state"].text, self["message"].text)

class InfoBarServiceErrorPopupSupport:
	STATE_TUNING = _("tuning...")
	STATE_CONNECTING = _("connecting...")
	MESSAGE_WAIT = _("Please wait!")
	STATE_RECONNECTING = _("reconnecting...")

	_stateInfo = None

	def __init__(self):
		Notifications.notificationQueue.registerDomain("ZapError", _("ZapError"), Notifications.ICON_DEFAULT)
		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
			{
				iPlayableService.evServiceChanged: self.__serviceChanged,
				iPlayableService.evTuneFailed: self.__tuneFailed,
				iPlayableService.evStart: self.__serviceStarted,
				iPlayableService.evPlay: self.__servicePlaying,
				iPlayableService.evNotFound: self.__notFound,
				iPlayableService.evUpdatedEventInfo: self.__servicePlaying #just to be sure we're not staying on screen forever
			})
		self._isStream = False
		self._isLiveStream = False
		self._isReconnect = False
		self._currentRef = None
		self.last_error = None
		if not InfoBarServiceErrorPopupSupport._stateInfo:
			InfoBarServiceErrorPopupSupport._stateInfo = self.session.instantiateDialog(InfoBarStateInfo,zPosition=-5)
			InfoBarServiceErrorPopupSupport._stateInfo.neverAnimate()
		self._reconnTimer = eTimer()
		self._reconnTimer_conn = self._reconnTimer.timeout.connect(self._doReconnect)
		self._restoreInfo = None

		self.onShown.append(self.__restoreState)
		self.onExecEnd.append(self.__hideState)
		self.onClose.append(self.__hideState)

		self.__servicePlaying()

	def __restoreState(self):
		Log.i()
		if self.execing and self._restoreInfo:
			self.setPlaybackState(*self._restoreInfo)

	def __hideState(self):
		if InfoBarServiceErrorPopupSupport._stateInfo.shown:
			self._restoreInfo = InfoBarServiceErrorPopupSupport._stateInfo.current()
		InfoBarServiceErrorPopupSupport._stateInfo.hide()

	def setPlaybackState(self, state=None, message=None):
		Log.i("%s %s %s" %(state, message, time()))
		if state or message:
			if self.execing:
				InfoBarServiceErrorPopupSupport._stateInfo.setPlaybackState(state, message)
				InfoBarServiceErrorPopupSupport._stateInfo.show()
				self._restoreInfo = None
			else:
				self._restoreInfo = (state, message)
		else:
			self._restoreInfo = None
			InfoBarServiceErrorPopupSupport._stateInfo.hide()

	def __serviceStarted(self):
		if not self._isStream:
			self.__servicePlaying()
		self.last_error = None

	def __serviceChanged(self):
		ref = self.session.nav.getCurrentServiceReference()
		if not ref:
			self.setPlaybackState()
			return
		path = ref and ref.getPath()
		self._isReconnect = self._currentRef and ref.toCompareString() == self._currentRef.toCompareString()
		if not self._isReconnect:
			self._reconnTimer.stop()
		self._isStream = path and not path.startswith("/")
		self._isLiveStream = self._isStream and (ref and ref.flags & eServiceReference.isLive)
		self._currentRef = ref
		if self._isStream:
			self._pendingState = self.STATE_RECONNECTING if self._isReconnect else self.STATE_CONNECTING
			self.setPlaybackState(self._pendingState, self.MESSAGE_WAIT)

	def __servicePlaying(self):
		Log.w()
		self.setPlaybackState()

	def __notFound(self):
		state = self.STATE_TUNING
		if self._isStream:
			state = self.STATE_RECONNECTING if self._isReconnect else self.STATE_CONNECTING
		self.setPlaybackState(state, _("Service not found!"))
		self._checkReconnect()

	def _doReconnect(self):
		if self._isReconnect:
			self.setPlaybackState(self.STATE_RECONNECTING)
			self.session.nav.playService(self._currentRef, forceRestart=True)

	def _checkReconnect(self):
		Log.w("%s / %s" %(str(self._isReconnect), str(self._isLiveStream)))
		self._isReconnect = self._isLiveStream
		if self._isReconnect:
			self._reconnTimer.startLongTimer(3)

	def __tuneFailed(self):
		service = self.session.nav.getCurrentService()
		info = service and service.info()
		error = info and info.getInfo(iServiceInformation.sDVBState)

		if error == self.last_error:
			error = None
		else:
			self.last_error = error

		error = {
			eDVBServicePMTHandler.eventNoResources: _("No free tuner!"),
			eDVBServicePMTHandler.eventTuneFailed: _("Tune failed!"),
			eDVBServicePMTHandler.eventNoPAT: _("No data on transponder!\n(Timeout reading PAT)"),
			eDVBServicePMTHandler.eventNoPATEntry: _("Service not found!\n(SID not found in PAT)"),
			eDVBServicePMTHandler.eventNoPMT: _("Service invalid!\n(Timeout reading PMT)"),
			eDVBServicePMTHandler.eventNewProgramInfo: None,
			eDVBServicePMTHandler.eventTuned: None,
			eDVBServicePMTHandler.eventSOF: None,
			eDVBServicePMTHandler.eventEOF: None,
			eDVBServicePMTHandler.eventMisconfiguration: _("Service unavailable!\nCheck tuner configuration!"),
		}.get(error) #this returns None when the key not exist in the dict

		if error:
			self.setPlaybackState(self.STATE_TUNING, error)
		else:
			self.setPlaybackState()

class InfoBarGstreamerErrorPopupSupport(object):
	def __init__(self):
		self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
		{
			eServiceMP3.evAudioDecodeError	: self.__evAudioDecodeError,
			eServiceMP3.evVideoDecodeError	: self.__evVideoDecodeError,
			eServiceMP3.evPluginError		: self.__evPluginError,
			eServiceMP3.evStreamingSrcError	: self.__evStreamingSrcError,
			eServiceMP3.evFileReadError		: self.__evFileReadError,
			eServiceMP3.evTypeNotFoundError	: self.__evTypeNotFoundError,
			eServiceMP3.evGeneralGstError	: self.__evGeneralGstError
		})
		self.__messages = {
				eServiceMP3.evAudioDecodeError 	: _("This Dreambox can't decode %s streams!"),
				eServiceMP3.evVideoDecodeError	: _("This Dreambox can't decode %s streams!"),
				eServiceMP3.evPluginError		: "%s",
				eServiceMP3.evStreamingSrcError	: _("Streaming error: %s"),
				eServiceMP3.evFileReadError		: _("Couldn't read file: %s"),
				eServiceMP3.evTypeNotFoundError	: _("Couldn't find media type"),
				eServiceMP3.evGeneralGstError	: _("Gstreamer error: %s")
			}

	def __notify(self, key, hasMessage=True):
		error = self.__messages.get(key)
		if hasMessage:
			currPlay = self.session.nav.getCurrentService()
			error = error %(currPlay.info().getInfoString(iServiceInformation.sErrorText),)
		self.setPlaybackState(self.STATE_CONNECTING, error)

	def __evAudioDecodeError(self):
		self.__notify(eServiceMP3.evAudioDecodeError)

	def __evVideoDecodeError(self):
		self.__notify(eServiceMP3.evVideoDecodeError)

	def __evPluginError(self):
		self.__notify(eServiceMP3.evPluginError)

	def __evStreamingSrcError(self):
		self.__notify(eServiceMP3.evStreamingSrcError)
		self._checkReconnect()

	def __evFileReadError(self):
		self.__notify(eServiceMP3.evFileReadError)
		self._checkReconnect()

	def __evTypeNotFoundError(self):
		self.__notify(eServiceMP3.evTypeNotFoundError, hasMessage=False)

	def __evGeneralGstError(self):
		self.__notify(eServiceMP3.evGeneralGstError)
		self._checkReconnect()
