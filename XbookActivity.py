import logging
from gettext import gettext as _
import gtk
import evince
from sugar.activity.Activity import Activity

from toolbar import Toolbar

class XbookActivity(Activity):
	def __init__(self):
		Activity.__init__(self)

		logging.debug('Starting xbook...')
		self.set_title(_('Read Activity'))
		
		evince.job_queue_init()
		self._evince_view = evince.View()
				
		vbox = gtk.VBox(False, 0)
		self.add(vbox)
		vbox.show()

		self._toolbar = Toolbar(self._evince_view)
		vbox.pack_start(self._toolbar, False)
		self._toolbar.show()
		
		scrolled = gtk.ScrolledWindow()
		vbox.pack_start(scrolled, True, True)
		scrolled.show()

		scrolled.add(self._evince_view)
		self._evince_view.show()

	def execute(self, command, args):
		if(command == 'open_document'):
			document = evince.factory_get_document('file://' + args[0])
			self._evince_view.set_document(document)
			
			# FIXME: Hack for rendering in a fast way by having an integer scale factor.
			self._evince_view.set_sizing_mode(2)
			self._evince_view.set_zoom(2.0, False)

			self._toolbar.set_document(document)
                        return True

                else :
                	return False
