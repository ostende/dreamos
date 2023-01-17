from __future__ import division
from __future__ import print_function
from Screens.Screen import Screen
from Screens.ChannelSelection import ChannelSelectionBase
from Components.ActionMap import ActionMap
from Components.Sources.StaticText import StaticText
from Components.config import config, ConfigNothing
from Components.ConfigList import ConfigList
from Components.NimManager import nimmanager
from Components.SelectionList import SelectionList
from ServiceReference import ServiceReference
from Plugins.Plugin import PluginDescriptor
from xml.etree.cElementTree import parse as ci_parse
from enigma import eDVBCI_UI, eDVBCIInterfaces, eEnv, eServiceReference, eServiceCenter

from os import path as os_path, unlink as os_unlink, fsync
from xml.sax.saxutils import escape as xml_escape, unescape as xml_unescape
from six.moves import range

class CIselectMainMenu(Screen):
	skin = """
		<screen name="CIselectMainMenu" position="center,120" size="820,520" title="CI Assignment">
			<ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="200,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="210,5" size="200,40" alphatest="on" />
			<widget source="key_red" render="Label" position="10,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<widget source="key_green" render="Label" position="210,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<eLabel position="10,50" size="800,1" backgroundColor="grey" />
			<widget name="CiList" position="10,60" size="800,450" enableWrapAround="1" scrollbarMode="showOnDemand" />
		</screen>"""

	def __init__(self, session, args = 0):

		Screen.__init__(self, session)

		self["key_red"] = StaticText(_("Close"))
		self["key_green"] = StaticText(_("Edit"))

		self["actions"] = ActionMap(["ColorActions","SetupActions"],
			{
				"green": self.greenPressed,
				"red": self.close,
				"ok": self.greenPressed,
				"cancel": self.close
			}, -1)

		NUM_CI=eDVBCIInterfaces.getInstance().getNumOfSlots()

		print("[CI_Wizzard] FOUND %d CI Slots " % NUM_CI)

		self.dlg = None
		self.state = { }
		self.list = [ ]
		if NUM_CI > 0:
			for slot in range(NUM_CI):
				state = eDVBCI_UI.getInstance().getState(slot)
				if state == 0:
					appname = _("Slot %d") %(slot+1) + " - " + _("no module found")
				elif state == 1:	
					appname = _("Slot %d") %(slot+1) + " - " + _("init modules")
				elif state == 2:
					appname = _("Slot %d") %(slot+1) + " - " + eDVBCI_UI.getInstance().getAppName(slot)
				if state != -1:
					self.list.append( (appname, ConfigNothing(), 0, slot) )
		if not self.list:
			self.list.append( (_("no CI slots found") , ConfigNothing(), 1, -1) )

		menuList = ConfigList(self.list)
		menuList.list = self.list
		menuList.l.setList(self.list)
		self["CiList"] = menuList
		self.onShown.append(self.setWindowTitle)

	def setWindowTitle(self):
		self.setTitle(_("CI assignment"))

	def greenPressed(self):
		cur = self["CiList"].getCurrent()
		if cur and len(cur) > 2:
			action = cur[2]
			slot = cur[3]
			if action == 1:
				print("[CI_Wizzard] there is no CI Slot in your receiver")
			else:
				print("[CI_Wizzard] selected CI Slot : %d" % slot)
				if config.usage.setup_level.index > 1: # advanced
					self.session.open(CIconfigMenu, slot)
				else:
					self.session.open(easyCIconfigMenu, slot)

	"""def yellowPressed(self): # unused
		NUM_CI=eDVBCIInterfaces.getInstance().getNumOfSlots()
		print "[CI_Check] FOUND %d CI Slots " % NUM_CI
		if NUM_CI > 0:
			for ci in range(NUM_CI):
				print eDVBCIInterfaces.getInstance().getDescrambleRules(ci)"""


