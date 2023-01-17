from __future__ import absolute_import
from Components.HTMLComponent import HTMLComponent
from Components.GUIComponent import GUIComponent
from Components.VariableText import VariableText

from enigma import eButton

class Button(VariableText, HTMLComponent, GUIComponent):
	def __init__(self, text="", onClick = [ ]):
		GUIComponent.__init__(self)
		VariableText.__init__(self)
		self.setText(text)
		self.onClick = onClick
	
	def push(self):
		for x in self.onClick:
			x()
		return 0
	
	def disable(self):
		pass
	
	def enable(self):
		pass

# html:
	def produceHTML(self):
		return "<input type=\"submit\" text=\"" + self.getText() + "\">\n"

	GUI_WIDGET = eButton

	def postWidgetCreate(self, instance):
		instance.setText(self.text)
		instance.setDefaultAnimationEnabled(True)
		self.selected_conn = instance.selected.connect(self.push)

	def preWidgetRemove(self, instance):
		self.selected_conn = None
