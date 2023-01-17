from __future__ import print_function
from datetime import datetime
from Tools.BoundFunction import boundFunction
from Tools.LoadPixmap import LoadPixmap
from Tools.Directories import resolveFilename, SCOPE_CURRENT_SKIN
import six

class NotificationQueueEntry():
	def __init__(self, fnc, screen, id, *args, **kwargs):
		self.timestamp = datetime.now()
		self.pending = True
		self.fnc = fnc
		self.screen = screen
		self.id = id
		self.args = args
		self.kwargs = kwargs
		self.domain = "default"

		if "domain" in kwargs:
			if kwargs["domain"]:
				if kwargs["domain"] in notificationQueue.domains:
					self.domain = kwargs["domain"]
				else:
					print("[NotificationQueueEntry] WARNING: domain", kwargs["domain"], "is not registred in notificationQueue!")
			del kwargs["domain"]

		if "deferred_callable" in kwargs:
			if kwargs["deferred_callable"]:
				self.deferred_callable = kwargs["deferred_callable"]
			del kwargs["deferred_callable"]
		else:
			self.deferred_callable = notificationQueue.domains[self.domain]["deferred_callable"]

		if "text" in kwargs:
			self.text = kwargs["text"]
		elif len(args) and isinstance(args, tuple) and isinstance(args[0],six.string_types):
			self.text = args[0]
		else:
			self.text = screen.__name__
		#print "[NotificationQueueEntry] QueueEntry created", self.timestamp, "function:", self.fnc, "screen:", self.screen, "id:", self.id, "args:", self.args, "kwargs:", self,kwargs, "domain:", self.domain, "text:", self.text

def isPendingOrVisibleNotificationID(id):
	q = notificationQueue
	return q.isVisibleID(id) or q.isPendingID(id)

def __AddNotification(fnc, screen, id, *args, **kwargs):
	entry = NotificationQueueEntry(fnc, screen, id, *args, **kwargs)
	notificationQueue.addEntry(entry)

def AddNotification(screen, *args, **kwargs):
	AddNotificationWithCallback(None, screen, *args, **kwargs)

def AddNotificationWithCallback(fnc, screen, *args, **kwargs):
	__AddNotification(fnc, screen, None, *args, **kwargs)

def AddNotificationWithID(id, screen, *args, **kwargs):
	q = notificationQueue
	if q.isVisibleID(id) or q.isPendingID(id):
		print("ignore duplicate notification", id, screen)
		return
	__AddNotification(None, screen, id, *args, **kwargs)

# we don't support notifications with callback and ID as this
# would require manually calling the callback on cancelled popups.

def RemovePopup(id):
	# remove similiar notifications
	print("RemovePopup, id =", id)
	notificationQueue.removeSameID(id)

from Screens.MessageBox import MessageBox

def AddPopup(text, type, timeout, id = None, domain = None, screen=MessageBox, additionalActionMap=None):
	if id is not None:
		RemovePopup(id)
	print("AddPopup, id =", id, "domain =", domain)
	__AddNotification(None, screen, id, text = text, type = type, timeout = timeout, close_on_any_key = True, domain = domain, additionalActionMap = additionalActionMap)

ICON_DEFAULT = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, 'skin_default/icons/marker.png'))
ICON_MAIL = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, 'skin_default/icons/notification_mail.png'))
ICON_TIMER = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, 'skin_default/icons/clock.png'))

class NotificationQueue():
	def __init__(self):
		self.queue = []
		self.__screen = None

		# notifications which are currently on screen (and might be closed by similiar notifications)
		self.current = [ ]

		# functions which will be called when new notification is added
		self.addedCB = [ ]

		self.domains = { "default": { "name": _("unspecified"), "icon": ICON_DEFAULT, "deferred_callable": False } }

	def registerDomain(self, key, name, icon = ICON_DEFAULT, deferred_callable = False):
		if not key in self.domains:
			self.domains[key] = { "name": name, "icon": icon, "deferred_callable": deferred_callable }

	def addEntry(self, entry):
		assert isinstance(entry, NotificationQueueEntry)

		self.queue.append(entry)
		for x in self.addedCB:
			x()

	def isPendingID(self, id):
		for entry in self.queue:
			if entry.pending and entry.id == id:
				return True
		return False

	def isVisibleID(self, id):
		for entry, dlg in self.current:
			if entry.id == id:
				return True
		return False

	def removeSameID(self, id):
		for entry in self.queue:
			if entry.pending and entry.id == id:
				print("(found in notifications)")
				self.queue.remove(entry)

		for entry, dlg in self.current:
			if entry.id == id:
				print("(found in current notifications)")
				dlg.close()

	def getPending(self, domain = None):
		res = []
		for entry in self.queue:
			if entry.pending and (domain == None or entry.domain == domain):
				res.append(entry)
		return res

	def popNotification(self, parent, entry = None):
		if entry:
			performCB = entry.deferred_callable
		else:
			pending = self.getPending()
			if len(pending):
				entry = pending[0]
			else:
				return
			performCB = True

		print("[NotificationQueue::popNotification] domain", entry.domain, "deferred_callable:", entry.deferred_callable)

		if performCB and "onSessionOpenCallback" in entry.kwargs:
			entry.kwargs["onSessionOpenCallback"]()
			del entry.kwargs["onSessionOpenCallback"]

		entry.pending = False
		if performCB and entry.fnc is not None:
			dlg = parent.session.openWithCallback(entry.fnc, entry.screen, *entry.args, **entry.kwargs)
		else:
			dlg = parent.session.open(entry.screen, *entry.args, **entry.kwargs)

		# remember that this notification is currently active
		d = (entry, dlg)
		self.current.append(d)
		dlg.onClose.append(boundFunction(self.__notificationClosed, d))

	def __notificationClosed(self, d):
		#print "[NotificationQueue::__notificationClosed]", d, self.current
		self.current.remove(d)

notificationQueue = NotificationQueue()
