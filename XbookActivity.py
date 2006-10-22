import os
from gettext import gettext as _
import gtk
import evince
from sugar.activity.Activity import Activity

from toolbar import Toolbar

class XbookActivity(Activity):
    def __init__(self):
        Activity.__init__(self)

        self.set_title(_('Read Activity'))
        
        evince.job_queue_init()
        evince_view = evince.View()
                
        vbox = gtk.VBox(False, 0)
        self.add(vbox)
        vbox.show()

        toolbar = Toolbar(evince_view)
        vbox.pack_start(toolbar, False)
        toolbar.show()
        
        scrolled = gtk.ScrolledWindow()
        vbox.pack_start(scrolled, True, True)
        scrolled.show()

        scrolled.add(evince_view)
        evince_view.show()

        test_file = 'file://' + os.path.expanduser('~/test.pdf')
        document = evince.factory_get_document(test_file)
        evince_view.set_document(document)
        toolbar.set_document(document)
