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
        self._evince_view = evince.View()
                
        vbox = hippo.CanvasBox()
        self.set_root(vbox)

        self._toolbar = XbookToolbar(self._evince_view)
        vbox.append(self._toolbar)

        canvas_widget = hippo.CanvasWidget()
        vbox.append(canvas_widget, hippo.PACK_EXPAND)        
        
        scrolled = gtk.ScrolledWindow()
        scrolled.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled.props.shadow_type = gtk.SHADOW_NONE

        canvas_widget.props.widget = scrolled
        scrolled.show()

        scrolled.add(self._evince_view)
        self._evince_view.show()

        document = evince.factory_get_document('file:///home/tomeu/Desktop/olpc/docs/OLS/jones-reprint.pdf')
        self._evince_view.set_document(document)
        self._toolbar.set_document(document)

    def execute(self, command, args):
        if(command == 'open_document'):
            document = evince.factory_get_document('file://' + args[0])
            self._evince_view.set_document(document)
            self._toolbar.set_document(document)
            
            return True
        else:
            return False
