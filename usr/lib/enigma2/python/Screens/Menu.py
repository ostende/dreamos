from __future__ import print_function
from __future__ import absolute_import
from enigma import eSize
import six

from Screens.Screen import Screen
from Components.Sources.List import List
from Components.ActionMap import NumberActionMap
from Components.Sources.StaticText import StaticText
from Components.config import configfile
from Components.Pixmap import Pixmap
from Components.PluginComponent import plugins
from Components.config import config
from Components.SystemInfo import SystemInfo

from Tools.Directories import resolveFilename, SCOPE_SKIN, SCOPE_CURRENT_SKIN, fileExists
from Tools.LoadPixmap import LoadPixmap

import xml.etree.cElementTree

from Screens.Setup import Setup, getSetupTitle

#		<item text="TV-Mode">self.setModeTV()</item>
#		<item text="Radio-Mode">self.setModeRadio()</item>
#		<item text="File-Mode">self.setModeFile()</item>
#			<item text="Sleep Timer"></item>

from skin import componentSizes
lastMenuID = None

def MenuEntryPixmap(entryID, png_cache, lastMenuID):
	width = componentSizes.itemWidth(componentSizes.MENU_PIXMAP, default=192)
	height = componentSizes.itemHeight(componentSizes.MENU_PIXMAP, default=192)
	pixmapSize = eSize(width, height)
	png = png_cache.get(entryID, None)
	if png is None: # no cached entry
		pngPath = resolveFilename(SCOPE_CURRENT_SKIN, "menu/" + entryID + ".svg")
		pos = config.skin.primary_skin.value.rfind('/')
		if pos > -1:
			current_skin = config.skin.primary_skin.value[:pos+1]
		else:
			current_skin = ""
		if not fileExists(pngPath) or not (( current_skin in pngPath and current_skin ) or not current_skin ):
			pngPath = resolveFilename(SCOPE_CURRENT_SKIN, "menu/" + entryID + ".png")
		if ( current_skin in pngPath and current_skin ) or not current_skin:
			png = LoadPixmap(pngPath, cached=True, size=pixmapSize) #lets look for a dedicated icon
		if png is None: # no dedicated icon found
			if lastMenuID is not None:
				png = png_cache.get(lastMenuID, None)
		png_cache[entryID] = png
	if png is None:
		png = png_cache.get("missing", None)
		if png is None:
			png = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "menu/missing.svg"), cached=True, size=pixmapSize)
			if not png:
				png = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "menu/missing.png"), cached=True, size=pixmapSize)
			png_cache["missing"] = png
	return png

# read the menu
mdom = xml.etree.cElementTree.parse(resolveFilename(SCOPE_SKIN, 'menu.xml'))

class boundFunction:
	def __init__(self, fnc, *args):
		self.fnc = fnc
		self.args = args
	def __call__(self):
		self.fnc(*self.args)

class MenuUpdater:
	def __init__(self):
		self.updatedMenuItems = {}

	def addMenuItem(self, id, pos, text, module, screen, weight, description):
		if not self.updatedMenuAvailable(id):
			self.updatedMenuItems[id] = []
		self.updatedMenuItems[id].append([text, pos, module, screen, weight, description])

	def delMenuItem(self, id, pos, text, module, screen, weight, description):
		self.updatedMenuItems[id].remove([text, pos, module, screen, weight, description])

	def updatedMenuAvailable(self, id):
		return id in self.updatedMenuItems

	def getUpdatedMenu(self, id):
		return self.updatedMenuItems[id]

menuupdater = MenuUpdater()

class MenuSummary(Screen):
	skin = """
	<screen position="0,0" size="132,64">
		<widget source="parent.title" render="Label" position="6,4" size="120,21" font="Regular;18" />
		<widget source="parent.menu" render="Label" position="6,25" size="120,21" font="Regular;16">
			<convert type="StringListSelection" />
		</widget>
		<widget source="global.CurrentTime" render="Label" position="56,46" size="82,18" font="Regular;16" >
			<convert type="ClockToText">WithSeconds</convert>
		</widget>
	</screen>"""

