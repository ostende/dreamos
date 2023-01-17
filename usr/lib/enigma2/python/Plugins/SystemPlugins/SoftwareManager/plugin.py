from __future__ import print_function
from __future__ import absolute_import
from enigma import eNetworkManager

from Plugins.Plugin import PluginDescriptor
from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.Ipkg import Ipkg
from Components.ActionMap import ActionMap, NumberActionMap
from Components.Input import Input
from Components.Ipkg import IpkgComponent
from Components.Sources.StaticText import StaticText
from Components.ScrollLabel import ScrollLabel
from Components.Pixmap import Pixmap
from Components.MenuList import MenuList
from Components.Sources.List import List
from Components.Slider import Slider
from Components.Harddisk import harddiskmanager
from Components.config import config,getConfigListEntry, ConfigSubsection, ConfigText, ConfigLocations, ConfigSelection
from Components.ConfigList import ConfigListScreen
from Components.Console import Console
from Components.SelectionList import SelectionList
from Components.PluginComponent import plugins
from Components.DreamInfoHandler import DreamInfoHandler
from Components.Language import language
from Components.AVSwitch import AVSwitch
from Tools.Directories import resolveFilename, SCOPE_PLUGINS, SCOPE_CURRENT_PLUGIN, SCOPE_CURRENT_SKIN, SCOPE_METADIR
from Tools.LoadPixmap import LoadPixmap
from Tools.NumericalTextInput import NumericalTextInput
from enigma import eTimer, quitMainloop, getDesktop, ePicLoad, getPrevAsciiCode, eEnv
from six.moves.cPickle import dump, load
from os import path as os_path, stat, mkdir, makedirs, listdir, access, remove, W_OK, R_OK, F_OK
from time import time
from stat import ST_MTIME
from twisted.web import client
from re import compile as re_compile

from .ImageWizard import ImageWizard
from .BackupRestore import BackupSelection, RestoreMenu, BackupScreen, RestoreScreen, getBackupPath, getBackupFilename
from .SoftwareTools import iSoftwareTools
from Components.ResourceManager import resourcemanager

from .UpdatePlugin import UpdatePlugin
from .UpdateCheck import updateCheck, UpdateCheckConfig
from six import unichr
from six.moves import range


config.plugins.configurationbackup = ConfigSubsection()
config.plugins.configurationbackup.backuplocation = ConfigText(default = '/media/hdd/', visible_width = 50, fixed_size = False)
config.plugins.configurationbackup.backupdirs = ConfigLocations(default=[eEnv.resolve('${sysconfdir}/enigma2/'), '/etc/hostname'])

config.plugins.softwaremanager = ConfigSubsection()
config.plugins.softwaremanager.overwriteConfigFiles = ConfigSelection(
				[
				 ("Y", _("Yes, always")),
				 ("N", _("No, never"))
				], "Y")

def write_cache(cache_file, cache_data):
	#Does a cPickle dump
	if not os_path.isdir( os_path.dirname(cache_file) ):
		try:
			mkdir( os_path.dirname(cache_file) )
		except OSError:
			print(os_path.dirname(cache_file), 'is a file')
	fd = open(cache_file, 'w')
	dump(cache_data, fd, -1)
	fd.close()

def valid_cache(cache_file, cache_ttl):
	#See if the cache file exists and is still living
	try:
		mtime = stat(cache_file)[ST_MTIME]
	except:
		return 0
	curr_time = time()
	if (curr_time - mtime) > cache_ttl:
		return 0
	else:
		return 1

def load_cache(cache_file):
	#Does a cPickle load
	fd = open(cache_file)
	cache_data = load(fd)
	fd.close()
	return cache_data


class UpdatePluginMenu(Screen):
	skin = """
		<screen name="UpdatePluginMenu" position="center,120" size="820,520" title="Software management" >
			<ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="200,40" />
			<widget source="key_red" render="Label" position="10,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-2,-2"/>
			<eLabel	position="10,50" size="800,1" backgroundColor="grey"/>
			<widget source="menu" render="Listbox" position="10,60" size="420,390" enableWrapAround="1" scrollbarMode="showOnDemand">
				<convert type="TemplatedMultiContent">
					{"template": [
					MultiContentEntryText(pos=(10,2),size=(400,26),flags=RT_HALIGN_LEFT,text=1),# index 0 is the MenuText,
					],
					"fonts": [gFont("Regular",22)],
					"itemHeight": 30
					}
				</convert>
			</widget>
			<eLabel	position="440,50" size="1,430" backgroundColor="grey"/>
			<widget source="menu" render="Listbox" position="450,60" size="360,420" scrollbarMode="showNever" selectionDisabled="1">
				<convert type="TemplatedMultiContent">
					{"template": [
					MultiContentEntryText(pos=(0,0),size=(360,420),flags=RT_HALIGN_CENTER|RT_VALIGN_CENTER|RT_WRAP,text=2),# index 2 is the Description,
					],
					"fonts": [gFont("Regular",22)],
					"itemHeight": 420
					}
				</convert>
			</widget>
			<eLabel	position="10,480" size="800,1" backgroundColor="grey"/>
			<widget source="status" render="Label" position="10,488" size="800,25" font="Regular;22" halign="center" transparent="1"/>
		</screen>"""
		
	def __init__(self, session, args = 0):
		Screen.__init__(self, session)
		self.skin_path = plugin_path
		self.menu = args
		self.list = []
		self.oktext = _("\nPress OK on your remote control to continue.")
		self.menutext = _("Press MENU on your remote control for additional options.")
		self.infotext = _("Press INFO on your remote control for additional information.")
		self.text = ""
		self.device_name = iSoftwareTools.hardware_info.device_name
		self.backupdirs = ' '.join( config.plugins.configurationbackup.backupdirs.value )
		if self.menu == 0:
			print("building menu entries")
			self.list.append(("install-extensions", _("Manage extensions"), _("\nManage extensions or plugins for your Dreambox" ) + self.oktext, None))
			self.list.append(("software-update", _("Software update"), _("\nOnline update of your Dreambox software." ) + self.oktext, None))
			self.list.append(("software-restore", _("Software restore"), _("\nRestore your Dreambox with a new firmware." ) + self.oktext, None))
			self.list.append(("system-backup", _("Backup system settings"), _("\nBackup your Dreambox settings." ) + self.oktext + "\n\n" + self.infotext, None))
			self.list.append(("system-restore",_("Restore system settings"), _("\nRestore your Dreambox settings." ) + self.oktext, None))
			self.list.append(("ipkg-install", _("Install local extension"),  _("\nScan for local extensions and install them." ) + self.oktext, None))
			self.list.append(("update-checker", _("Automatic update checks"),  _("\nCheck software updates periodically." ) + self.oktext, None))
			for p in plugins.getPlugins(PluginDescriptor.WHERE_SOFTWAREMANAGER):
				if "SoftwareSupported" in p.__call__:
					callFnc = p.__call__["SoftwareSupported"]
					if callFnc is not None:
						if "menuEntryName" in p.__call__:
							menuEntryName = p.__call__["menuEntryName"]
						else:
							menuEntryName = _('Extended Software')
						if "menuEntryDescription" in p.__call__:
							menuEntryDescription = p.__call__["menuEntryDescription"]
						else:
							menuEntryDescription = _('Extended Software Plugin')
						self.list.append(('default-plugin', menuEntryName, menuEntryDescription + self.oktext, callFnc))
			if config.usage.setup_level.index >= 2: # expert+
				self.list.append(("advanced", _("Advanced Options"), _("\nAdvanced options and settings." ) + self.oktext, None))
		elif self.menu == 1:
			self.list.append(("advancedrestore", _("Advanced restore"), _("\nRestore your backups by date." ) + self.oktext, None))
			self.list.append(("backuplocation", _("Choose backup location"),  _("\nSelect your backup device.\nCurrent device: " ) + config.plugins.configurationbackup.backuplocation.value + self.oktext, None))
			self.list.append(("backupfiles", _("Choose backup files"),  _("Select files for backup.") + self.oktext + "\n\n" + self.infotext, None))
			if config.usage.setup_level.index >= 2: # expert+
				self.list.append(("ipkg-manager", _("Packet management"),  _("\nView, install and remove available or installed packages." ) + self.oktext, None))
			self.list.append(("ipkg-source",_("Choose upgrade source"), _("\nEdit the upgrade source address." ) + self.oktext, None))
			for p in plugins.getPlugins(PluginDescriptor.WHERE_SOFTWAREMANAGER):
				if "AdvancedSoftwareSupported" in p.__call__:
					callFnc = p.__call__["AdvancedSoftwareSupported"]
					if callFnc is not None:
						if "menuEntryName" in p.__call__:
							menuEntryName = p.__call__["menuEntryName"]
						else:
							menuEntryName = _('Advanced Software')
						if "menuEntryDescription" in p.__call__:
							menuEntryDescription = p.__call__["menuEntryDescription"]
						else:
							menuEntryDescription = _('Advanced Software Plugin')
						self.list.append(('advanced-plugin', menuEntryName, menuEntryDescription + self.oktext, callFnc))

		self["menu"] = List(self.list)
		self["key_red"] = StaticText(_("Close"))
		self["status"] = StaticText(self.menutext)

		self["shortcuts"] = ActionMap(["ShortcutActions", "WizardActions", "InfobarEPGActions", "MenuActions"],
		{
			"ok": self.go,
			"back": self.close,
			"red": self.close,
			"menu": self.handleMenu,
			"showEventInfo": self.handleInfo,
		}, -1)
		self.onLayoutFinish.append(self.layoutFinished)
		self.backuppath = getBackupPath()
		self.backupfile = getBackupFilename()
		self.fullbackupfilename = self.backuppath + "/" + self.backupfile
		self.onShown.append(self.setWindowTitle)

	def layoutFinished(self):
		idx = 0
		self["menu"].index = idx

	def setWindowTitle(self):
		self.setTitle(_("Software management"))

	def handleMenu(self):
		self.session.open(SoftwareManagerSetup)
		
	def handleInfo(self):
		current = self["menu"].getCurrent()
		if current:
			currentEntry = current[0]
			if currentEntry in ("system-backup","backupfiles"):
				self.session.open(SoftwareManagerInfo, mode = "backupinfo")

	def go(self):
		current = self["menu"].getCurrent()
		if current:
			currentEntry = current[0]
			if self.menu == 0:
				if currentEntry == "update-checker":
					self.session.open(UpdateCheckConfig)
				if (currentEntry == "software-update"):
					self.session.openWithCallback(self.runUpgrade, MessageBox, _("Do you want to update your Dreambox?")+"\n"+_("\nAfter pressing OK, please wait!"))
				elif (currentEntry == "software-restore"):
					self.session.open(ImageWizard)
				elif (currentEntry == "install-extensions"):
					self.session.open(PluginManager, self.skin_path)
				elif (currentEntry == "system-backup"):
					self.session.openWithCallback(self.backupDone,BackupScreen, runBackup = True)
				elif (currentEntry == "system-restore"):
					if os_path.exists(self.fullbackupfilename):
						self.session.openWithCallback(self.startRestore, MessageBox, _("Are you sure you want to restore your Enigma2 backup?\nEnigma2 will restart after the restore"))
					else:
						self.session.open(MessageBox, _("Sorry no backups found!"), MessageBox.TYPE_INFO, timeout = 10)
				elif (currentEntry == "ipkg-install"):
					try:
						from Plugins.Extensions.MediaScanner.plugin import main
						main(self.session)
					except:
						self.session.open(MessageBox, _("Sorry MediaScanner is not installed!"), MessageBox.TYPE_INFO, timeout = 10)
				elif (currentEntry == "default-plugin"):
					self.extended = current[3]
					self.extended(self.session, None)
				elif (currentEntry == "advanced"):
					self.session.open(UpdatePluginMenu, 1)
			elif self.menu == 1:
				if (currentEntry == "ipkg-manager"):
					self.session.open(PacketManager, self.skin_path)
				elif (currentEntry == "backuplocation"):
					parts = [ (r.description, r.mountpoint, self.session) for r in harddiskmanager.getMountedPartitions(onlyhotplug = False)]
					for x in parts:
						if not access(x[1], F_OK|R_OK|W_OK) or x[1] == '/':
							parts.remove(x)
					if len(parts):
						self.session.openWithCallback(self.backuplocation_chosen, ChoiceBox, title = _("Please select medium to use as backup location"), list = parts)
				elif (currentEntry == "backupfiles"):
					self.session.openWithCallback(self.backupfiles_chosen,BackupSelection)
				elif (currentEntry == "advancedrestore"):
					self.session.open(RestoreMenu, self.skin_path)
				elif (currentEntry == "ipkg-source"):
					self.session.open(IPKGMenu, self.skin_path)
				elif (currentEntry == "advanced-plugin"):
					self.extended = current[3]
					self.extended(self.session, None)

	def backupfiles_chosen(self, ret):
		self.backupdirs = ' '.join( config.plugins.configurationbackup.backupdirs.value )
		config.plugins.configurationbackup.backupdirs.save()
		config.plugins.configurationbackup.save()
		
	def backuplocation_chosen(self, option):
		oldpath = config.plugins.configurationbackup.backuplocation.getValue()
		if option is not None:
			config.plugins.configurationbackup.backuplocation.value = str(option[1])
		config.plugins.configurationbackup.backuplocation.save()
		config.plugins.configurationbackup.save()
		newpath = config.plugins.configurationbackup.backuplocation.getValue()
		if newpath != oldpath:
			self.createBackupfolders()

	def runUpgrade(self, result):
		if result:
			self.session.open(UpdatePlugin, self.skin_path)

	def createBackupfolders(self):
		print("Creating backup folder if not already there...")
		self.backuppath = getBackupPath()
		try:
			if (os_path.exists(self.backuppath) == False):
				makedirs(self.backuppath)
		except OSError:
			self.session.open(MessageBox, _("Sorry, your backup destination is not writeable.\n\nPlease choose another one."), MessageBox.TYPE_INFO, timeout = 10)

	def backupDone(self,retval = None):
		if retval is True:
			self.session.open(MessageBox, _("Backup done."), MessageBox.TYPE_INFO, timeout = 10)
		else:
			self.session.open(MessageBox, _("Backup failed."), MessageBox.TYPE_INFO, timeout = 10)

	def startRestore(self, ret = False):
		if ret:
			self.exe = True
			self.session.open(RestoreScreen, runRestore = True)

