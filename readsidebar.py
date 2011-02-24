# Copyright 2009 One Laptop Per Child
# Author: Sayamindu Dasgupta <sayamindu@laptop.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import logging
import time

import gtk

from sugar.graphics.icon import Icon
from sugar.graphics.xocolor import XoColor
from sugar import profile
from sugar.util import timestamp_to_elapsed_string

from readbookmark import Bookmark
from readdb import BookmarkManager
from readdialog import BookmarkAddDialog, BookmarkEditDialog

from gettext import gettext as _


_logger = logging.getLogger('read-activity')

# TODO: Add support for multiple bookmarks in a single page
# (required when sharing)


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

        self._bookmark_icon = None
        self._bookmark_manager = None
        self._is_showing_local_bookmark = False

        self.add_events(gtk.gdk.BUTTON_PRESS_MASK)

    def _add_bookmark_icon(self, bookmark):
        xocolor = XoColor(bookmark.color)
        self._bookmark_icon = Icon(icon_name='emblem-favorite', pixel_size=18,
                                   xo_color=xocolor)

        self._bookmark_icon.props.has_tooltip = True
        self.__bookmark_icon_query_tooltip_cb_id = \
            self._bookmark_icon.connect('query_tooltip',
            self.__bookmark_icon_query_tooltip_cb, bookmark)

        self.__event_cb_id = \
            self.connect('event', self.__event_cb, bookmark)

        self._box.pack_start(self._bookmark_icon, expand=False, fill=False)
        self._bookmark_icon.show_all()

        if bookmark.is_local():
            self._is_showing_local_bookmark = True

    def __bookmark_icon_query_tooltip_cb(self, widget, x, y, keyboard_mode,
            tip, bookmark):
        tooltip_header = bookmark.get_note_title()
        tooltip_body = bookmark.get_note_body()
        #TRANS: This goes like Bookmark added by User 5 days ago
        #TRANS: (the elapsed string gets translated automatically)
        tooltip_footer = (_('Bookmark added by %(user)s %(time)s') \
                % {'user': bookmark.nick,
                'time': timestamp_to_elapsed_string(bookmark.timestamp)})

        vbox = gtk.VBox()

        l = gtk.Label('<big>%s</big>' % tooltip_header)
        l.set_use_markup(True)
        l.set_width_chars(40)
        l.set_line_wrap(True)
        vbox.pack_start(l, expand=False, fill=False)
        l.show()

        l = gtk.Label('%s' % tooltip_body)
        l.set_use_markup(True)
        l.set_alignment(0, 0)
        l.set_padding(2, 6)
        l.set_width_chars(40)
        l.set_line_wrap(True)
        l.set_justify(gtk.JUSTIFY_FILL)
        vbox.pack_start(l, expand=True, fill=True)
        l.show()

        l = gtk.Label('<small><i>%s</i></small>' % tooltip_footer)
        l.set_use_markup(True)
        l.set_width_chars(40)
        l.set_line_wrap(True)
        vbox.pack_start(l, expand=False, fill=False)
        l.show()

        tip.set_custom(vbox)

        return True

    def __event_cb(self, widget, event, bookmark):
        if event.type == gtk.gdk.BUTTON_PRESS and \
                    self._bookmark_icon is not None:

            bookmark_title = bookmark.get_note_title()
            bookmark_content = bookmark.get_note_body()

            dialog = BookmarkEditDialog(
                parent_xid=self.get_toplevel().window.xid,
                dialog_title=_("Add notes for bookmark: "),
                bookmark_title=bookmark_title,
                bookmark_content=bookmark_content, page=bookmark.page_no,
                sidebarinstance=self)
            dialog.show_all()

        return False

    def _clear_bookmarks(self):
        if self._bookmark_icon is not None:
            self._bookmark_icon.disconnect(
                    self.__bookmark_icon_query_tooltip_cb_id)
            self.disconnect(self.__event_cb_id)

            self._bookmark_icon.hide()  # XXX: Is this needed??
            self._bookmark_icon.destroy()

            self._bookmark_icon = None

            self._is_showing_local_bookmark = False

    def set_bookmarkmanager(self, bookmark_manager):
        self._bookmark_manager = bookmark_manager

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
        bookmark_title = (_("%s's bookmark") % profile.get_nick_name())
        bookmark_content = (_("Bookmark for page %d") % page)
        dialog = BookmarkAddDialog(
            parent_xid=self.get_toplevel().window.xid,
            dialog_title=_("Add notes for bookmark: "),
            bookmark_title=bookmark_title,
            bookmark_content=bookmark_content, page=page,
            sidebarinstance=self)
        dialog.show_all()

    def _real_add_bookmark(self, page, content):
        self._bookmark_manager.add_bookmark(page, unicode(content))
        self.update_for_page(page)

    def del_bookmark(self, page):
        self._bookmark_manager.del_bookmark(page)
        self.update_for_page(page)

    def is_showing_local_bookmark(self):
        return self._is_showing_local_bookmark
