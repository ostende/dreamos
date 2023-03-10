# -*- coding: UTF-8 -*-
from __future__ import absolute_import
from enigma import eListboxPythonMultiContent, gFont, RT_HALIGN_CENTER, RT_VALIGN_CENTER, getPrevAsciiCode
from Screens.Screen import Screen
from Components.Language import language
from Components.ActionMap import ActionMap, NumberActionMap
from Components.Sources.StaticText import StaticText
from Components.Label import Label
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmapAlphaTest
from Tools.Directories import resolveFilename, SCOPE_CURRENT_SKIN
from Tools.LoadPixmap import LoadPixmap
from Tools.NumericalTextInput import NumericalTextInput

from skin import TemplatedListFonts, componentSizes
from six import unichr
from six.moves import range
import six

class VirtualKeyBoardList(MenuList):
	COMPONENT_VIRTUAL_KEYBOARD_LIST = "VirtualKeyBoardList"
	def __init__(self, list, enableWrapAround=False):
		MenuList.__init__(self, list, enableWrapAround, eListboxPythonMultiContent)
		tlf = TemplatedListFonts()
		self.l.setFont(0, gFont(tlf.face(tlf.KEYBOARD, default=tlf.face(tlf.BIG)), tlf.size(tlf.KEYBOARD, default=tlf.size(tlf.BIG))))
		self.l.setItemHeight(VirtualKeyBoardList.itemHeight())

	@staticmethod
	def itemHeight():
		return componentSizes.itemHeight(VirtualKeyBoardList.COMPONENT_VIRTUAL_KEYBOARD_LIST, 45)

def VirtualKeyBoardEntryComponent(keys, selectedKey,shiftMode=False):
	key_backspace = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "skin_default/vkey_backspace.png"))
	key_bg = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "skin_default/vkey_bg.png"))
	key_clr = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "skin_default/vkey_clr.png"))
	key_esc = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "skin_default/vkey_esc.png"))
	key_ok = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "skin_default/vkey_ok.png"))
	key_sel = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "skin_default/vkey_sel.png"))
	key_shift = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "skin_default/vkey_shift.png"))
	key_shift_sel = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "skin_default/vkey_shift_sel.png"))
	key_space = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "skin_default/vkey_space.png"))
	res = [ (keys) ]
	
	x = 0
	count = 0
	height = VirtualKeyBoardList.itemHeight()
	if shiftMode:
		shiftkey_png = key_shift_sel
	else:
		shiftkey_png = key_shift
	for key in keys:
		width = None
		if key == "EXIT":
			width = key_esc.size().width()
			res.append(MultiContentEntryPixmapAlphaTest(pos=(x, 0), size=(width, height), png=key_esc))
		elif key == "BACKSPACE":
			width = key_backspace.size().width()
			res.append(MultiContentEntryPixmapAlphaTest(pos=(x, 0), size=(width, height), png=key_backspace))
		elif key == "CLEAR":
			width = key_clr.size().width()
			res.append(MultiContentEntryPixmapAlphaTest(pos=(x, 0), size=(width, height), png=key_clr))
		elif key == "SHIFT":
			width = shiftkey_png.size().width()
			res.append(MultiContentEntryPixmapAlphaTest(pos=(x, 0), size=(width, height), png=shiftkey_png))
		elif key == "SPACE":
			width = key_space.size().width()
			res.append(MultiContentEntryPixmapAlphaTest(pos=(x, 0), size=(width, height), png=key_space))
		elif key == "OK":
			width = key_ok.size().width()
			res.append(MultiContentEntryPixmapAlphaTest(pos=(x, 0), size=(width, height), png=key_ok))
		#elif key == "<-":
		#	res.append(MultiContentEntryPixmapAlphaTest(pos=(x, 0), size=(45, 45), png=key_left))
		#elif key == "->":
		#	res.append(MultiContentEntryPixmapAlphaTest(pos=(x, 0), size=(45, 45), png=key_right))
		
		else:
			width = key_bg.size().width()
			res.extend((
				MultiContentEntryPixmapAlphaTest(pos=(x, 0), size=(width, height), png=key_bg),
				MultiContentEntryText(pos=(x, 0), size=(width, height), font=0, text=six.ensure_str(key), flags=RT_HALIGN_CENTER | RT_VALIGN_CENTER)
			))
		
		if selectedKey == count:
			width = key_sel.size().width()
			res.append(MultiContentEntryPixmapAlphaTest(pos=(x, 0), size=(width, height), png=key_sel))

		if width is not None:
			x += width
		else:
			x += height
		count += 1
	
	return res