class SoftwareManagerSetup(Screen, ConfigListScreen):
	skin = """
		<screen name="SoftwareManagerSetup" position="center,120" size="820,520" title="SoftwareManager setup">
			<ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="200,40"  />
			<ePixmap pixmap="skin_default/buttons/green.png" position="210,5" size="200,40"  />
			<widget source="key_red" render="Label" position="10,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-2,-2" />
			<widget source="key_green" render="Label" position="210,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-2,-2" />
			<eLabel position="10,50" size="800,1" backgroundColor="grey" />
			<widget name="config" position="10,55" size="800,420" enableWrapAround="1" scrollbarMode="showOnDemand" />
			<eLabel position="10,480" size="800,1" backgroundColor="grey" />
			<widget source="introduction" render="Label" position="10,488" size="800,25" font="Regular;22" halign="center" />
		</screen>"""

	def __init__(self, session, skin_path = None):
		Screen.__init__(self, session)
		self.session = session
		self.skin_path = skin_path
		if self.skin_path == None:
			self.skin_path = resolveFilename(SCOPE_CURRENT_PLUGIN, "SystemPlugins/SoftwareManager")

		self.onChangedEntry = [ ]
		self.setup_title = _("Software manager setup")
		self.overwriteConfigfilesEntry = None

		self.list = [ ]
		ConfigListScreen.__init__(self, self.list, session = session, on_change = self.changedEntry)

		self["actions"] = ActionMap(["SetupActions"],
			{
				"cancel": self.keyCancel,
				"save": self.apply,
			}, -2)

		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("OK"))
		self["key_yellow"] = StaticText()
		self["key_blue"] = StaticText()
		self["introduction"] = StaticText()

		self.createSetup()
		self.onLayoutFinish.append(self.layoutFinished)

	def layoutFinished(self):
		self.setTitle(self.setup_title)

	def createSetup(self):
		self.list = [ ]
		self.overwriteConfigfilesEntry = getConfigListEntry(_("Overwrite configuration files ?"), config.plugins.softwaremanager.overwriteConfigFiles)
		self.list.append(self.overwriteConfigfilesEntry)	
		self["config"].list = self.list
		self["config"].l.setSeparation(400)
		self["config"].l.setList(self.list)
		if not self.selectionChanged in self["config"].onSelectionChanged:
			self["config"].onSelectionChanged.append(self.selectionChanged)
		self.selectionChanged()

	def selectionChanged(self):
		if self["config"].getCurrent() == self.overwriteConfigfilesEntry:
			self["introduction"].setText(_("Overwrite configuration files during software upgrade?"))
		else:
			self["introduction"].setText("")

	def newConfig(self):
		pass

	def keyLeft(self):
		ConfigListScreen.keyLeft(self)

	def keyRight(self):
		ConfigListScreen.keyRight(self)

	def confirm(self, confirmed):
		if not confirmed:
			print("not confirmed")
			return
		else:
			self.keySave()

	def apply(self):
		self.session.openWithCallback(self.confirm, MessageBox, _("Use this settings?"), MessageBox.TYPE_YESNO, timeout = 20, default = True)

	def cancelConfirm(self, result):
		if not result:
			return
		for x in self["config"].list:
			x[1].cancel()
		self.close()

	def keyCancel(self):
		if self["config"].isChanged():
			self.session.openWithCallback(self.cancelConfirm, MessageBox, _("Really close without saving settings?"), MessageBox.TYPE_YESNO, timeout = 20, default = True)
		else:
			self.close()

	# for summary:
	def changedEntry(self):
		for x in self.onChangedEntry:
			x()
		self.selectionChanged()

	def getCurrentEntry(self):
		return self["config"].getCurrent()[0]

	def getCurrentValue(self):
		return str(self["config"].getCurrent()[1].value)

	def createSummary(self):
		from Screens.Setup import SetupSummary
		return SetupSummary


