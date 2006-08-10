 

import gtk
import evince

from sugar.activity.Activity import Activity

class XbookActivity(Activity):
	def __init__(self):
		Activity.__init__(self)

		evince.job_queue_init()

		window = gtk.Window()
		window.set_default_size(640, 480)

		scrolled = gtk.ScrolledWindow()
		window.add(scrolled)
		scrolled.show()

		test_file = 'file:///home/manu/Desktop/OLPC.pdf'

		view = evince.View()
		document = evince.factory_get_document(test_file)
		document.load(test_file)
		view.set_document(document)

		scrolled.add(view)
		view.show()