class VirtualKeyBoard(Screen, NumericalTextInput):
	IS_DIALOG = True
	LINESIZE = 12

	def __init__(self, session, title="", text=""):
		Screen.__init__(self, session)
		NumericalTextInput.__init__(self, nextFunc = self.nextFunc)
		self.setZPosition(10000)
		self.keys_list = []
		self.shiftkeys_list = []
		self.lang = language.getLanguage()
		self.nextLang = None
		self.shiftMode = False
		self.text = text
		self.selectedKey = 0
		self.editing = False

		self["country"] = StaticText("")
		self["header"] = Label(title)
		self["text"] = Label(self.text)
		self["list"] = VirtualKeyBoardList([])
		
		self["actions"] = ActionMap(["OkCancelActions", "WizardActions", "ColorActions", "KeyboardInputActions", "InputBoxActions", "InputAsciiActions"],
			{
				"gotAsciiCode": self.keyGotAscii,
				"ok": self.okClicked,
				"cancel": self.exit,
				"left": self.left,
				"right": self.right,
				"up": self.up,
				"down": self.down,
				"red": self.backClicked,
				"green": self.ok,
				"yellow": self.switchLang,
				"deleteBackward": self.backClicked,
				"back": self.exit				
			}, -2)
		self["numberActions"] = NumberActionMap(["NumberActions"],
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
			"0": self.keyNumberGlobal
		})
		self.setLang()
		self.onExecBegin.append(self.setKeyboardModeAscii)
		self.onLayoutFinish.append(self.buildVirtualKeyBoard)
	
	def switchLang(self):
		self.lang = self.nextLang
		self.setLang()
		self.buildVirtualKeyBoard()

	def setLang(self):
		if self.lang == 'de_DE':
			self.keys_list = [
				[u"EXIT", u"1", u"2", u"3", u"4", u"5", u"6", u"7", u"8", u"9", u"0", u"BACKSPACE"],
				[u"q", u"w", u"e", u"r", u"t", u"z", u"u", u"i", u"o", u"p", u"??", u"+"],
				[u"a", u"s", u"d", u"f", u"g", u"h", u"j", u"k", u"l", u"??", u"??", u"#"],
				[u"<", u"y", u"x", u"c", u"v", u"b", u"n", u"m", u",", ".", u"-", u"CLEAR"],
				[u"SHIFT", u"SPACE", u"@", u"??", u"OK"]]
			self.shiftkeys_list = [
				[u"EXIT", u"!", u'"', u"??", u"$", u"%", u"&", u"/", u"(", u")", u"=", u"BACKSPACE"],
				[u"Q", u"W", u"E", u"R", u"T", u"Z", u"U", u"I", u"O", u"P", u"??", u"*"],
				[u"A", u"S", u"D", u"F", u"G", u"H", u"J", u"K", u"L", u"??", u"??", u"'"],
				[u">", u"Y", u"X", u"C", u"V", u"B", u"N", u"M", u";", u":", u"_", u"CLEAR"],
				[u"SHIFT", u"SPACE", u"?", u"\\", u"OK"]]
			self.nextLang = 'es_ES'
		elif self.lang == 'es_ES':
			#still missing keys (u"????")
			self.keys_list = [
				[u"EXIT", u"1", u"2", u"3", u"4", u"5", u"6", u"7", u"8", u"9", u"0", u"BACKSPACE"],
				[u"q", u"w", u"e", u"r", u"t", u"z", u"u", u"i", u"o", u"p", u"??", u"+"],
				[u"a", u"s", u"d", u"f", u"g", u"h", u"j", u"k", u"l", u"??", u"??", u"#"],
				[u"<", u"y", u"x", u"c", u"v", u"b", u"n", u"m", u",", ".", u"-", u"CLEAR"],
				[u"SHIFT", u"SPACE", u"@", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"OK"]]
			self.shiftkeys_list = [
				[u"EXIT", u"!", u'"', u"??", u"$", u"%", u"&", u"/", u"(", u")", u"=", u"BACKSPACE"],
				[u"Q", u"W", u"E", u"R", u"T", u"Z", u"U", u"I", u"O", u"P", u"??", u"*"],
				[u"A", u"S", u"D", u"F", u"G", u"H", u"J", u"K", u"L", u"??", u"??", u"'"],
				[u">", u"Y", u"X", u"C", u"V", u"B", u"N", u"M", u";", u":", u"_", u"CLEAR"],
				[u"SHIFT", u"SPACE", u"?", u"\\", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"OK"]]
			self.nextLang = 'fi_FI'
		elif self.lang == 'fi_FI':
			self.keys_list = [
				[u"EXIT", u"1", u"2", u"3", u"4", u"5", u"6", u"7", u"8", u"9", u"0", u"BACKSPACE"],
				[u"q", u"w", u"e", u"r", u"t", u"z", u"u", u"i", u"o", u"p", u"??", u"+"],
				[u"a", u"s", u"d", u"f", u"g", u"h", u"j", u"k", u"l", u"??", u"??", u"#"],
				[u"<", u"y", u"x", u"c", u"v", u"b", u"n", u"m", u",", ".", u"-", u"CLEAR"],
				[u"SHIFT", u"SPACE", u"@", u"??", u"??", u"OK"]]
			self.shiftkeys_list = [
				[u"EXIT", u"!", u'"', u"??", u"$", u"%", u"&", u"/", u"(", u")", u"=", u"BACKSPACE"],
				[u"Q", u"W", u"E", u"R", u"T", u"Z", u"U", u"I", u"O", u"P", u"??", u"*"],
				[u"A", u"S", u"D", u"F", u"G", u"H", u"J", u"K", u"L", u"??", u"??", u"'"],
				[u">", u"Y", u"X", u"C", u"V", u"B", u"N", u"M", u";", u":", u"_", u"CLEAR"],
				[u"SHIFT", u"SPACE", u"?", u"\\", u"??", u"OK"]]
			self.nextLang = 'ru_RU'
		elif self.lang == 'ru_RU':
			self.keys_list = [
				[u"EXIT", u"1", u"2", u"3", u"4", u"5", u"6", u"7", u"8", u"9", u"0", u"BACKSPACE"],
				[u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"+"],
				[u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"#"],
				[u"<", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u",", ".", u"-", u"CLEAR"],
				[u"SHIFT", u"SPACE", u"@", u"??", u"??", u"??", u"??", u"OK"]]
			self.shiftkeys_list = [
				[u"EXIT", u"!", u'"', u"??", u"$", u"%", u"&", u"/", u"(", u")", u"=", u"BACKSPACE"],
				[u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"*"],
				[u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"'"],
				[u">", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u";", u":", u"_", u"CLEAR"],
				[u"SHIFT", u"SPACE", u"?", u"\\", u"??", u"??", u"??",  u"??", u"OK"]]
			self.nextLang = 'sv_SE'
		elif self.lang == 'sv_SE':
			self.keys_list = [
				[u"EXIT", u"1", u"2", u"3", u"4", u"5", u"6", u"7", u"8", u"9", u"0", u"BACKSPACE"],
				[u"q", u"w", u"e", u"r", u"t", u"z", u"u", u"i", u"o", u"p", u"??", u"+"],
				[u"a", u"s", u"d", u"f", u"g", u"h", u"j", u"k", u"l", u"??", u"??", u"#"],
				[u"<", u"y", u"x", u"c", u"v", u"b", u"n", u"m", u",", ".", u"-", u"CLEAR"],
				[u"SHIFT", u"SPACE", u"@", u"??", u"??", u"OK"]]
			self.shiftkeys_list = [
				[u"EXIT", u"!", u'"', u"??", u"$", u"%", u"&", u"/", u"(", u")", u"=", u"BACKSPACE"],
				[u"Q", u"W", u"E", u"R", u"T", u"Z", u"U", u"I", u"O", u"P", u"??", u"*"],
				[u"A", u"S", u"D", u"F", u"G", u"H", u"J", u"K", u"L", u"??", u"??", u"'"],
				[u">", u"Y", u"X", u"C", u"V", u"B", u"N", u"M", u";", u":", u"_", u"CLEAR"],
				[u"SHIFT", u"SPACE", u"?", u"\\", u"??", u"OK"]]
			self.nextLang = 'sk_SK'
		elif self.lang =='sk_SK':
			self.keys_list = [
				[u"EXIT", u"1", u"2", u"3", u"4", u"5", u"6", u"7", u"8", u"9", u"0", u"BACKSPACE"],
				[u"q", u"w", u"e", u"r", u"t", u"z", u"u", u"i", u"o", u"p", u"??", u"+"],
				[u"a", u"s", u"d", u"f", u"g", u"h", u"j", u"k", u"l", u"??", u"@", u"#"],
				[u"<", u"y", u"x", u"c", u"v", u"b", u"n", u"m", u",", ".", u"-", u"CLEAR"],
				[u"SHIFT", u"SPACE", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"OK"]]
			self.shiftkeys_list = [
				[u"EXIT", u"!", u'"', u"??", u"$", u"%", u"&", u"/", u"(", u")", u"=", u"BACKSPACE"],
				[u"Q", u"W", u"E", u"R", u"T", u"Z", u"U", u"I", u"O", u"P", u"??", u"*"],
				[u"A", u"S", u"D", u"F", u"G", u"H", u"J", u"K", u"L", u"??", u"??", u"'"],
				[u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"??"],
				[u">", u"Y", u"X", u"C", u"V", u"B", u"N", u"M", u";", u":", u"_", u"CLEAR"],
				[u"SHIFT", u"SPACE", u"?", u"\\", u"??", u"??", u"??", u"??", u"??", u"??", u"OK"]]
			self.nextLang = 'cs_CZ'
		elif self.lang == 'cs_CZ':
			self.keys_list = [
				[u"EXIT", u"1", u"2", u"3", u"4", u"5", u"6", u"7", u"8", u"9", u"0", u"BACKSPACE"],
				[u"q", u"w", u"e", u"r", u"t", u"z", u"u", u"i", u"o", u"p", u"??", u"+"],
				[u"a", u"s", u"d", u"f", u"g", u"h", u"j", u"k", u"l", u"??", u"@", u"#"],
				[u"<", u"y", u"x", u"c", u"v", u"b", u"n", u"m", u",", ".", u"-", u"CLEAR"],
				[u"SHIFT", u"SPACE", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"OK"]]
			self.shiftkeys_list = [
				[u"EXIT", u"!", u'"', u"??", u"$", u"%", u"&", u"/", u"(", u")", u"=", u"BACKSPACE"],
				[u"Q", u"W", u"E", u"R", u"T", u"Z", u"U", u"I", u"O", u"P", u"??", u"*"],
				[u"A", u"S", u"D", u"F", u"G", u"H", u"J", u"K", u"L", u"??", u"??", u"'"],
				[u">", u"Y", u"X", u"C", u"V", u"B", u"N", u"M", u";", u":", u"_", u"CLEAR"],
				[u"SHIFT", u"SPACE", u"?", u"\\", u"??", u"??", u"??", u"??", u"??", u"??", u"??", u"OK"]]
			self.nextLang = 'en_GB'
		else:
			self.keys_list = [
				[u"EXIT", u"1", u"2", u"3", u"4", u"5", u"6", u"7", u"8", u"9", u"0", u"BACKSPACE"],
				[u"q", u"w", u"e", u"r", u"t", u"z", u"u", u"i", u"o", u"p", u"+", u"@"],
				[u"a", u"s", u"d", u"f", u"g", u"h", u"j", u"k", u"l", u"#", u"\\"],
				[u"<", u"y", u"x", u"c", u"v", u"b", u"n", u"m", u",", ".", u"-", u"CLEAR"],
				[u"SHIFT", u"SPACE", u"OK"]]
			self.shiftkeys_list = [
				[u"EXIT", u"!", u'"', u"??", u"$", u"%", u"&", u"/", u"(", u")", u"=", u"BACKSPACE"],
				[u"Q", u"W", u"E", u"R", u"T", u"Z", u"U", u"I", u"O", u"P", u"*"],
				[u"A", u"S", u"D", u"F", u"G", u"H", u"J", u"K", u"L", u"'", u"?"],
				[u">", u"Y", u"X", u"C", u"V", u"B", u"N", u"M", u";", u":", u"_", u"CLEAR"],
				[u"SHIFT", u"SPACE", u"OK"]]
			self.lang = 'en_GB'
			self.nextLang = 'de_DE'		
		self["country"].setText(self.lang)

	def buildVirtualKeyBoard(self, selectedKey=0):
		list = []
		
		if self.shiftMode:
			self.k_list = self.shiftkeys_list
			for keys in self.k_list:
				if selectedKey < self.LINESIZE and selectedKey > -1:
					list.append(VirtualKeyBoardEntryComponent(keys, selectedKey,True))
				else:
					list.append(VirtualKeyBoardEntryComponent(keys, -1,True))
				selectedKey -= self.LINESIZE
		else:
			self.k_list = self.keys_list
			for keys in self.k_list:
				if selectedKey < self.LINESIZE and selectedKey > -1:
					list.append(VirtualKeyBoardEntryComponent(keys, selectedKey))
				else:
					list.append(VirtualKeyBoardEntryComponent(keys, -1))
				selectedKey -= self.LINESIZE
		self.lines = len(self.k_list)
		self.max_key = (self.lines - 1) * self.LINESIZE #len of all lines but last (may be shorter)
		self.max_key += len(self.k_list[-1]) - 1 #len of last line
		self["list"].setList(list)
	
	def backClicked(self):
		self.nextKey()
		self.editing = False
		self["text"].setMarkedPos(-1)
		self.text = self["text"].getText()[:-1]
		self["text"].setText(self.text)
			
	def okClicked(self):
		self.nextKey()
		self.editing = False
		self["text"].setMarkedPos(-1)
		if self.shiftMode:
			list = self.shiftkeys_list
		else:
			list = self.keys_list
		
		selectedKey = self.selectedKey

		text = None

		for x in list:
			if selectedKey < self.LINESIZE:
				if selectedKey < len(x):
					text = x[selectedKey]
				break
			else:
				selectedKey -= self.LINESIZE

		if text is None:
			return

		text = six.ensure_str(text)

		if text == "EXIT":
			self.close(None)
		
		elif text == "BACKSPACE":
			self.text = self["text"].getText()[:-1]
			self["text"].setText(self.text)
		
		elif text == "CLEAR":
			self.text = ""
			self["text"].setText(self.text)
		
		elif text == "SHIFT":
			if self.shiftMode:
				self.shiftMode = False
			else:
				self.shiftMode = True
			
			self.buildVirtualKeyBoard(self.selectedKey)
		
		elif text == "SPACE":
			self.text += " "
			self["text"].setText(self.text)
		
		elif text == "OK":
			self.close(self["text"].getText())
		
		else:
			self.text = self["text"].getText()
			self.text += text
			self["text"].setText(self.text)

	def ok(self):
		self.close(self["text"].getText())

	def exit(self):
		self.close(None)

	def left(self):
		self.selectedKey -= 1
		for line in range(0,self.LINESIZE):
			if self.selectedKey == (self.LINESIZE * line) - 1:
				selectedKey = ((line + 1) * self.LINESIZE) - 1
				self.selectedKey = min(self.max_key, selectedKey)
				break
		self.showActiveKey()

	def right(self):
		self.selectedKey += 1
		if self.selectedKey > self.max_key:
			self.selectedKey = (self.lines - 1) * self.LINESIZE
		else:
			for line in range(0,self.LINESIZE):
				if self.selectedKey == self.LINESIZE * ( line + 1 ):
					self.selectedKey = line * self.LINESIZE
					break
		self.showActiveKey()

	def up(self):
		lines = self.lines
		self.selectedKey -= self.LINESIZE

		if (self.selectedKey < 0) and (self.selectedKey >= (self.max_key - lines * self.LINESIZE)):
			self.selectedKey += self.LINESIZE * (lines -1)
		elif self.selectedKey < 0:
			self.selectedKey += self.LINESIZE * lines
		self.showActiveKey()

	def down(self):
		lines = self.lines
		self.selectedKey += self.LINESIZE
		if (self.selectedKey > self.max_key) and (self.selectedKey > (lines * self.LINESIZE) - 1):
			self.selectedKey -= lines * self.LINESIZE
		elif self.selectedKey > self.max_key:
			self.selectedKey -= (lines - 1) * self.LINESIZE
		self.showActiveKey()

	def showActiveKey(self):
		self.buildVirtualKeyBoard(self.selectedKey)

	def inShiftKeyList(self,key):
		for KeyList in self.shiftkeys_list:
			for char in KeyList:
				if char == key:
					return True
		return False

	def keyGotAscii(self):
		char = six.ensure_str(unichr(getPrevAsciiCode()))
		if self.inShiftKeyList(char):
			self.shiftMode = True
			list = self.shiftkeys_list
		else:
			self.shiftMode = False
			list = self.keys_list	

		if char == " ":
			char = "SPACE"

		selkey = 0
		for keylist in list:
			for key in keylist:
				if key == char:
					self.selectedKey = selkey
					self.okClicked()
					self.showActiveKey()
					return
				else:
					selkey += 1

	def keyNumberGlobal(self, number):
		unichar = self.getKey(number)
		if not self.editing:
			self.text = self["text"].getText()
			self.editing = True
			self["text"].setMarkedPos(len(self.text))
		self["text"].setText(self.text + six.ensure_str(unichar))

	def nextFunc(self):
		self.text = self["text"].getText()
		self.editing = False
		self["text"].setMarkedPos(-1)
