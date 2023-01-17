from Tools.Directories import resolveFilename, SCOPE_SYSETC
from enigma import getEnigmaVersionString
from Tools.IO import runPipe

class About:
	def __init__(self):
		pass

	def getVersionString(self):
		return self.getImageVersionString()

	def getImageVersionString(self):
		try:
			file = open(resolveFilename(SCOPE_SYSETC, 'image-version'), 'r')
			lines = file.readlines()
			for x in lines:
				splitted = x.split('=')
				if splitted[0] == "version":
					#     YYYY MM DD hh mm
					#0120 2005 11 29 01 16
					#0123 4567 89 01 23 45
					version = splitted[1]
					image_type = version[0] # 0 = release, 1 = experimental
					major = version[1]
					minor = version[2]
					revision = version[3]
					year = version[4:8]
					month = version[8:10]
					day = version[10:12]
					date = '-'.join((year, month, day))
					if image_type == '0':
						image_type = "Release"
					else:
						image_type = "Experimental"
					version = '.'.join((major, minor, revision))
					if version != '0.0.0':
						return ' '.join((image_type, version, date))
					else:
						return ' '.join((image_type, date))
			file.close()
		except IOError:
			pass

		return "unavailable"

	def getEnigmaVersionString(self):
		return getEnigmaVersionString()

	def getKernelVersionString(self):
		try:
			_, output = runPipe(['uname', '-r'])
			return output.split('-')[0]
		except:
			pass

		return "unknown"

about = About()