class CIconfigMenu(Screen):
	skin = """
		<screen name="CIconfigMenu" position="center,120" size="820,520" title="CI Assignment">
			<ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="200,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="210,5" size="200,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/yellow.png" position="410,5" size="200,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/blue.png" position="610,5" size="200,40" alphatest="on" />
			<widget source="key_red" render="Label" position="10,5" size="200,40" zPosition="1" font="Regular;19" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<widget source="key_green" render="Label" position="210,5" size="200,40" zPosition="1" font="Regular;19" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<widget source="key_yellow" render="Label" position="410,5" size="200,40" zPosition="1" font="Regular;19" halign="center" valign="center" backgroundColor="#a08500" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<widget source="key_blue" render="Label" position="610,5" size="200,40" zPosition="1" font="Regular;19" halign="center" valign="center" backgroundColor="#18188b" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<eLabel position="10,50" size="800,1" backgroundColor="grey" />
			<widget source="CAidList_desc" render="Label" position="10,55" size="800,27" font="Regular;22" />
			<eLabel position="10,85" size="800,1" backgroundColor="grey" />
			<widget source="CAidList" render="Label" position="10,95" size="800,90" font="Regular;20" />
			<eLabel position="10,200" size="800,1" backgroundColor="grey" />
			<widget source="ServiceList_desc" render="Label" position="10,205" size="800,27" font="Regular;22" />
			<eLabel position="10,235" size="800,1" backgroundColor="grey" />
			<widget name="ServiceList" position="10,245" size="800,240" enableWrapAround="1" scrollbarMode="showOnDemand" />
			<widget source="ServiceList_info" render="Label" position="10,245" size="800,240" font="Regular;22" />
		</screen>"""

	def __init__(self, session, ci_slot="9"):

		Screen.__init__(self, session)
		self.ci_slot=ci_slot
		self.filename = eEnv.resolve("${sysconfdir}/enigma2/ci") + str(self.ci_slot) + ".xml"

		self["key_red"] = StaticText(_("Delete"))
		self["key_green"] = StaticText(_("add Service"))
		self["key_yellow"] = StaticText(_("add Provider"))
		self["key_blue"] = StaticText(_("select CAId"))
		self["CAidList_desc"] = StaticText(_("assigned CAIds:"))
		self["CAidList"] = StaticText()
		self["ServiceList_desc"] = StaticText(_("assigned Services/Provider:"))
		self["ServiceList_info"] = StaticText()

		self["actions"] = ActionMap(["ColorActions","SetupActions"],
			{
				"green": self.greenPressed,
				"red": self.redPressed,
				"yellow": self.yellowPressed,
				"blue": self.bluePressed,
				"cancel": self.cancel
			}, -1)

		print("[CI_Wizzard_Config] Configuring CI Slots : %d  " % self.ci_slot)

		i=0
		self.caidlist=[]
		print(eDVBCIInterfaces.getInstance().readCICaIds(self.ci_slot))
		for caid in eDVBCIInterfaces.getInstance().readCICaIds(self.ci_slot):
			i+=1
			self.caidlist.append((str(hex(int(caid))),str(caid),i))

		print("[CI_Wizzard_Config_CI%d] read following CAIds from CI: %s" %(self.ci_slot, self.caidlist))

		self.selectedcaid = []
		self.servicelist = []
		self.caids = ""

		serviceList = ConfigList(self.servicelist)
		serviceList.list = self.servicelist
		serviceList.l.setList(self.servicelist)
		self["ServiceList"] = serviceList

		self.loadXML()
		# if config mode !=advanced autoselect any caid
		if config.usage.setup_level.index <= 1: # advanced
			self.selectedcaid=self.caidlist
			self.finishedCAidSelection(self.selectedcaid)
		self.onShown.append(self.setWindowTitle)

	def setWindowTitle(self):
		self.setTitle(_("CI assignment"))

	def redPressed(self):
		self.delete()

	def greenPressed(self):
		self.session.openWithCallback( self.finishedChannelSelection, myChannelSelection, None)

	def yellowPressed(self):
		self.session.openWithCallback( self.finishedProviderSelection, myProviderSelection, None)

	def bluePressed(self):
		self.session.openWithCallback(self.finishedCAidSelection, CAidSelect, self.caidlist, self.selectedcaid)

	def cancel(self):
		self.saveXML()
		activate_all(self)
		self.close()

	def setServiceListInfo(self):
		if len(self.servicelist):
			self["ServiceList_info"].setText("")
		else:
			self["ServiceList_info"].setText(_("no Services/Providers selected"))

	def delete(self):
		cur = self["ServiceList"].getCurrent()
		if cur and len(cur) > 2:
			self.servicelist.remove(cur)
		self["ServiceList"].l.setList(self.servicelist)
		self.setServiceListInfo()

	def finishedChannelSelection(self, *args):
		if len(args):
			ref=args[0]
			service_ref = ServiceReference(ref)
			service_name = service_ref.getServiceName()
			if find_in_list(self.servicelist, service_name, 0)==False:
				split_ref=service_ref.ref.toString().split(":")
				if split_ref[0] == "1":#== dvb service und nicht muell von None
					self.servicelist.append( (service_name , ConfigNothing(), 0, service_ref.ref.toString()) )
					self["ServiceList"].l.setList(self.servicelist)
					self.setServiceListInfo()

	def finishedProviderSelection(self, *args):
		if len(args)>1: # bei nix selected kommt nur 1 arg zurueck (==None)
			name=args[0]
			dvbnamespace=args[1]
			if find_in_list(self.servicelist, name, 0)==False:
				self.servicelist.append( (name , ConfigNothing(), 1, dvbnamespace) )
				self["ServiceList"].l.setList(self.servicelist)
				self.setServiceListInfo()

	def finishedCAidSelection(self, *args):
		if len(args):
			self.selectedcaid=args[0]
			self.caids=""
			if len(self.selectedcaid):
				for item in self.selectedcaid:
					if len(self.caids):
						self.caids+= ", " + item[0]
					else:
						self.caids=item[0]
			else:
				self.selectedcaid=[]
				self.caids=_("no CAId selected")
		else:
			self.selectedcaid=[]
			self.caids=_("no CAId selected")
		self["CAidList"].setText(self.caids)

	def saveXML(self):
		try:
			fp = open(self.filename, 'w')
			fp.write("<?xml version=\"1.0\" encoding=\"utf-8\" ?>\n")
			fp.write("<ci>\n")
			fp.write("\t<slot>\n")
			fp.write("\t\t<id>%s</id>\n" % self.ci_slot)
			for item in self.selectedcaid:
				if len(self.selectedcaid):
					fp.write("\t\t<caid id=\"%s\" />\n" % item[0])
			for item in self.servicelist:
				if len(self.servicelist):
					psname = xml_escape(item[0])
					psattr = xml_escape(item[3])
					if item[2]==1:
						fp.write("\t\t<provider name=\"%s\" dvbnamespace=\"%s\" />\n" % (psname, psattr))
					else:
						fp.write("\t\t<service name=\"%s\" ref=\"%s\" />\n"  % (psname, psattr))
			fp.write("\t</slot>\n")
			fp.write("</ci>\n")
			fp.flush()
			fsync(fp.fileno())
			fp.close()
		except:
			print("[CI_Config_CI%d] xml not written" %self.ci_slot)
			os_unlink(self.filename)

	def loadXML(self):
		if not os_path.exists(self.filename):
			return

		def getValue(definitions, default):
			Len = len(definitions)
			return Len > 0 and definitions[Len-1].text or default

		try:
			tree = ci_parse(self.filename).getroot()
			self.read_services=[]
			self.read_providers=[]
			self.usingcaid=[]
			self.ci_config=[]
			for slot in tree.findall("slot"):
				read_slot = getValue(slot.findall("id"), False).encode("UTF-8")
				print("ci " + read_slot)

				i=0
				for caid in slot.findall("caid"):
					read_caid = caid.get("id").encode("UTF-8")
					self.selectedcaid.append((str(read_caid),str(read_caid),i))
					self.usingcaid.append(int(read_caid,16))
					i+=1

				for service in  slot.findall("service"):
					read_service_ref = xml_unescape( service.get("ref").encode("UTF-8") )
					self.read_services.append (read_service_ref)

				for provider in  slot.findall("provider"):
					read_provider_name = xml_unescape( provider.get("name").encode("UTF-8") )
					read_provider_dvbname = xml_unescape( provider.get("dvbnamespace").encode("UTF-8") )
					self.read_providers.append((read_provider_name,read_provider_dvbname))

				self.ci_config.append((int(read_slot), (self.read_services, self.read_providers, self.usingcaid)))
		except:
			print("[CI_Config_CI%d] error parsing xml..." %self.ci_slot)

		for item in self.read_services:
			if len(item):
				self.finishedChannelSelection(item)

		for item in self.read_providers:
			if len(item):
				self.finishedProviderSelection(item[0],item[1])

		print(self.ci_config)
		self.finishedCAidSelection(self.selectedcaid)
		self["ServiceList"].l.setList(self.servicelist)
		self.setServiceListInfo()


