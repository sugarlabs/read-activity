import os
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

		toolbar = Toolbar(self._evince_view)
		vbox.pack_start(toolbar, False)
		toolbar.show()
		
		scrolled = gtk.ScrolledWindow()
		vbox.pack_start(scrolled, True, True)
		scrolled.show()

		scrolled.add(self._evince_view)
		self._evince_view.show()

	def execute(self, command, args):
		if(command == 'open_document'):
			#FIXME: Get the entire path from GSugarDownload
			file_name = '/tmp/' + args[0]
			
			document = evince.factory_get_document('file://' + file_name)
			self._evince_view.set_document(document)
			toolbar.set_document(document)