class SoftwareManagerInfo(Screen):
	skin = """
		<screen name="SoftwareManagerInfo" position="center,120" size="820,520" title=" ">
			<ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="200,40"  />
			<widget source="key_red" render="Label" position="10,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-2,-2" />
			<eLabel position="10,50" size="800,1" backgroundColor="grey" />
			<widget source="list" render="Listbox" position="10,55" size="800,420" enableWrapAround="1" scrollbarMode="showOnDemand">
				<convert type="TemplatedMultiContent">
					{"template": [
					MultiContentEntryText(pos=(5,3),size=(790,30),font=0,flags=RT_HALIGN_CENTER,text=0),# index 0 is the name
					],
					"fonts": [gFont("Regular",22)],
					"itemHeight": 30
					}
				</convert>
			</widget>
			<eLabel position="10,480" size="800,1" backgroundColor="grey" />
			<widget source="introduction" render="Label" position="10,488" size="800,25" font="Regular;22" halign="center" />
		</screen>"""

	def __init__(self, session, skin_path = None, mode = None):
		Screen.__init__(self, session)
		self.session = session
		self.mode = mode
		self.skin_path = skin_path
		if self.skin_path == None:
			self.skin_path = resolveFilename(SCOPE_CURRENT_PLUGIN, "SystemPlugins/SoftwareManager")

		self["actions"] = ActionMap(["ShortcutActions", "WizardActions"],
			{
				"back": self.close,
				"red": self.close,
			}, -2)

		self.list = []
		self["list"] = List(self.list)
		
		self["key_red"] = StaticText(_("Close"))
		self["key_green"] = StaticText()
		self["key_yellow"] = StaticText()
		self["key_blue"] = StaticText()
		self["introduction"] = StaticText()

		self.onLayoutFinish.append(self.layoutFinished)

	def layoutFinished(self):
		self.setTitle(_("Softwaremanager information"))
		if self.mode is not None:
			self.showInfos()

	def showInfos(self):
		if self.mode == "backupinfo":
			self.list = []
			backupfiles = config.plugins.configurationbackup.backupdirs.value
			for entry in backupfiles:
				self.list.append((entry,))
			self['list'].setList(self.list)

sqsh_re = None

def pendingSqshImgInstall():
	global sqsh_re
	if sqsh_re is None:
		sqsh_re = re_compile('^\.u*mount_.+_needed$')
	for f in listdir('/var/tmp'):
		if sqsh_re.match(f):
			return True
	return False