class easyCIconfigMenu(CIconfigMenu):
	skin = """
		<screen name="easyCIconfigMenu" position="center,120" size="820,520" title="CI Assignment">
			<ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="200,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="210,5" size="200,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/yellow.png" position="410,5" size="200,40" alphatest="on" />
			<widget source="key_red" render="Label" position="10,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<widget source="key_green" render="Label" position="210,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<widget source="key_yellow" render="Label" position="410,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<eLabel position="10,50" size="800,1" backgroundColor="grey" />
			<widget source="ServiceList_desc" render="Label" position="10,55" size="800,27" font="Regular;22" />
			<eLabel position="10,85" size="800,1" backgroundColor="grey" />
			<widget name="ServiceList" position="10,95" size="800,420" enableWrapAround="1" scrollbarMode="showOnDemand" />
			<widget source="ServiceList_info" render="Label" position="10,95" size="800,420" font="Regular;22" />
		</screen>"""

	def __init__(self, session, ci_slot="9"):
		CIconfigMenu.__init__(self, session, ci_slot)

		self["actions"] = ActionMap(["ColorActions","SetupActions"],
		{
			"green": self.greenPressed,
			"red": self.redPressed,
			"yellow": self.yellowPressed,
			"cancel": self.cancel
		})


class CAidSelect(Screen):
	skin = """
		<screen name="CAidSelect" position="center,120" size="820,520" title="select CAId's">
			<ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="200,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="210,5" size="200,40" alphatest="on" />
			<widget source="key_red" render="Label" position="10,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<widget source="key_green" render="Label" position="210,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<eLabel position="10,50" size="800,1" backgroundColor="grey" />
			<widget name="list" position="10,55" size="800,420" enableWrapAround="1" scrollbarMode="showOnDemand" />
			<eLabel position="10,480" size="800,1" backgroundColor="grey" />
			<widget source="introduction" render="Label" position="10,488" size="800,25" font="Regular;22" halign="center" />
		</screen>"""

	def __init__(self, session, list, selected_caids):

		Screen.__init__(self, session)

		self.list = SelectionList()
		self["list"] = self.list

		for listindex in range(len(list)):
			if find_in_list(selected_caids,list[listindex][0],0):
				self.list.addSelection(list[listindex][0], list[listindex][1], listindex, True)
			else:
				self.list.addSelection(list[listindex][0], list[listindex][1], listindex, False)

		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("Save"))
		self["introduction"] = StaticText(_("Press OK to select/deselect a CAId."))

		self["actions"] = ActionMap(["ColorActions","SetupActions"],
		{
			"ok": self.list.toggleSelection, 
			"cancel": self.cancel, 
			"green": self.greenPressed,
			"red": self.cancel
		}, -1)
		self.onShown.append(self.setWindowTitle)

	def setWindowTitle(self):
		self.setTitle(_("select CAId's"))

	def greenPressed(self):
		list = self.list.getSelectionsList()
		print(list)
		self.close(list)

	def cancel(self):
		self.close()

