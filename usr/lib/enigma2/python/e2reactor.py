# based on qt4reactor.py
# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.
# Original Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
# Original Ported to QT4: U{Gabe Rudy<mailto:rudy@goldenhelix.com>}

"""
This module provides support for Twisted to interact with Enigma2's mainloop.

Maintainer: U{Andreas Monzner<mailto:andreas.monzner@dream-property.net>}
"""

__all__ = ['install']

# System Imports
from enigma import runMainloop, quitMainloop, eSocketNotifier, eTimer
from select import POLLIN, POLLOUT

from zope.interface import implementer

from twisted.internet.interfaces import IReactorFDSet
from twisted.python import log
from twisted.internet.posixbase import PosixReactorBase

from sys import exc_info
from monotonic import monotonic

monotonic_time = monotonic

class TwistedSocketNotifier:
	"""
	Connection between an fd event and reader/writer callbacks.
	"""

	def __init__(self, reactor, watcher, type):
		self.sn = eSocketNotifier(watcher.fileno(), type)
		self.reactor = reactor
		self.watcher = watcher
		self.fn = None
		if type == POLLIN:
			self.fn = self.read
		elif type == POLLOUT:
			self.fn = self.write
		self.sn_conn = self.sn.activated.connect(self.fn)

	def shutdown(self):
		self.sn_conn = self.fn = self.watcher = None
		del self.sn

	def read(self, sock):
		w = self.watcher
		def _read():
			why = None
			try:
				why = w.doRead()
			except:
				log.err()
				why = exc_info()[1]
			if why:
				self.reactor._disconnectSelectable(w, why, True)
		log.callWithLogger(w, _read)
		self.reactor.simulate()

	def write(self, sock):
		w = self.watcher
		def _write():
			why = None
			try:
				why = w.doWrite()
			except:
				log.err()
				why = exc_info()[1]
			if why:
				self.reactor._disconnectSelectable(w, why, False)
		log.callWithLogger(w, _write)
		self.reactor.simulate()

@implementer(IReactorFDSet)
class e2reactor(PosixReactorBase):
	"""
	e2 reactor.
	"""

	# Reference to a DelayedCall for self.crash() when the reactor is
	# entered through .iterate()
	_crashCall = None

	_timer = None

	_now = None

	def __init__(self):
		self._reads = {}
		self._writes = {}
		self.savedTimeout = None
		self._shutdownRunning = 0
		self._timer = eTimer()
		self._timer_conn = self._timer.timeout.connect(self.simulate)
		self._insimulate = False
		self._wakeupPending = False
		# to limit the systemcalls per loop
		# twistes gets a cached monotonic time for internal timers
		# only updated once per loop (monotonic_time call in def simulate)
		PosixReactorBase.seconds = self.now
		PosixReactorBase.__init__(self)
		self.addSystemEventTrigger('after', 'shutdown', self.cleanup)

	def doShutdown(self):
		while self._timer: # iterate until cleanup is called...
			self.runUntilCurrent()
			self._insertNewDelayedCalls()
			self._shutdownRunning += 1 # without this hack the shutdown takes thirty seconds.. i dont know why

	def now(self):
		return self._insimulate and self._now or monotonic_time()+self._shutdownRunning

	def callLater(self, _seconds, _f, *args, **kw):
		ret = PosixReactorBase.callLater(self, _seconds, _f, *args, **kw)
		if not self._wakeupPending:
			self.wakeUp()
			self._wakeupPending = True
		return ret

	def addReader(self, reader):
		if not reader in self._reads:
			self._reads[reader] = TwistedSocketNotifier(self, reader, POLLIN)

	def addWriter(self, writer):
		if not writer in self._writes:
			self._writes[writer] = TwistedSocketNotifier(self, writer, POLLOUT)

	def removeReader(self, reader):
		if reader in self._reads:
			self._reads.pop(reader).shutdown()

	def removeWriter(self, writer):
		if writer in self._writes:
			self._writes.pop(writer).shutdown()

	def removeAll(self):
		return self._removeAll(self._reads, self._writes)

	def getReaders(self):
		return list(self._reads.keys())

	def getWriters(self):
		return list(self._writes.keys())

	def simulate(self):
		if not self.running:
			quitMainloop(6)
			return

		#update time returned by self.seconds
		e2reactor._now = monotonic_time()

		self._wakeupPending = False
		self._insimulate = True

		self.runUntilCurrent()

		if self._crashCall is not None:
			self._crashCall.reset(0)

		self._insertNewDelayedCalls()

		pendingTimedCalls = self._pendingTimedCalls
		if pendingTimedCalls:
			nextTimeout = pendingTimedCalls[0].time
			if nextTimeout != self.savedTimeout:
				self.savedTimeout = nextTimeout
				timeout = max(0, nextTimeout - self.seconds())
				self._timer.start(int(timeout * 1010), True)
		else:
			self._timer.stop()

		self._insimulate = False

	def cleanup(self):
		if self._timer is not None:
			self._timer_conn = None
			self._timer.stop()
			self._timer = None

	def iterate(self, delay=0.0):
		self._crashCall = self.callLater(delay, self._crash)
		self.run()

	def mainLoop(self):
		self.simulate()
		runMainloop()

	def _crash(self):
		if self._crashCall is not None:
			if self._crashCall.active():
				self._crashCall.cancel()
			self._crashCall = None
		self.running = False

def install(app=None):
	"""
	Configure the twisted mainloop to be run inside the e2 mainloop.
	"""
	from twisted.internet import main
	reactor = e2reactor()
	main.installReactor(reactor)