class PluginManager(Screen, DreamInfoHandler):
	skin = """
		<screen name="PluginManager" position="center,120" size="820,520" title="Extensions management">
			<ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="260,40" scale="stretch"/>
			<ePixmap pixmap="skin_default/buttons/green.png" position="280,5" size="260,40" scale="stretch"/>
			<ePixmap pixmap="skin_default/buttons/yellow.png" position="550,5" size="260,40" scale="stretch"/>
			<widget source="key_red" render="Label" position="10,5" size="260,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-2,-2" />
			<widget source="key_green" render="Label" position="280,5" size="260,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-2,-2" />
			<widget source="key_yellow" render="Label" position="550,5" size="260,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-2,-2" />
			<eLabel	position="10,50" size="800,1" backgroundColor="grey"/>
			<widget source="status" render="Label" position="10,55" size="800,25" font="Regular;22" halign="center" transparent="1"/>
			<eLabel	position="10,85" size="800,1" backgroundColor="grey"/>
			<widget source="list" render="Listbox" position="10,95" size="800,420" enableWrapAround="1" scrollbarMode="showOnDemand">
				<convert type="TemplatedMultiContent">
				{"templates":
					{"default": (60,[
							MultiContentEntryText(pos=(60,2),size=(710,28),font=0,flags=RT_HALIGN_LEFT,text=0),# index 0 is the name
							MultiContentEntryText(pos=(70,33),size=(700,20),font=1,flags=RT_HALIGN_LEFT,text=2),# index 2 is the description
							MultiContentEntryPixmapAlphaTest(pos=(5,5),size=(48,48),png=5),# index 5 is the status pixmap
							MultiContentEntryPixmapAlphaTest(pos=(0,59),size=(800,1),png=6),# index 6 is the div pixmap
						]),
					"category": (60,[
							MultiContentEntryText(pos=(10,2),size=(760,28),font=0,flags=RT_HALIGN_LEFT,text=0),# index 0 is the name
							MultiContentEntryText(pos=(20,33),size=(750,20),font=1,flags=RT_HALIGN_LEFT,text=1),# index 1 is the description
							MultiContentEntryPixmapAlphaTest(pos=(0,59),size=(800,1),png=3),# index 3 is the div pixmap
						])
					},
					"fonts": [gFont("Regular",24),gFont("Regular",18)],
					"itemHeight": 60
				}
				</convert>
			</widget>
		</screen>"""

	def __init__(self, session, plugin_path = None, args = None):
		Screen.__init__(self, session)
		self.session = session
		self.skin_path = plugin_path
		if self.skin_path == None:
			self.skin_path = resolveFilename(SCOPE_CURRENT_PLUGIN, "SystemPlugins/SoftwareManager")

		self["shortcuts"] = ActionMap(["ShortcutActions", "WizardActions", "InfobarEPGActions", "HelpActions" ],
		{
			"ok": self.handleCurrent,
			"back": self.exit,
			"red": self.exit,
			"green": self.handleCurrent,
			"yellow": self.handleSelected,
			"showEventInfo": self.handleSelected,
			"displayHelp": self.handleHelp,
		}, -1)

		self.list = []
		self.statuslist = []
		self.selectedFiles = []
		self.categoryList = []
		self.packetlist = []
		self["list"] = List(self.list)
		self["key_red"] = StaticText(_("Close"))
		self["key_green"] = StaticText("")
		self["key_yellow"] = StaticText("")
		self["key_blue"] = StaticText("")
		self["status"] = StaticText("")

		self.cmdList = []
		self.oktext = _("\nAfter pressing OK, please wait!")
		if not self.selectionChanged in self["list"].onSelectionChanged:
			self["list"].onSelectionChanged.append(self.selectionChanged)

		self.currList = ""
		self.currentSelectedTag = None
		self.currentSelectedIndex = None
		self.currentSelectedPackage = None
		self.saved_currentSelectedPackage = None
		self.restartRequired = False
		self.rebootRequired = False
		self.device_name = iSoftwareTools.hardware_info.device_name

		self.onShown.append(self.setWindowTitle)
		self.onLayoutFinish.append(self.getUpdateInfos)
		self.onClose.append(iSoftwareTools.cleanupSoftwareTools)

	def setWindowTitle(self):
		self.setTitle(_("Extensions management"))

	def exit(self):
		if self.currList == "packages":
			self.currList = "category"
			self.currentSelectedTag = None
			self["list"].style = "category"
			self['list'].setList(self.categoryList)
			self["list"].setIndex(self.currentSelectedIndex)
			self["list"].updateList(self.categoryList)
			self.selectionChanged()
		else:
			self.prepareInstall()
			if len(self.cmdList):
				self.session.openWithCallback(self.runExecute, PluginManagerInfo, self.skin_path, self.cmdList)
			else:
				self.close()

	def handleHelp(self):
		if self.currList != "status":
			self.session.open(PluginManagerHelp, self.skin_path)

	def setState(self,status = None):
		if status:
			self.currList = "status"
			self.statuslist = []
			self["key_green"].setText("")
			self["key_blue"].setText("")
			self["key_yellow"].setText("")
			divpng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "skin_default/div-h.png"))
			if status == 'update':
				statuspng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_PLUGIN, "SystemPlugins/SoftwareManager/upgrade.png"))
				self.statuslist.append(( _("Updating software catalog"), '', _("Searching for available updates. Please wait..." ),'', '', statuspng, divpng, None, '' ))
			elif status == 'sync':
				statuspng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_PLUGIN, "SystemPlugins/SoftwareManager/upgrade.png"))
				self.statuslist.append(( _("Package list update"), '', _("Searching for new installed or removed packages. Please wait..." ),'', '', statuspng, divpng, None, '' ))
			elif status == 'error':
				self["key_green"].setText(_("Continue"))
				statuspng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_PLUGIN, "SystemPlugins/SoftwareManager/remove.png"))
				self.statuslist.append(( _("Error"), '', _("There was an error downloading the packetlist. Please try again." ),'', '', statuspng, divpng, None, '' ))
			self["list"].style = "default"
			self['list'].setList(self.statuslist)


	def getUpdateInfos(self):
		if (iSoftwareTools.lastDownloadDate is not None and iSoftwareTools.NetworkConnectionAvailable is False):
			self.rebuildList()
		else:
			self.setState('update')
			iSoftwareTools.startSoftwareTools(self.getUpdateInfosCB)

	def getUpdateInfosCB(self, retval = None):
		if retval is not None:
			if retval is True:
				if iSoftwareTools.available_updates is not 0:
					self["status"].setText(_("There are at least ") + str(iSoftwareTools.available_updates) + _(" updates available."))
				else:
					self["status"].setText(_("There are no updates available."))
				self.rebuildList()
			elif retval is False:
				if iSoftwareTools.lastDownloadDate is None:
					self.setState('error')
					if iSoftwareTools.NetworkConnectionAvailable:
						self["status"].setText(_("Updatefeed not available."))
					else:
						self["status"].setText(_("No network connection available."))
				else:
					iSoftwareTools.lastDownloadDate = time()
					iSoftwareTools.list_updating = True
					self.setState('update')
					iSoftwareTools.getUpdates(self.getUpdateInfosCB)

	def rebuildList(self, retval = None):
		if self.currentSelectedTag is None:
			self.buildCategoryList()
		else:
			self.buildPacketList(self.currentSelectedTag)

	def selectionChanged(self):
		current = self["list"].getCurrent()
		self["status"].setText("")
		if current:
			if self.currList == "packages":
				self["key_red"].setText(_("Back"))
				if current[4] == 'installed':
					self["key_green"].setText(_("Uninstall"))
				elif current[4] == 'installable':
					self["key_green"].setText(_("Install"))
					if iSoftwareTools.NetworkConnectionAvailable is False:
						self["key_green"].setText("")
				elif current[4] == 'remove':
					self["key_green"].setText(_("Undo uninstall"))
				elif current[4] == 'install':
					self["key_green"].setText(_("Undo install"))
					if iSoftwareTools.NetworkConnectionAvailable is False:
						self["key_green"].setText("")
				self["key_yellow"].setText(_("View details"))
				self["key_blue"].setText("")
				if len(self.selectedFiles) == 0 and iSoftwareTools.available_updates is not 0:
					self["status"].setText(_("There are at least ") + str(iSoftwareTools.available_updates) + _(" updates available."))
				elif len(self.selectedFiles) is not 0:
					self["status"].setText(str(len(self.selectedFiles)) + _(" packages selected."))
				else:
					self["status"].setText(_("There are currently no outstanding actions."))
			elif self.currList == "category":
				self["key_red"].setText(_("Close"))
				self["key_green"].setText("")
				self["key_yellow"].setText("")
				self["key_blue"].setText("")
				if len(self.selectedFiles) == 0 and iSoftwareTools.available_updates is not 0:
					self["status"].setText(_("There are at least ") + str(iSoftwareTools.available_updates) + _(" updates available."))
					self["key_yellow"].setText(_("Update"))
				elif len(self.selectedFiles) is not 0:
					self["status"].setText(str(len(self.selectedFiles)) + _(" packages selected."))
					self["key_yellow"].setText(_("Process"))
				else:
					self["status"].setText(_("There are currently no outstanding actions."))

	def getSelectionState(self, detailsFile):
		for entry in self.selectedFiles:
			if entry[0] == detailsFile:
				return True
		return False

	def handleCurrent(self):
		current = self["list"].getCurrent()
		if current:
			if self.currList == "category":
				self.currentSelectedIndex = self["list"].index
				selectedTag = current[2]
				self.buildPacketList(selectedTag)
			elif self.currList == "packages":
				if current[7] is not '':
					idx = self["list"].getIndex()
					detailsFile = self.list[idx][1]
					if self.list[idx][7] == True:
						for entry in self.selectedFiles:
							if entry[0] == detailsFile:
								self.selectedFiles.remove(entry)
					else:
						alreadyinList = False
						for entry in self.selectedFiles:
							if entry[0] == detailsFile:
								alreadyinList = True
						if not alreadyinList:
							if (iSoftwareTools.NetworkConnectionAvailable is False and current[4] in ('installable','install')):
								pass
							else:
								self.selectedFiles.append((detailsFile,current[4],current[3]))
								self.currentSelectedPackage = ((detailsFile,current[4],current[3]))
					if current[4] == 'installed':
						self.list[idx] = self.buildEntryComponent(current[0], current[1], current[2], current[3], 'remove', True)
					elif current[4] == 'installable':
						if iSoftwareTools.NetworkConnectionAvailable:
							self.list[idx] = self.buildEntryComponent(current[0], current[1], current[2], current[3], 'install', True)
					elif current[4] == 'remove':
						self.list[idx] = self.buildEntryComponent(current[0], current[1], current[2], current[3], 'installed', False)
					elif current[4] == 'install':
						if iSoftwareTools.NetworkConnectionAvailable:
							self.list[idx] = self.buildEntryComponent(current[0], current[1], current[2], current[3], 'installable',False)
					self["list"].setList(self.list)
					self["list"].setIndex(idx)
					self["list"].updateList(self.list)
					self.selectionChanged()
			elif self.currList == "status":
				iSoftwareTools.lastDownloadDate = time()
				iSoftwareTools.list_updating = True
				self.setState('update')
				iSoftwareTools.getUpdates(self.getUpdateInfosCB)
				
	def handleSelected(self):
		current = self["list"].getCurrent()
		if current:
			if self.currList == "packages":
				if current[7] is not '':
					self.saved_currentSelectedPackage = self.currentSelectedPackage
					self.session.openWithCallback(self.detailsClosed, PluginDetails, self.skin_path, current)
			elif self.currList == "category":
				self.prepareInstall()
				if len(self.cmdList):
					self.session.openWithCallback(self.runExecute, PluginManagerInfo, self.skin_path, self.cmdList)

	def detailsClosed(self, result = None):
		if result is not None:
			if result is not False:
				self.setState('sync')
				iSoftwareTools.lastDownloadDate = time()
				for entry in self.selectedFiles:
					if entry == self.saved_currentSelectedPackage:
						self.selectedFiles.remove(entry)
				iSoftwareTools.startIpkgListInstalled(self.rebuildList)

	def buildEntryComponent(self, name, details, description, packagename, state, selected = False):
		divpng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "skin_default/div-h.png"))
		installedpng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_PLUGIN, "SystemPlugins/SoftwareManager/installed.png"))
		installablepng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_PLUGIN, "SystemPlugins/SoftwareManager/installable.png"))
		removepng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_PLUGIN, "SystemPlugins/SoftwareManager/remove.png"))
		installpng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_PLUGIN, "SystemPlugins/SoftwareManager/install.png"))
		if state == 'installed':
			return((name, details, description, packagename, state, installedpng, divpng, selected))
		elif state == 'installable':
			return((name, details, description, packagename, state, installablepng, divpng, selected))
		elif state == 'remove':
			return((name, details, description, packagename, state, removepng, divpng, selected))
		elif state == 'install':
			return((name, details, description, packagename, state, installpng, divpng, selected))

	def buildPacketList(self, categorytag = None):
		if categorytag is not None:
			self.currList = "packages"
			self.currentSelectedTag = categorytag
			self.packetlist = []
			for package in iSoftwareTools.packagesIndexlist[:]:
				prerequisites = package[0]["prerequisites"]
				if "tag" in prerequisites:
					for foundtag in prerequisites["tag"]:
						if categorytag == foundtag:
							attributes = package[0]["attributes"]
							if "packagetype" in attributes:
								if attributes["packagetype"] == "internal":
									continue
								self.packetlist.append([attributes["name"], attributes["details"], attributes["shortdescription"], attributes["packagename"]])
							else:
								self.packetlist.append([attributes["name"], attributes["details"], attributes["shortdescription"], attributes["packagename"]])
			self.list = []
			for x in self.packetlist:
				status = ""
				name = x[0].strip()
				details = x[1].strip()
				description = x[2].strip()
				if description == "":
					description = "No description available."
				packagename = x[3].strip()
				selectState = self.getSelectionState(details)
				if packagename in iSoftwareTools.installed_packetlist:
					if selectState == True:
						status = "remove"
					else:
						status = "installed"
					self.list.append(self.buildEntryComponent(name, _(details), _(description), packagename, status, selected = selectState))
				else:
					if selectState == True:
						status = "install"
					else:
						status = "installable"
					self.list.append(self.buildEntryComponent(name, _(details), _(description), packagename, status, selected = selectState))
			if len(self.list):
				self.list.sort(key=lambda x: x[0])
			self["list"].style = "default"
			self['list'].setList(self.list)
			self["list"].updateList(self.list)
			self.selectionChanged()

	def buildCategoryList(self):
		self.currList = "category"
		self.categories = []
		self.categoryList = []
		for package in iSoftwareTools.packagesIndexlist[:]:
			prerequisites = package[0]["prerequisites"]
			if "tag" in prerequisites:
				for foundtag in prerequisites["tag"]:
					if foundtag not in self.categories:
						self.categories.append(foundtag)
						self.categoryList.append(self.buildCategoryComponent(foundtag))
		self.categoryList.sort(key=lambda x: x[0])
		self["list"].style = "category"
		self['list'].setList(self.categoryList)
		self["list"].updateList(self.categoryList)
		self.selectionChanged()

	def buildCategoryComponent(self, tag = None):
		divpng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "skin_default/div-h.png"))
		if tag is not None:
			if tag == 'System':
				return(( _("System"), _("View list of available system extensions" ), tag, divpng ))
			elif tag == 'Skin':
				return(( _("Skins"), _("View list of available skins" ), tag, divpng ))
			elif tag == 'Recording':
				return(( _("Recordings"), _("View list of available recording extensions" ), tag, divpng ))
			elif tag == 'Network':
				return(( _("Network"), _("View list of available networking extensions" ), tag, divpng ))
			elif tag == 'CI':
				return(( _("CommonInterface"), _("View list of available CommonInterface extensions" ), tag, divpng ))
			elif tag == 'Default':
				return(( _("Default Settings"), _("View list of available default settings" ), tag, divpng ))
			elif tag == 'SAT':
				return(( _("Satellite equipment"), _("View list of available Satellite equipment extensions." ), tag, divpng ))
			elif tag == 'Software':
				return(( _("Software"), _("View list of available software extensions" ), tag, divpng ))
			elif tag == 'Multimedia':
				return(( _("Multimedia"), _("View list of available multimedia extensions." ), tag, divpng ))
			elif tag == 'Display':
				return(( _("Display and Userinterface"), _("View list of available Display and Userinterface extensions." ), tag, divpng ))
			elif tag == 'EPG':
				return(( _("Electronic Program Guide"), _("View list of available EPG extensions." ), tag, divpng ))
			elif tag == 'Communication':
				return(( _("Communication"), _("View list of available communication extensions." ), tag, divpng ))
			else: # dynamically generate non existent tags
				return(( str(tag), _("View list of available ") + str(tag) + _(" extensions." ), tag, divpng ))

	def prepareInstall(self):
		self.cmdList = []
		if iSoftwareTools.available_updates > 0:
			upgrade_args = {'use_maintainer' : True, 'test_only': False}
			if config.plugins.softwaremanager.overwriteConfigFiles.value == 'N':
				upgrade_args = {'use_maintainer' : False, 'test_only': False}
			self.cmdList.append((IpkgComponent.CMD_UPGRADE, upgrade_args))
		if self.selectedFiles and len(self.selectedFiles):
			for plugin in self.selectedFiles:
				detailsfile = plugin[0]
				if os_path.exists(detailsfile):
					self.package = iSoftwareTools.getPackageDetails(detailsfile)
					self.attributes = self.package["attributes"]
					if "needsRestart" in self.attributes:
						self.restartRequired = True
					if "package" in self.attributes:
						self.packagefiles = self.attributes["package"]
					if plugin[1] == 'installed':
						if self.packagefiles:
							for package in self.packagefiles[:]:
								self.cmdList.append((IpkgComponent.CMD_REMOVE, { "autoremove": True, "package": package["name"] }))
						else:
							self.cmdList.append((IpkgComponent.CMD_REMOVE, { "autoremove": True, "package": plugin[2] }))
					else:
						if self.packagefiles:
							for package in self.packagefiles[:]:
								self.cmdList.append((IpkgComponent.CMD_INSTALL, { "package": package["name"] }))
						else:
							self.cmdList.append((IpkgComponent.CMD_INSTALL, { "package": plugin[2] }))
				else:
					if plugin[1] == 'installed':
						self.cmdList.append((IpkgComponent.CMD_REMOVE, { "autoremove": True, "package": plugin[2] }))
					else:
						self.cmdList.append((IpkgComponent.CMD_INSTALL, { "package": plugin[2] }))

	def runExecute(self, result = None):
		if result is not None:
			if result[0] is True:
				self.session.openWithCallback(self.runExecuteFinished, Ipkg, cmdList = self.cmdList)
			elif result[0] is False:
				self.cmdList = result[1]
				self.session.openWithCallback(self.runExecuteFinished, Ipkg, cmdList = self.cmdList)
		else:
			self.close()

	def runExecuteFinished(self):
		self.reloadPluginlist()

		if plugins.restartRequired or self.restartRequired or pendingSqshImgInstall():
			self.session.openWithCallback(self.ExecuteReboot, MessageBox, _("Install or remove finished.") +" "+_("Do you want to reboot your Dreambox?"), MessageBox.TYPE_YESNO)
		else:
			self.selectedFiles = []
			self.restartRequired = False
			self.detailsClosed(True)

	def ExecuteReboot(self, result):
		if result:
			quitMainloop(3)
		else:
			self.selectedFiles = []
			self.restartRequired = False
			self.detailsClosed(True)

	def reloadPluginlist(self):
		plugins.readPluginList(resolveFilename(SCOPE_PLUGINS))


