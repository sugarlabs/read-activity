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
        evince_view = evince.View()
                
        vbox = hippo.CanvasBox()
        self.set_root(vbox)

        toolbar = XbookToolbar(evince_view)
        vbox.append(toolbar)

        canvas_widget = hippo.CanvasWidget()
        vbox.append(canvas_widget, hippo.PACK_EXPAND)        
        
        scrolled = gtk.ScrolledWindow()
        scrolled.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled.props.shadow_type = gtk.SHADOW_NONE

        canvas_widget.props.widget = scrolled
        scrolled.show()

        scrolled.add(evince_view)
        evince_view.show()

        document = evince.factory_get_document('file://' + handle.uri)
        evince_view.set_document(document)
        toolbar.set_document(document)