class Menu(Screen):

	ALLOW_SUSPEND = Screen.SUSPEND_STOPS
	png_cache = {}

	def okbuttonClick(self):
		print("okbuttonClick")
		selection = self["menu"].getCurrent()
		if selection is not None:
			global lastMenuID
			lastMenuID = selection[2]
			selection[1]()

	def execText(self, text):
		exec(text)

	def runScreen(self, arg):
		# arg[0] is the module (as string)
		# arg[1] is Screen inside this module
		#        plus possible arguments, as
		#        string (as we want to reference
		#        stuff which is just imported)
		# FIXME. somehow
		if arg[0] != "":
			exec("from " + arg[0] + " import *")

		self.openDialog(*eval(arg[1]))

	def nothing(self):	#dummy
		pass

	def openDialog(self, *dialog):	# in every layer needed
		self.session.openWithCallback(self.menuClosed, *dialog)

	def openSetup(self, dialog):
		self.session.openWithCallback(self.menuClosed, Setup, dialog)

	def addMenu(self, destList, node):
		requires = node.get("requires")
		if requires:
			if requires[0] == '!':
				if SystemInfo.get(requires[1:], False):
					return
			elif not SystemInfo.get(requires, False):
				return
		MenuTitle = _(six.ensure_str(node.get("text", "??")))
		entryID = node.get("entryID", "undefined")
		weight = node.get("weight", 50)
		description = six.ensure_str(node.get("description", "")) or None
		description = description and _(description)
		menupng = MenuEntryPixmap(entryID, self.png_cache, lastMenuID)
		x = node.get("flushConfigOnClose")
		if x:
			a = boundFunction(self.session.openWithCallback, self.menuClosedWithConfigFlush, Menu, node)
		else:
			a = boundFunction(self.session.openWithCallback, self.menuClosed, Menu, node)
		#TODO add check if !empty(node.childNodes)
		destList.append((MenuTitle, a, entryID, weight, description, menupng))

	def menuClosedWithConfigFlush(self, *res):
		configfile.save()
		self.menuClosed(*res)

	def menuClosed(self, *res):
		if res and res[0]:
			global lastMenuID
			lastMenuID = None
			self.close(True)

	def addItem(self, destList, node):
		requires = node.get("requires")
		if requires:
			if requires[0] == '!':
				if SystemInfo.get(requires[1:], False):
					return
			elif not SystemInfo.get(requires, False):
				return
		item_text = six.ensure_str(node.get("text", ""))
		entryID = node.get("entryID", "undefined")
		weight = node.get("weight", 50)
		description = six.ensure_str(node.get("description", "")) or None
		description = description and _(description)
		menupng = MenuEntryPixmap(entryID, self.png_cache, lastMenuID)
		for x in node:
			if x.tag == 'screen':
				module = x.get("module")
				screen = x.get("screen")

				if screen is None:
					screen = module

				print(module, screen)
				if module:
					module = "Screens." + module
				else:
					module = ""

				# check for arguments. they will be appended to the
				# openDialog call
				args = x.text or ""
				screen += ", " + args

				destList.append((_(item_text or "??"), boundFunction(self.runScreen, (module, screen)), entryID, weight, description, menupng))
				return
			elif x.tag == 'code':
				destList.append((_(item_text or "??"), boundFunction(self.execText, x.text), entryID, weight, description, menupng))
				return
			elif x.tag == 'setup':
				id = x.get("id")
				if item_text == "":
					item_text = _(getSetupTitle(id))
				else:
					item_text = _(item_text)
				destList.append((item_text, boundFunction(self.openSetup, id), entryID, weight, description, menupng))
				return
		destList.append((item_text, self.nothing, entryID, weight, description, menupng))

	def __init__(self, session, parent):
		Screen.__init__(self, session)
		list = []

		menuID = None
		count = 0
		for x in parent:	#walk through the actual nodelist
			if x.tag == 'item':
				item_level = int(x.get("level", 0))
				if item_level <= config.usage.setup_level.index:
					self.addItem(list, x)
					count += 1
			elif x.tag == 'menu':
				self.addMenu(list, x)
				count += 1
			elif x.tag == "id":
				menuID = x.get("val")
				count = 0

			if menuID is not None:
				# menuupdater?
				if menuupdater.updatedMenuAvailable(menuID):
					for x in menuupdater.getUpdatedMenu(menuID):
						if x[1] == count:
							description = six.ensure_str(x.get("description", "")) or None
							description = description and _(description)
							menupng = MenuEntryPixmap(menuID, self.png_cache, lastMenuID)
							list.append((x[0], boundFunction(self.runScreen, (x[2], x[3] + ", ")), x[4], description, menupng))
							count += 1

		if menuID is not None:
			# plugins
			for l in plugins.getPluginsForMenu(menuID):
				# check if a plugin overrides an existing menu
				plugin_menuid = l[2]
				for x in list:
					if x[2] == plugin_menuid:
						list.remove(x)
						break
				description = l[4] if len(l) == 5 else plugins.getDescriptionForMenuEntryID(menuID, plugin_menuid)
				menupng = MenuEntryPixmap(l[2], self.png_cache, lastMenuID)
				list.append((l[0], boundFunction(l[1], self.session), l[2], l[3] or 50, description, menupng))

		# for the skin: first try a menu_<menuID>, then Menu
		self.skinName = [ ]
		if menuID is not None:
			self.skinName.append("menu_" + menuID)
		self.skinName.append("Menu")

		# Sort by Weight
		list.sort(key=lambda x: int(x[3]))

		self._list = List(list)
		self._list.onSelectionChanged.append(self._onSelectionChanged)
		self["menu"] = self._list
		self["pixmap"] = Pixmap()
		self["description"] = StaticText()

		self["actions"] = NumberActionMap(["OkCancelActions", "MenuActions", "NumberActions"],
			{
				"ok": self.okbuttonClick,
				"cancel": self.closeNonRecursive,
				"menu": self.closeRecursive,
				"1": self.keyNumberGlobal,
				"2": self.keyNumberGlobal,
				"3": self.keyNumberGlobal,
				"4": self.keyNumberGlobal,
				"5": self.keyNumberGlobal,
				"6": self.keyNumberGlobal,
				"7": self.keyNumberGlobal,
				"8": self.keyNumberGlobal,
				"9": self.keyNumberGlobal
			})

		a = six.ensure_str(parent.get("title", "")) or None
		a = a and _(a)
		if a is None:
			a = _(six.ensure_str(parent.get("text", "")))
		self["title"] = StaticText(a)
		self.menu_title = a
		self.onLayoutFinish.append(self._onLayoutFinish)

	def _onLayoutFinish(self):
		self._onSelectionChanged()

	def keyNumberGlobal(self, number):
		print("menu keyNumber:", number)
		# Calculate index
		number -= 1

		if len(self["menu"].list) > number:
			self["menu"].setIndex(number)
			self.okbuttonClick()

	def _onSelectionChanged(self):
		current = self._list.current
		description, pixmap = "", None
		if current:
			description, pixmap = current[4:]
		self["description"].setText(_(description))
		if pixmap:
			self["pixmap"].setPixmap(pixmap)

	def closeNonRecursive(self):
		self.close(False)

	def closeRecursive(self):
		self.close(True)

	def createSummary(self):
		return MenuSummary

class MainMenu(Menu):
	#add file load functions for the xml-file

	def __init__(self, *x):
		self.skinName = "Menu"
		Menu.__init__(self, *x)