class PluginManagerInfo(Screen):
	skin = """
		<screen name="PluginManagerInfo" position="center,120" size="820,520" title="Plugin manager activity information">
			<ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="200,40" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="210,5" size="200,40" />
			<widget source="key_red" render="Label" position="10,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-2,-2"/>
			<widget source="key_green" render="Label" position="210,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-2,-2"/>
			<eLabel position="10,50" size="800,1" backgroundColor="grey"/>
			<widget source="status" render="Label" position="10,55" size="800,25" font="Regular;22" halign="center" transparent="1"/>
			<eLabel	position="10,85" size="800,1" backgroundColor="grey"/>
			<widget source="list" render="Listbox" position="10,95" size="800,420" enableWrapAround="1" scrollbarMode="showOnDemand">
				<convert type="TemplatedMultiContent">
					{"template": [
					MultiContentEntryText(pos=(100,2),size=(630,28),font=0,flags=RT_HALIGN_LEFT,text=0),# index 0 is the name
					MultiContentEntryText(pos=(100,33),size=(630,20),font=1,flags=RT_HALIGN_LEFT,text=1),# index 1 is the state
					MultiContentEntryPixmapAlphaTest(pos=(15,5),size=(48,48),png=2),# index 2 is the status pixmap
					MultiContentEntryPixmapAlphaTest(pos=(0,59),size=(800,1),png=3),# index 3 is the div pixmap
					],
					"fonts": [gFont("Regular",24),gFont("Regular",18)],
					"itemHeight": 60
					}
				</convert>
			</widget>
		</screen>"""

	def __init__(self, session, plugin_path, cmdlist = None):
		Screen.__init__(self, session)
		self.session = session
		self.skin_path = plugin_path
		self.cmdlist = cmdlist

		self["shortcuts"] = ActionMap(["ShortcutActions", "WizardActions"],
		{
			"ok": self.process_all,
			"back": self.exit,
			"red": self.exit,
			"green": self.process_extensions,
		}, -1)

		self.list = []
		self["list"] = List(self.list)
		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("Only extensions."))
		self["status"] = StaticText(_("Following tasks will be done after you press OK!"))

		self.onShown.append(self.setWindowTitle)
		self.onLayoutFinish.append(self.rebuildList)

	def setWindowTitle(self):
		self.setTitle(_("Plugin manager activity information"))

	def rebuildList(self):
		self.list = []
		if self.cmdlist is not None:
			for entry in self.cmdlist:
				action = ""
				info = ""
				cmd = entry[0]
				if cmd == 0:
					action = 'install'
				elif cmd == 2:
					action = 'remove'
				else:
					action = 'upgrade'
				args = entry[1]
				if cmd == 0:
					info = args['package']
				elif cmd == 2:
					info = args['package']
				else:
					info = _("Dreambox software because updates are available.")

				self.list.append(self.buildEntryComponent(action,info))
			self['list'].setList(self.list)
			self['list'].updateList(self.list)

	def buildEntryComponent(self, action,info):
		divpng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "skin_default/div-h.png"))
		upgradepng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_PLUGIN, "SystemPlugins/SoftwareManager/upgrade.png"))
		installpng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_PLUGIN, "SystemPlugins/SoftwareManager/install.png"))
		removepng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_PLUGIN, "SystemPlugins/SoftwareManager/remove.png"))
		if action == 'install':
			return(( _('Installing'), info, installpng, divpng))
		elif action == 'remove':
			return(( _('Removing'), info, removepng, divpng))
		else:
			return(( _('Upgrading'), info, upgradepng, divpng))

	def exit(self):
		self.close()

	def process_all(self):
		self.close((True,None))

	def process_extensions(self):
		self.list = []
		if self.cmdlist is not None:
			for entry in self.cmdlist:
				if entry[0] in (0,2):
					self.list.append((entry))
		self.close((False,self.list))


class PluginManagerHelp(Screen):
	skin = """
		<screen name="PluginManagerHelp" position="center,120" size="820,520" title="Plugin manager help">
			<ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="200,40" />
			<widget source="key_red" render="Label" position="10,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-2,-2"/>
			<eLabel	position="10,50" size="800,1" backgroundColor="grey"/>
			<widget source="status" render="Label" position="10,55" size="800,25" font="Regular;22" halign="center" transparent="1"/>
			<eLabel	position="10,85" size="800,1" backgroundColor="grey"/>
			<widget source="list" render="Listbox" position="10,95" size="800,420" enableWrapAround="1" scrollbarMode="showOnDemand">
				<convert type="TemplatedMultiContent">
					{"template": [
					MultiContentEntryText(pos=(100,2),size=(630,28),font=0,flags=RT_HALIGN_LEFT,text=0),# index 0 is the name
					MultiContentEntryText(pos=(100,33),size=(630,20),font=1,flags=RT_HALIGN_LEFT,text=1),# index 1 is the state
					MultiContentEntryPixmapAlphaTest(pos=(15,5),size=(48,48),png=2),# index 2 is the status pixmap
					MultiContentEntryPixmapAlphaTest(pos=(0,59),size=(800,1),png=3),# index 3 is the div pixmap
					],
					"fonts": [gFont("Regular",22),gFont("Regular",18)],
					"itemHeight": 60
					}
				</convert>
			</widget>
		</screen>"""

	def __init__(self, session, plugin_path):
		Screen.__init__(self, session)
		self.session = session
		self.skin_path = plugin_path

		self["shortcuts"] = ActionMap(["ShortcutActions", "WizardActions"],
		{
			"back": self.exit,
			"red": self.exit,
		}, -1)

		self.list = []
		self["list"] = List(self.list)
		self["key_red"] = StaticText(_("Close"))
		self["status"] = StaticText(_("A small overview of the available icon states and actions."))

		self.onShown.append(self.setWindowTitle)
		self.onLayoutFinish.append(self.rebuildList)

	def setWindowTitle(self):
		self.setTitle(_("Plugin manager help"))

	def rebuildList(self):
		self.list = []
		self.list.append(self.buildEntryComponent('install'))
		self.list.append(self.buildEntryComponent('installable'))
		self.list.append(self.buildEntryComponent('installed'))
		self.list.append(self.buildEntryComponent('remove'))
		self['list'].setList(self.list)
		self['list'].updateList(self.list)

	def buildEntryComponent(self, state):
		divpng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "skin_default/div-h.png"))
		installedpng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_PLUGIN, "SystemPlugins/SoftwareManager/installed.png"))
		installablepng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_PLUGIN, "SystemPlugins/SoftwareManager/installable.png"))
		removepng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_PLUGIN, "SystemPlugins/SoftwareManager/remove.png"))
		installpng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_PLUGIN, "SystemPlugins/SoftwareManager/install.png"))

		if state == 'installed':
			return(( _('This plugin is installed.'), _('You can remove this plugin.'), installedpng, divpng))
		elif state == 'installable':
			return(( _('This plugin is not installed.'), _('You can install this plugin.'), installablepng, divpng))
		elif state == 'install':
			return(( _('This plugin will be installed.'), _('You can cancel the installation.'), installpng, divpng))
		elif state == 'remove':
			return(( _('This plugin will be removed.'), _('You can cancel the removal.'), removepng, divpng))

	def exit(self):
		self.close()


