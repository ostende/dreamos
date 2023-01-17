# -*- coding: UTF-8 -*-
from __future__ import absolute_import
from Components.config import config
from Plugins.SystemPlugins.UPnP.UPnPMediaRenderer import restartMediaRenderer
from Plugins.Plugin import PluginDescriptor
from Plugins.SystemPlugins.UPnP.UPnPConfig import getUUID

from .PlayerImpl import PlayerImpl

def start(reason, session=None, **kwargs):
	if session and reason == 0 and config.plugins.mediarenderer.enabled.value:
		restartMediaRenderer(
				session,
				PlayerImpl(session),
				config.plugins.mediarenderer.name.value,
				getUUID(config.plugins.mediarenderer.uuid),
				manufacturer='dreambox',
				manufacturer_url='http://www.dreambox.de',
				model_description='Dreambox MediaRenderer',
				model_name=config.plugins.mediarenderer.name.value,
				model_number=config.plugins.mediarenderer.name.value,
				model_url='http://www.dreambox.de'
			)

def Plugins(**kwargs):
	return [ PluginDescriptor(where=[PluginDescriptor.WHERE_UPNP, PluginDescriptor.WHERE_UPNP], fnc=start) ]
