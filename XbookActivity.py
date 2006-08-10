import os

import gtk
import evince

from sugar.activity.Activity import Activity

class XbookActivity(Activity):
	def __init__(self):
		Activity.__init__(self)

		evince.job_queue_init()

		scrolled = gtk.ScrolledWindow()
		self.add(scrolled)
		scrolled.show()

		test_file = 'file://' + os.path.expanduser('~/test.pdf')

		view = evince.View()
		document = evince.factory_get_document(test_file)
		document.load(test_file)
		view.set_document(document)

		scrolled.add(view)
		view.show()