class PluginDetails(Screen):
	skin = """
		<screen name="PluginDetails" position="center,120" size="820,520" title="Plugin details">
			<ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="200,40" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="210,5" size="200,40" />
			<widget source="key_red" render="Label" position="10,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-2,-2"/>
			<widget source="key_green" render="Label" position="210,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-2,-2"/>
			<eLabel	position="10,50" size="800,1" backgroundColor="grey"/>
			<widget name="statuspic" position="20,55" size="48,48" />
			<widget source="author" render="Label" position="100,65" size="700,30" font="Regular;25" backgroundColor="background"/>
			<eLabel	position="10,110" size="800,1" backgroundColor="grey"/>
			<widget name="detailtext" position="10,120" size="490,380" font="Regular;23" />
			<widget name="screenshot" position="510,120" size="280,210" />
			<widget name="divpic" position="0,0" size="0,0"/>
		</screen>"""
	def __init__(self, session, plugin_path, packagedata = None):
		Screen.__init__(self, session)
		self.skin_path = plugin_path
		self.language = language.getLanguage()[:2] # getLanguage returns e.g. "fi_FI" for "language_country"
		self.directory = resolveFilename(SCOPE_METADIR)
		if packagedata:
			self.pluginname = packagedata[0]
			self.pluginstate = packagedata[4]
			self.statuspicinstance = packagedata[5]
			self.divpicinstance = packagedata[6]
			handler = DreamInfoHandler(self.statusCallback)
			self.attributes = handler.getPackageDetails(packagedata[1])["attributes"]
		self.thumbnail = ""

		self["shortcuts"] = ActionMap(["ShortcutActions", "WizardActions"],
		{
			"back": self.exit,
			"red": self.exit,
			"green": self.go,
			"up": self.pageUp,
			"down":	self.pageDown,
			"left":	self.pageUp,
			"right": self.pageDown,
		}, -1)

		self["key_red"] = StaticText(_("Close"))
		self["key_green"] = StaticText("")
		self["author"] = StaticText()
		self["statuspic"] = Pixmap()
		self["divpic"] = Pixmap()
		self["screenshot"] = Pixmap()
		self["detailtext"] = ScrollLabel()

		self["statuspic"].hide()
		self["screenshot"].hide()
		self["divpic"].hide()

		self.restartRequired = False
		self.cmdList = []
		self.oktext = _("\nAfter pressing OK, please wait!")
		self.picload = ePicLoad()
		self.picload_conn = self.picload.PictureData.connect(self.paintScreenshotPixmapCB)
		self.onShown.append(self.setWindowTitle)
		self.onLayoutFinish.append(self.setInfos)

	def setWindowTitle(self):
		self.setTitle(_("Details for plugin: ") + self.pluginname )

	def exit(self):
		self.close(False)

	def pageUp(self):
		self["detailtext"].pageUp()

	def pageDown(self):
		self["detailtext"].pageDown()

	def statusCallback(self, status, progress):
		pass

	def setInfos(self):
		if "screenshot" in self.attributes:
			self.loadThumbnail(self.attributes)

		if "name" in self.attributes:
			self.pluginname = self.attributes["name"]
		else:
			self.pluginname = _("unknown")

		if "author" in self.attributes:
			self.author = self.attributes["author"]
		else:
			self.author = _("unknown")

		if "description" in self.attributes:
			self.description = _(self.attributes["description"].replace("\\n", "\n"))
		else:
			self.description = _("No description available.")

		self["author"].setText(_("Author: ") + self.author)
		self["detailtext"].setText(_(self.description))
		if self.pluginstate in ('installable', 'install'):
			if iSoftwareTools.NetworkConnectionAvailable:
				self["key_green"].setText(_("Install"))
			else:
				self["key_green"].setText("")
		else:
			self["key_green"].setText(_("Remove"))

	def loadThumbnail(self, entry):
		thumbnailUrl = None
		if "screenshot" in entry:
			thumbnailUrl = entry["screenshot"]
			if self.language == "de":
				if thumbnailUrl[-7:] == "_en.jpg":
					thumbnailUrl = thumbnailUrl[:-7] + "_de.jpg"

		if thumbnailUrl is not None:
			self.thumbnail = "/tmp/" + thumbnailUrl.split('/')[-1]
			print("[PluginDetails] downloading screenshot " + thumbnailUrl + " to " + self.thumbnail)
			if iSoftwareTools.NetworkConnectionAvailable:
				client.downloadPage(thumbnailUrl,self.thumbnail).addCallback(self.setThumbnail).addErrback(self.fetchFailed)
			else:
				self.setThumbnail(noScreenshot = True)
		else:
			self.setThumbnail(noScreenshot = True)

	def setThumbnail(self, noScreenshot = False):
		if not noScreenshot:
			filename = self.thumbnail
		else:
			filename = resolveFilename(SCOPE_CURRENT_PLUGIN, "SystemPlugins/SoftwareManager/noprev.png")

		sc = AVSwitch().getFramebufferScale()
		self.picload.setPara((self["screenshot"].instance.size().width(), self["screenshot"].instance.size().height(), sc[0], sc[1], False, 1, "#00000000"))
		self.picload.startDecode(filename)

		if self.statuspicinstance != None:
			self["statuspic"].instance.setPixmap(self.statuspicinstance)
			self["statuspic"].show()
		if self.divpicinstance != None:
			self["divpic"].instance.setPixmap(self.divpicinstance)
			self["divpic"].show()

	def paintScreenshotPixmapCB(self, picInfo=None):
		ptr = self.picload.getData()
		if ptr != None:
			self["screenshot"].instance.setPixmap(ptr)
			self["screenshot"].show()
		else:
			self.setThumbnail(noScreenshot = True)

	def go(self):
		if "package" in self.attributes:
			self.packagefiles = self.attributes["package"]
		if "needsRestart" in self.attributes:
			self.restartRequired = True
		self.cmdList = []
		if self.pluginstate in ('installed', 'remove'):
			if self.packagefiles:
				for package in self.packagefiles[:]:
					self.cmdList.append((IpkgComponent.CMD_REMOVE, { "autoremove": True, "package": package["name"] }))
					if len(self.cmdList):
						self.session.openWithCallback(self.runRemove, MessageBox, _("Do you want to remove the package:\n") + self.pluginname + "\n" + self.oktext)
		else:
			if iSoftwareTools.NetworkConnectionAvailable:
				if self.packagefiles:
					for package in self.packagefiles[:]:
						self.cmdList.append((IpkgComponent.CMD_INSTALL, { "package": package["name"] }))
						if len(self.cmdList):
							self.session.openWithCallback(self.runUpgrade, MessageBox, _("Do you want to install the package:\n") + self.pluginname + "\n" + self.oktext)

	def runUpgrade(self, result):
		if result:
			self.session.openWithCallback(self.runUpgradeFinished, Ipkg, cmdList = self.cmdList)

	def runUpgradeFinished(self):
		self.reloadPluginlist()
		if plugins.restartRequired or self.restartRequired or pendingSqshImgInstall():
			self.session.openWithCallback(self.UpgradeReboot, MessageBox, _("Installation finished.") +" "+_("Do you want to reboot your Dreambox?"), MessageBox.TYPE_YESNO)
		else:
			self.close(True)

	def UpgradeReboot(self, result):
		if result:
			quitMainloop(3)
		else:
			self.close(True)

	def runRemove(self, result):
		if result:
			self.session.openWithCallback(self.runRemoveFinished, Ipkg, cmdList = self.cmdList)

	def runRemoveFinished(self):
		if pendingSqshImgInstall():
			self.session.openWithCallback(self.UpgradeReboot, MessageBox, _("Remove finished.") +" "+_("Do you want to reboot your Dreambox?"), MessageBox.TYPE_YESNO)
		else:
			self.close(True)

	def reloadPluginlist(self):
		plugins.readPluginList(resolveFilename(SCOPE_PLUGINS))

	def fetchFailed(self,string):
		self.setThumbnail(noScreenshot = True)
		print("[PluginDetails] fetch failed " + string.getErrorMessage())

class IPKGMenu(Screen):
	skin = """
		<screen name="IPKGMenu" position="center,120" size="820,520" title="Select upgrade source to edit.">
			<ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="200,40"  />
			<ePixmap pixmap="skin_default/buttons/green.png" position="210,5" size="200,40"  />
			<widget source="key_red" render="Label" position="10,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-2,-2" />
			<widget source="key_green" render="Label" position="210,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-2,-2" />
			<eLabel position="10,50" size="800,1" backgroundColor="grey" />
			<widget name="filelist" position="10,60" size="800,450" enableWrapAround="1" scrollbarMode="showOnDemand" />
		</screen>"""

	def __init__(self, session, plugin_path):
		Screen.__init__(self, session)
		self.skin_path = plugin_path
		
		self["key_red"] = StaticText(_("Close"))
		self["key_green"] = StaticText(_("Edit"))

		self.sel = []
		self.val = []
		self.entry = False
		self.exe = False
		
		self.path = ""

		self["actions"] = NumberActionMap(["SetupActions"],
		{
			"ok": self.KeyOk,
			"cancel": self.keyCancel
		}, -1)

		self["shortcuts"] = ActionMap(["ShortcutActions"],
		{
			"red": self.keyCancel,
			"green": self.KeyOk,
		})
		self.flist = []
		self["filelist"] = MenuList(self.flist)
		self.fill_list()
		self.onLayoutFinish.append(self.layoutFinished)

	def layoutFinished(self):
		self.setWindowTitle()

	def setWindowTitle(self):
		self.setTitle(_("Select upgrade source to edit."))

	def fill_list(self):
		self.flist = []
		self.path = '/etc/opkg/'
		if (os_path.exists(self.path) == False):
			self.entry = False
			return
		for file in listdir(self.path):
			if (file.endswith(".conf")):
				if file != 'arch.conf':
					self.flist.append((file))
					self.entry = True
					self["filelist"].l.setList(self.flist)

	def KeyOk(self):
		if (self.exe == False) and (self.entry == True):
			self.sel = self["filelist"].getCurrent()
			self.val = self.path + self.sel
			self.session.open(IPKGSource, self.val)

	def keyCancel(self):
		self.close()

	def Exit(self):
		self.close()


