import logging
from gettext import gettext as _

import gtk
import evince
import hippo
from sugar.activity import activity

from xbooktoolbar import XbookToolbar

class XbookActivity(activity.Activity):
    def __init__(self, handle):
        activity.Activity.__init__(self, handle)

        logging.debug('Starting xbook...')
        self.set_title(_('Read Activity'))
        
        evince.job_queue_init()
        self._view = evince.View()
                
        vbox = hippo.CanvasBox()
        self.set_root(vbox)

        toolbar = XbookToolbar(self._view)
        toolbar.connect('open-document', self._open_document_cb)
        vbox.append(toolbar)

        canvas_widget = hippo.CanvasWidget()
        vbox.append(canvas_widget, hippo.PACK_EXPAND)        
        
        scrolled = gtk.ScrolledWindow()
        scrolled.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled.props.shadow_type = gtk.SHADOW_NONE

        canvas_widget.props.widget = scrolled
        scrolled.show()

        scrolled.add(self._view)
        self._view.show()

        if handle.uri:
            self._load_document(handle.uri)

    def _load_document(self, filename):
        document = evince.factory_get_document('file://' + filename)
        self._view.set_document(document)
        toolbar.set_document(document)

    def _open_document_cb(self, widget, fname):
        self._load_document(fname)
