from __future__ import absolute_import
from Plugins.Plugin import PluginDescriptor

def videoFinetuneMain(session, **kwargs):
	from .VideoFinetune import VideoFinetune
	session.open(VideoFinetune)

def startSetup(menuid):
	if menuid != "osd_video_audio":
		return [ ]

	return [(_("Video Fine-Tuning"), videoFinetuneMain, "video_finetune", 21)]

def Plugins(**kwargs):
	return [
		PluginDescriptor(name=_("Video Fine-Tuning"), description=_("fine-tune your display"), where = PluginDescriptor.WHERE_MENU, needsRestart = False, fnc=startSetup),
	]