class IPKGSource(Screen):
	skin = """
		<screen name="IPKGSource" position="center,center" size="1080,100" title="IPKG source">
			<ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="200,40"  />
			<ePixmap pixmap="skin_default/buttons/green.png" position="210,5" size="200,40"  />
			<widget source="key_red" render="Label" position="10,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-2,-2" />
			<widget source="key_green" render="Label" position="210,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-2,-2" />
			<widget name="text" position="10,55" size="1060,30" font="Regular;24" />
		</screen>"""

	def __init__(self, session, configfile = None):
		Screen.__init__(self, session)
		self.session = session
		self.configfile = configfile
		text = ""
		if self.configfile:
			try:
				fp = open(configfile, 'r')
				sources = fp.readlines()
				if sources:
					text = sources[0]
				fp.close()
			except IOError:
				pass

		desk = getDesktop(0)
		y= int(desk.size().height())

		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("Save"))

		if (y>=720):
			self["text"] = Input(text, maxSize=False, type=Input.TEXT)
		else:
			self["text"] = Input(text, maxSize=False, visible_width = 55, type=Input.TEXT)

		self["actions"] = NumberActionMap(["WizardActions", "InputActions", "TextEntryActions", "KeyboardInputActions","ShortcutActions"], 
		{
			"ok": self.go,
			"back": self.close,
			"red": self.close,
			"green": self.go,
			"left": self.keyLeft,
			"right": self.keyRight,
			"home": self.keyHome,
			"end": self.keyEnd,
			"deleteForward": self.keyDeleteForward,
			"deleteBackward": self.keyDeleteBackward,
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

		self.onLayoutFinish.append(self.layoutFinished)

	def layoutFinished(self):
		self.setWindowTitle()
		self["text"].right()

	def setWindowTitle(self):
		self.setTitle(_("Edit upgrade source url."))

	def go(self):
		text = self["text"].getText()
		if text:
			fp = open(self.configfile, 'w')
			fp.write(text)
			fp.write("\n")
			fp.close()
		self.close()

	def keyLeft(self):
		self["text"].left()
	
	def keyRight(self):
		self["text"].right()
	
	def keyHome(self):
		self["text"].home()
	
	def keyEnd(self):
		self["text"].end()
	
	def keyDeleteForward(self):
		self["text"].delete()
	
	def keyDeleteBackward(self):
		self["text"].deleteBackward()
	
	def keyNumberGlobal(self, number):
		self["text"].number(number)


class PacketManager(Screen, NumericalTextInput):
	skin = """
		<screen name="PacketManager" position="center,120" size="820,520" title="Packet manager">
			<ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="200,40" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="210,5" size="200,40" />
			<widget source="key_red" render="Label" position="10,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-2,-2"/>
			<widget source="key_green" render="Label" position="210,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-2,-2"/>
			<eLabel position="10,50" size="800,1" backgroundColor="grey" />
			<widget source="list" render="Listbox" position="10,55" size="800,420" enableWrapAround="1" scrollbarMode="showOnDemand" transparent="1">
				<convert type="TemplatedMultiContent">
					{"template": [
					MultiContentEntryText(pos=(60,2),size=(710,28),font=0,flags=RT_HALIGN_LEFT,text=0),# index 0 is the name
					MultiContentEntryText(pos=(70,33),size=(700,20),font=1,flags=RT_HALIGN_LEFT,text=2),# index 2 is the description
					MultiContentEntryPixmapAlphaTest(pos=(5,5),size=(48,48),png=4),# index 5 is the status pixmap
					MultiContentEntryPixmapAlphaTest(pos=(0,59),size=(800,1),png=5),# index 6 is the div pixmap
					],
					"fonts": [gFont("Regular",24),gFont("Regular",18)],
					"itemHeight": 60
					}
				</convert>
			</widget>
			<eLabel	position="10,480" size="800,1" backgroundColor="grey"/>
		</screen>"""
		
	def __init__(self, session, plugin_path, args = None):
		Screen.__init__(self, session)
		NumericalTextInput.__init__(self)
		self.session = session
		self.skin_path = plugin_path

		self.setUseableChars(u'1234567890abcdefghijklmnopqrstuvwxyz')

		self["shortcuts"] = NumberActionMap(["ShortcutActions", "WizardActions", "NumberActions", "InputActions", "InputAsciiActions", "KeyboardInputActions" ],
		{
			"ok": self.go,
			"back": self.exit,
			"red": self.exit,
			"green": self.reload,
			"gotAsciiCode": self.keyGotAscii,
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
		
		self.list = []
		self.statuslist = []
		self["list"] = List(self.list)
		self["key_red"] = StaticText(_("Close"))
		self["key_green"] = StaticText(_("Reload"))

		self.list_updating = True
		self.packetlist = []
		self.installed_packetlist = {}
		self.upgradeable_packages = {}
		self.Console = Console()
		self.cmdList = []
		self.cachelist = []
		self.cache_ttl = 86400  #600 is default, 0 disables, Seconds cache is considered valid (24h should be ok for caching ipkgs)
		self.cache_file = eEnv.resolve('${libdir}/enigma2/python/Plugins/SystemPlugins/SoftwareManager/packetmanager.cache') #Path to cache directory
		self.oktext = _("\nAfter pressing OK, please wait!")
		self.unwanted_extensions = ('-dbg', '-dev', '-doc', '-staticdev')

		self.ipkg = IpkgComponent()
		self.ipkg.addCallback(self.ipkgCallback)
		self.onShown.append(self.setWindowTitle)
		self.onLayoutFinish.append(self.rebuildList)

	def keyNumberGlobal(self, val):
		key = self.getKey(val)
		if key is not None:
			keyvalue = key.encode("utf-8")
			if len(keyvalue) == 1:
				self.setNextIdx(keyvalue[0])
		
	def keyGotAscii(self):
		keyvalue = unichr(getPrevAsciiCode()).encode("utf-8")
		if len(keyvalue) == 1:
			self.setNextIdx(keyvalue[0])
		
	def setNextIdx(self,char):
		if char in ("0", "1", "a"):
			self["list"].setIndex(0)
		else:
			idx = self.getNextIdx(char)
			if idx and idx <= self["list"].count:
				self["list"].setIndex(idx)

	def getNextIdx(self,char):
		idx = 0
		for i in self["list"].list:
			if i[0][0] == char:
				return idx
			idx += 1

	def exit(self):
		self.ipkg.stop()
		if self.Console is not None:
			if len(self.Console.appContainers):
				for name in self.Console.appContainers.keys():
					self.Console.kill(name)
		self.close()

	def reload(self):
		if (os_path.exists(self.cache_file) == True):
			remove(self.cache_file)
			self.list_updating = True
			self.rebuildList()
			
	def setWindowTitle(self):
		self.setTitle(_("Packet manager"))

	def setStatus(self,status = None):
		if status:
			self.statuslist = []
			divpng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "skin_default/div-h.png"))
			if status == 'update':
				statuspng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_PLUGIN, "SystemPlugins/SoftwareManager/upgrade.png"))
				self.statuslist.append(( _("Package list update"), '', _("Trying to download a new packetlist. Please wait..." ),'',statuspng, divpng ))
				self['list'].setList(self.statuslist)	
			elif status == 'error':
				statuspng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_PLUGIN, "SystemPlugins/SoftwareManager/remove.png"))
				self.statuslist.append(( _("Error"), '', _("There was an error downloading the packetlist. Please try again." ),'',statuspng, divpng ))
				self['list'].setList(self.statuslist)				

	def rebuildList(self):
		self.setStatus('update')
		self.inv_cache = 0
		self.vc = valid_cache(self.cache_file, self.cache_ttl)
		if self.cache_ttl > 0 and self.vc != 0:
			try:
				self.buildPacketList()
			except:
				self.inv_cache = 1
		if self.cache_ttl == 0 or self.inv_cache == 1 or self.vc == 0:
			self.run = 0
			self.ipkg.startCmd(IpkgComponent.CMD_UPDATE)

	def go(self, returnValue = None):
		cur = self["list"].getCurrent()
		if cur:
			status = cur[3]
			package = cur[0]
			self.cmdList = []
			if status == 'installed':
				self.cmdList.append((IpkgComponent.CMD_REMOVE, { "autoremove": True, "package": package }))
				if len(self.cmdList):
					self.session.openWithCallback(self.runRemove, MessageBox, _("Do you want to remove the package:\n") + package + "\n" + self.oktext)
			elif status == 'upgradeable':
				self.cmdList.append((IpkgComponent.CMD_INSTALL, { "package": package }))
				if len(self.cmdList):
					self.session.openWithCallback(self.runUpgrade, MessageBox, _("Do you want to upgrade the package:\n") + package + "\n" + self.oktext)
			elif status == "installable":
				self.cmdList.append((IpkgComponent.CMD_INSTALL, { "package": package }))
				if len(self.cmdList):
					self.session.openWithCallback(self.runUpgrade, MessageBox, _("Do you want to install the package:\n") + package + "\n" + self.oktext)

	def runRemove(self, result):
		if result:
			self.session.openWithCallback(self.runRemoveFinished, Ipkg, cmdList = self.cmdList)

	def runRemoveFinished(self):
		self.session.openWithCallback(self.RemoveReboot, MessageBox, _("Remove finished.") +" "+_("Do you want to reboot your Dreambox?"), MessageBox.TYPE_YESNO)

	def RemoveReboot(self, result):
		if result is None:
			return
		if result is False:
			cur = self["list"].getCurrent()
			if cur:
				item = self['list'].getIndex()
				self.list[item] = self.buildEntryComponent(cur[0], cur[1], cur[2], 'installable')
				self.cachelist[item] = [cur[0], cur[1], cur[2], 'installable']
				self['list'].setList(self.list)
				write_cache(self.cache_file, self.cachelist)
				self.reloadPluginlist()
		if result:
			quitMainloop(3)

	def runUpgrade(self, result):
		if result:
			self.session.openWithCallback(self.runUpgradeFinished, Ipkg, cmdList = self.cmdList)

	def runUpgradeFinished(self):
		self.session.openWithCallback(self.UpgradeReboot, MessageBox, _("Upgrade finished.") +" "+_("Do you want to reboot your Dreambox?"), MessageBox.TYPE_YESNO)

	def UpgradeReboot(self, result):
		if result is None:
			return
		if result is False:
			cur = self["list"].getCurrent()
			if cur:
				item = self['list'].getIndex()
				self.list[item] = self.buildEntryComponent(cur[0], cur[1], cur[2], 'installed')
				self.cachelist[item] = [cur[0], cur[1], cur[2], 'installed']
				self['list'].setList(self.list)
				write_cache(self.cache_file, self.cachelist)
				self.reloadPluginlist()
		if result:
			quitMainloop(3)

	def ipkgCallback(self, event, param):
		if event == IpkgComponent.EVENT_ERROR:
			self.list_updating = False
			self.setStatus('error')
		elif event == IpkgComponent.EVENT_DONE:
			if self.list_updating:
				self.list_updating = False
				if not self.Console:
					self.Console = Console()
				cmd = "opkg list"
				self.Console.ePopen(cmd, self.IpkgList_Finished)
		#print event, "-", param
		pass

	def IpkgList_Finished(self, result, retval, extra_args = None):
		if result:
			self.packetlist = []
			last_name = ""
			for x in result.splitlines():
				tokens = x.split(' - ') 
				name = tokens[0].strip()
				if not any(name.endswith(x) for x in self.unwanted_extensions):
					l = len(tokens)
					version = l > 1 and tokens[1].strip() or ""
					descr = l > 2 and tokens[2].strip() or ""
					if name == last_name:
						continue
					last_name = name 
					self.packetlist.append([name, version, descr])

		if not self.Console:
			self.Console = Console()
		cmd = "opkg list-installed"
		self.Console.ePopen(cmd, self.IpkgListInstalled_Finished)

	def IpkgListInstalled_Finished(self, result, retval, extra_args = None):
		if result:
			self.installed_packetlist = {}
			for x in result.splitlines():
				tokens = x.split(' - ')
				name = tokens[0].strip()
				if not any(name.endswith(x) for x in self.unwanted_extensions):
					l = len(tokens)
					version = l > 1 and tokens[1].strip() or ""
					self.installed_packetlist[name] = version
		if not self.Console:
			self.Console = Console()
		cmd = "opkg list-upgradable"
		self.Console.ePopen(cmd, self.OpkgListUpgradeable_Finished)

	def OpkgListUpgradeable_Finished(self, result, retval, extra_args = None):
		if result:
			self.upgradeable_packages = {}
			for x in result.splitlines():
				tokens = x.split(' - ')
				name = tokens[0].strip()
				if not any(name.endswith(x) for x in self.unwanted_extensions):
					l = len(tokens)
					version = l > 2 and tokens[2].strip() or ""
					self.upgradeable_packages[name] = version
		self.buildPacketList()
	
	def buildEntryComponent(self, name, version, description, state):
		divpng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "skin_default/div-h.png"))
		if description == "":
			description = "No description available."
		if state == 'installed':
			installedpng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_PLUGIN, "SystemPlugins/SoftwareManager/installed.png"))
			return((name, version, _(description), state, installedpng, divpng))	
		elif state == 'upgradeable':
			upgradeablepng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_PLUGIN, "SystemPlugins/SoftwareManager/upgradeable.png"))
			return((name, version, _(description), state, upgradeablepng, divpng))	
		else:
			installablepng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_PLUGIN, "SystemPlugins/SoftwareManager/installable.png"))
			return((name, version, _(description), state, installablepng, divpng))

	def buildPacketList(self):
		self.list = []
		self.cachelist = []
		if self.cache_ttl > 0 and self.vc != 0:
			print('Loading packagelist cache from ',self.cache_file)
			try:
				self.cachelist = load_cache(self.cache_file)
				if len(self.cachelist) > 0:
					for x in self.cachelist:
						self.list.append(self.buildEntryComponent(x[0], x[1], x[2], x[3]))
					self['list'].setList(self.list)
			except:
				self.inv_cache = 1

		if self.cache_ttl == 0 or self.inv_cache == 1 or self.vc == 0:
			print('rebuilding fresh package list')
			for x in self.packetlist:
				status = ""
				if x[0] in self.installed_packetlist:
					if x[0] in self.upgradeable_packages:
						status = "upgradeable"
					else:
						status = "installed"
				else:
					status = "installable"
				self.list.append(self.buildEntryComponent(x[0], x[1], x[2], status))	
				self.cachelist.append([x[0], x[1], x[2], status])
			write_cache(self.cache_file, self.cachelist)
			self['list'].setList(self.list)

	def reloadPluginlist(self):
		plugins.readPluginList(resolveFilename(SCOPE_PLUGINS))


