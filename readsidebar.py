import logging
import time

import gtk

from sugar.graphics.icon import Icon
from sugar.graphics.xocolor import XoColor

from readbookmark import Bookmark
from readdb import BookmarkManager

from gettext import gettext as _

_logger = logging.getLogger('read-activity')

class Sidebar(gtk.EventBox):
    def __init__(self):
        gtk.EventBox.__init__(self)
        self.set_size_request(20, -1)
        # Take care of the background first
        white = gtk.gdk.color_parse("white")
        self.modify_bg(gtk.STATE_NORMAL, white)

        self._box = gtk.VButtonBox()
        self._box.set_layout(gtk.BUTTONBOX_CENTER)
        self.add(self._box)

        self._box.show()
        self.show()
        
        self._bookmarks = []
        self._bookmark_manager = None
        self._is_showing_local_bookmark = False

    def _add_bookmark_icon(self, bookmark):
        xocolor = XoColor(bookmark.color)
        bookmark_icon = Icon(icon_name = 'emblem-favorite', \
            pixel_size = 18, xo_color = xocolor)

        tooltip_text = (_('Bookmark added by %(user)s on %(time)s') \
            % {'user': bookmark.nick, 'time': time.ctime(bookmark.timestamp)})
        bookmark_icon.set_tooltip_text(tooltip_text)

        self._box.pack_start(bookmark_icon ,expand=False,fill=False)
        bookmark_icon.show_all()
        
        self._bookmarks.append(bookmark_icon)

        if bookmark.is_local():
            self._is_showing_local_bookmark = True
        
    def _clear_bookmarks(self):
        for bookmark_icon in self._bookmarks:
            bookmark_icon.hide() #XXX: Is this needed??
            bookmark_icon.destroy()
        
        self._bookmarks = []
        
        self._is_showing_local_bookmark = False
    
    def set_bookmarkmanager(self, filehash):
        self._bookmark_manager = BookmarkManager(filehash)
        
    def get_bookmarkmanager(self):
        return (self._bookmark_manager)
    
    def update_for_page(self, page):
        self._clear_bookmarks()
        if self._bookmark_manager is None:
            return
        
        bookmarks = self._bookmark_manager.get_bookmarks_for_page(page)
        
        for bookmark in bookmarks:
            self._add_bookmark_icon(bookmark)
    
    def add_bookmark(self, page):
        self._bookmark_manager.add_bookmark(page, '') #TODO: Implement title support
        self.update_for_page(page)
        
    def del_bookmark(self, page):
        self._bookmark_manager.del_bookmark(page)
        self.update_for_page(page)
        
    def is_showing_local_bookmark(self):
        return self._is_showing_local_bookmark