class myProviderSelection(ChannelSelectionBase):
	skin = """
		<screen name="myProviderSelection" position="center,120" size="820,520" title="Select provider to add...">
			<ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="200,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="210,5" size="200,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/yellow.png" position="410,5" size="200,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/blue.png" position="610,5" size="200,40" alphatest="on" />
			<widget source="key_red" render="Label" position="10,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<widget source="key_green" render="Label" position="210,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<widget source="key_yellow" render="Label" position="410,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<widget source="key_blue" render="Label" position="610,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#18188b" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<eLabel position="10,50" size="800,1" backgroundColor="grey" />
			<widget name="list" position="10,55" size="800,420" enableWrapAround="1" scrollbarMode="showOnDemand" />
			<eLabel position="10,480" size="800,1" backgroundColor="grey" />
			<widget source="introduction" render="Label" position="10,488" size="800,25" font="Regular;22" halign="center"  />
		</screen>"""

	def __init__(self, session, title):
		ChannelSelectionBase.__init__(self, session)
		self.onShown.append(self.__onExecCallback)

		self["actions"] = ActionMap(["OkCancelActions", "ChannelSelectBaseActions"],
			{
				"showFavourites": self.doNothing,
				"showAllServices": self.cancel,
				"showProviders": self.doNothing,
				"showSatellites": self.doNothing,
				"cancel": self.cancel,
				"ok": self.channelSelected
			})
		self["key_red"] = StaticText(_("Close"))
		self["key_green"] = StaticText()
		self["key_yellow"] = StaticText()
		self["key_blue"] = StaticText()
		self["introduction"] = StaticText(_("Press OK to select a Provider."))

	def doNothing(self):
		pass

	def __onExecCallback(self):
		self.showSatellites()
		self.setTitle(_("Select provider to add..."))

	def channelSelected(self): # just return selected service
		ref = self.getCurrentSelection()
		splited_ref=ref.toString().split(":")
		if ref.flags == 7 and splited_ref[6] != "0":
			self.dvbnamespace=splited_ref[6]
			self.enterPath(ref)
		else:
			self.close(ref.getName(), self.dvbnamespace)

	def showSatellites(self):
		if not self.pathChangeDisabled:
			refstr = '%s FROM SATELLITES ORDER BY satellitePosition'%(self.service_types)
			if not self.preEnterPath(refstr):
				ref = eServiceReference(refstr)
				justSet=False
				prev = None

				if self.isBasePathEqual(ref):
					if self.isPrevPathEqual(ref):
						justSet=True
					prev = self.pathUp(justSet)
				else:
					currentRoot = self.getRoot()
					if currentRoot is None or currentRoot != ref:
						justSet=True
						self.clearPath()
						self.enterPath(ref, True)
				if justSet:
					serviceHandler = eServiceCenter.getInstance()
					servicelist = serviceHandler.list(ref)
					if not servicelist is None:
						while True:
							service = servicelist.getNext()
							if not service.valid(): #check if end of list
								break
							unsigned_orbpos = service.getUnsignedData(4) >> 16
							orbpos = service.getData(4) >> 16
							if orbpos < 0:
								orbpos += 3600
							if service.getPath().find("FROM PROVIDER") != -1:
								service_type = _("Providers")
								try:
									# why we need this cast?
									service_name = str(nimmanager.getSatDescription(orbpos))
								except:
									if unsigned_orbpos == 0xFFFF: #Cable
										service_name = _("Cable")
									elif unsigned_orbpos == 0xEEEE: #Terrestrial
										service_name = _("Terrestrial")
									else:
										if orbpos > 1800: # west
											orbpos = 3600 - orbpos
											h = _("W")
										else:
											h = _("E")
										service_name = ("%d.%d" + h) % (orbpos // 10, orbpos % 10)
								service.setName("%s - %s" % (service_name, service_type))
								self.servicelist.addService(service)
						self.servicelist.finishFill()
						if prev is not None:
							self.setCurrentSelection(prev)

	def cancel(self):
		self.close(None)

class myChannelSelection(ChannelSelectionBase):
	skin = """
		<screen name="myChannelSelection" position="center,120" size="820,520" title="Select service to add...">
			<ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="200,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="210,5" size="200,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/yellow.png" position="410,5" size="200,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/blue.png" position="610,5" size="200,40" alphatest="on" />
			<widget source="key_red" render="Label" position="10,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<widget source="key_green" render="Label" position="210,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<widget source="key_yellow" render="Label" position="410,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<widget source="key_blue" render="Label" position="610,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#18188b" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<eLabel position="10,50" size="800,1" backgroundColor="grey" />
			<widget name="list" position="10,55" size="800,420" enableWrapAround="1" scrollbarMode="showOnDemand" />
			<eLabel position="10,480" size="800,1" backgroundColor="grey" />
			<widget source="introduction" render="Label" position="10,488" size="800,25" font="Regular;22" halign="center" />
		</screen>"""

	def __init__(self, session, title):
		ChannelSelectionBase.__init__(self, session)
		self.onShown.append(self.__onExecCallback)

		self["actions"] = ActionMap(["OkCancelActions", "TvRadioActions", "ChannelSelectBaseActions"],
			{
				"showProviders": self.doNothing,
				"showSatellites": self.showAllServices,
				"showAllServices": self.cancel,
				"cancel": self.cancel,
				"ok": self.channelSelected,
				"keyRadio": self.setModeRadio,
				"keyTV": self.setModeTv
			})

		self["key_red"] = StaticText(_("Close"))
		self["key_green"] = StaticText(_("All"))
		self["key_yellow"] = StaticText()
		self["key_blue"] = StaticText(_("Favourites"))
		self["introduction"] = StaticText(_("Press OK to select a Provider."))

	def __onExecCallback(self):
		self.setModeTv()
		self.setTitle(_("Select service to add..."))

	def doNothing(self):
		pass

	def channelSelected(self): # just return selected service
		ref = self.getCurrentSelection()
		if (ref.flags & 7) == 7:
			self.enterPath(ref)
		elif not (ref.flags & eServiceReference.isMarker):
			ref = self.getCurrentSelection()
			self.close(ref)

	def setModeTv(self):
		self.setTvMode()
		self.showFavourites()

	def setModeRadio(self):
		self.setRadioMode()
		self.showFavourites()

	def cancel(self):
		self.close(None)

def activate_all(session):
	NUM_CI=eDVBCIInterfaces.getInstance().getNumOfSlots()
	print("[CI_Activate] FOUND %d CI Slots " % NUM_CI)
	if NUM_CI > 0:
		ci_config=[]
		def getValue(definitions, default):
			# How many definitions are present
			Len = len(definitions)
			return Len > 0 and definitions[Len-1].text or default	

		for ci in range(NUM_CI):
			filename = eEnv.resolve("${sysconfdir}/enigma2/ci") + str(ci) + ".xml"

			if not os_path.exists(filename):
				print("[CI_Activate_Config_CI%d] no config file found" %ci)

			try:
				tree = ci_parse(filename).getroot()
				read_services=set()
				read_providers=set()
				usingcaid=set()
				for slot in tree.findall("slot"):
					read_slot = getValue(slot.findall("id"), False).encode("UTF-8")

					for caid in slot.findall("caid"):
						read_caid = caid.get("id").encode("UTF-8")
						usingcaid.add(int(read_caid,16))

					for service in slot.findall("service"):
						read_service_ref = service.get("ref").encode("UTF-8")
						read_services.add(eServiceReference(read_service_ref))

					for provider in slot.findall("provider"):
						read_provider_name = provider.get("name").encode("UTF-8")
						read_provider_dvbname = provider.get("dvbnamespace").encode("UTF-8")
						read_providers.add((read_provider_name,int(read_provider_dvbname,16)))

					ci_config.append((int(read_slot), (read_services, read_providers, usingcaid)))
			except IOError:
				print("[CI_Activate_Config_CI%d] error parsing xml..." %ci)

		instance = eDVBCIInterfaces.getInstance()
		setProviderRules = instance.setProviderRules
		setCaidRules = instance.setCaidRules
		setServiceRules = instance.setServiceRules
		for item in ci_config:
			print("[CI_Activate] activate CI%d with following settings:" %item[0])
			print("services", [ x.toString() for x in item[1][0] ])
			print("providers", [ x for x in item[1][1] ])
			print("caids", [ x for x in item[1][2] ])
			setServiceRules(item[0], item[1][0]);
			setProviderRules(item[0], item[1][1]);
			setCaidRules(item[0], item[1][2]);

def find_in_list(list, search, listpos=0):
	for item in list:
		if item[listpos]==search:
			return True
	return False

global_session = None

def sessionstart(reason, session):
	global global_session
	global_session = session

def autostart(reason, **kwargs):
	global global_session
	if reason == 0:
		print("[CI_Assignment] activating ci configs:")
		activate_all(global_session)
	elif reason == 1:
		global_session = None

def main(session, **kwargs):
	session.open(CIselectMainMenu)

def menu(menuid, **kwargs):
	if menuid == "devices" and eDVBCIInterfaces.getInstance().getNumOfSlots():
		return [(_("Common Interface Assignment"), main, "ci_assign", 21)]
	return [ ]

def Plugins(**kwargs):
	if config.usage.setup_level.index > 1:
		return [PluginDescriptor( where = PluginDescriptor.WHERE_SESSIONSTART, needsRestart = False, fnc = sessionstart ),
				PluginDescriptor( where = PluginDescriptor.WHERE_AUTOSTART, needsRestart = False, fnc = autostart ),
				PluginDescriptor( name = "CommonInterfaceAssignment", description = _("a gui to assign services/providers/caids to common interface modules"), where = PluginDescriptor.WHERE_MENU, needsRestart = False, fnc = menu )]
	else:
		return [PluginDescriptor( where = PluginDescriptor.WHERE_SESSIONSTART, needsRestart = False, fnc = sessionstart ),
				PluginDescriptor( where = PluginDescriptor.WHERE_AUTOSTART, needsRestart = False, fnc = autostart ),
				PluginDescriptor( name = "CommonInterfaceAssignment", description = _("a gui to assign services/providers to common interface modules"), where = PluginDescriptor.WHERE_MENU, needsRestart = False, fnc = menu )]