class IpkgInstaller(Screen):
	skin = """
		<screen name="IpkgInstaller" position="center,120" size="820,520" title="Install extensions">
			<ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="200,40"  />
			<ePixmap pixmap="skin_default/buttons/green.png" position="210,5" size="200,40"  />
			<widget source="key_red" render="Label" position="10,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-2,-2" />
			<widget source="key_green" render="Label" position="210,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" foregroundColor="white" shadowColor="black" shadowOffset="-2,-2" />
			<eLabel position="10,50" size="800,1" backgroundColor="grey" />
			<widget name="list" position="10,55" size="800,420" enableWrapAround="1" scrollbarMode="showOnDemand" />
			<eLabel position="10,480" size="800,1" backgroundColor="grey" />
			<widget source="introduction" render="Label" position="10,488" size="800,25" font="Regular;22" halign="center" />
		</screen>"""
	
	def __init__(self, session, list):
		Screen.__init__(self, session)

		self.list = SelectionList()
		self["list"] = self.list
		for listindex in range(len(list)):
			self.list.addSelection(list[listindex], list[listindex], listindex, True)

		self["key_red"] = StaticText(_("Close"))
		self["key_green"] = StaticText(_("Install"))
		self["introduction"] = StaticText(_("Press OK to toggle the selection."))
		
		self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], 
		{
			"ok": self.list.toggleSelection, 
			"cancel": self.close,
			"red": self.close,
			"green": self.install
		}, -1)

	def install(self):
		list = self.list.getSelectionsList()
		cmdList = []
		for item in list:
			cmdList.append((IpkgComponent.CMD_INSTALL, { "package": item[1] }))
		self.session.open(Ipkg, cmdList = cmdList)


def filescan_open(list, session, **kwargs):
	filelist = [x.path for x in list]
	session.open(IpkgInstaller, filelist) # list

def filescan(**kwargs):
	from Components.Scanner import Scanner, ScanPath
	return \
		Scanner(mimetypes = ["application/x-debian-package"], 
			paths_to_scan = 
				[
					ScanPath(path = "ipk", with_subdirs = True),
					ScanPath(path = "deb", with_subdirs = True),
					ScanPath(path = "tmp", with_subdirs = True),
					ScanPath(path = "", with_subdirs = False), 
				], 
			name = "Dpkg",
			description = _("Install extensions."),
			openfnc = filescan_open, )



def UpgradeMain(session, **kwargs):
	session.open(UpdatePluginMenu)

def startSetup(menuid):
	if menuid != "setup": 
		return [ ]
	return [(_("Software management"), UpgradeMain, "software_manager", 5)]

def sessionstart(session, **kwargs):
	if session: #start
		updateCheck.start(session)

def Plugins(path, **kwargs):
	global plugin_path
	plugin_path = path

	resourcemanager.addResource("software_manager", UpdatePluginMenu)
	resourcemanager.addResource("software_manager_upgrade", UpdatePlugin)

	plugins = [
		PluginDescriptor(name=_("Software management"), description=_("Manage your receiver's software"), where = PluginDescriptor.WHERE_MENU, needsRestart = False, fnc=startSetup),
		PluginDescriptor(name=_("Dpkg"), where = PluginDescriptor.WHERE_FILESCAN, needsRestart = False, fnc = filescan),
		PluginDescriptor(name=_("Auto Updater"), where = PluginDescriptor.WHERE_SESSIONSTART, fnc=sessionstart)
	]
	if config.usage.setup_level.index >= 2: # expert+
		plugins.append(PluginDescriptor(name=_("Software management"), description=_("Manage your receiver's software"), where = PluginDescriptor.WHERE_EXTENSIONSMENU, needsRestart = False, fnc=UpgradeMain))
	return plugins
