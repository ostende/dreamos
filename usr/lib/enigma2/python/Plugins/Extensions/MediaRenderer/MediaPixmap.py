from enigma import ePicLoad
from Components.AVSwitch import AVSwitch
from Components.Pixmap import Pixmap
from Tools.Directories import resolveFilename, SCOPE_CURRENT_SKIN, fileExists

from Tools.Log import Log

class MediaPixmap(Pixmap):
	def __init__(self):
		Pixmap.__init__(self)
		self.pictureFileName = "__default__"
		self.defaultPixmap = None

		self.picload = ePicLoad()
		self.picload_conn = self.picload.PictureData.connect(self.paintPixmapCB)
		self.pictureFileNames = ["cover.jpg", "folder.png", "folder.jpg"]

	def embeddedCoverArt(self):
		Log.i("found")
		self.pictureFileName = "/tmp/.id3coverart"
		self.picload.startDecode(self.pictureFileName)

	def applySkin(self, desktop, screen):
		from Tools.LoadPixmap import LoadPixmap
		defaultPixmap = None
		if self.skinAttributes is not None:
			for (attrib, value) in self.skinAttributes:
				if attrib == "pixmap":
					defaultPixmap = value
					break
		if defaultPixmap is None:
			defaultPixmap = resolveFilename(SCOPE_CURRENT_SKIN, )
		self.defaultPixmap = LoadPixmap(defaultPixmap)

		return Pixmap.applySkin(self, desktop, screen)

	def execBegin(self):
		Pixmap.execBegin(self)
		sc = AVSwitch().getFramebufferScale()
		#0=Width 1=Height 2=Aspect 3=use_cache 4=resize_type 5=Background(#AARRGGBB)
		size = self.instance.size()
		self.picload.setPara((size.width(), size.height(), sc[0], sc[1], True, 1, "#00000000"))

	def paintPixmapCB(self, picInfo=None):
		ptr = self.picload.getData()
		if ptr != None:
			self.instance.setPixmap(ptr)

	def setPicturePath(self, path):
		newPictureFileName = path
		if path.endswith("/"):
			for filename in self.pictureFileNames:
				if fileExists(path + filename):
					newPictureFileName = path + filename
		if self.pictureFileName != newPictureFileName:
			self.pictureFileName = newPictureFileName
			if self.pictureFileName:
				self.picload.startDecode(self.pictureFileName)
			else:
				self.setDefaultPicture()

	def setDefaultPicture(self):
		Log.i("called")
		self.pictureFileName ="__default__"
		self.instance.setPixmap(self.defaultPixmap)
