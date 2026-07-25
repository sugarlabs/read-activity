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

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Graphene

from sugar4.graphics.icon import Icon
from sugar4.graphics.xocolor import XoColor
from sugar4.util import timestamp_to_elapsed_string
from sugar4.graphics import style
from sugar4 import profile

from readdialog import BookmarkAddDialog, BookmarkEditDialog

from gettext import gettext as _


_logger = logging.getLogger('read-activity')


class BookmarkView(Gtk.Box):

    __gsignals__ = {
        'bookmark-changed': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE,
                             ([])),
    }

    def __init__(self):
        super().__init__()
        self._box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._box.set_valign(Gtk.Align.START)
        self._box.set_margin_top(style.GRID_CELL_SIZE / 2)
        self.append(self._box)
        self._box.set_visible(True)
        self._bookmarks = []
        self._bookmark_icon = None
        self._bookmark_manager = None
        self._is_showing_local_bookmark = False

        click_controller = Gtk.GestureClick()
        click_controller.connect('pressed', self.__click_pressed_cb)
        self.add_controller(click_controller)

    def do_snapshot(self, snapshot):
        width = self.get_width()
        height = self.get_height()
        bounds = Graphene.Rect().init(0, 0, width, height)
        ctx = snapshot.append_cairo(bounds)
        width = style.GRID_CELL_SIZE
        height = style.GRID_CELL_SIZE * (len(self._bookmarks) + 1)

        ctx.rectangle(0, 0, width, height)
        ctx.set_source_rgba(*self._fill_color.get_rgba())
        ctx.paint()

        ctx.new_path()
        ctx.move_to(0, 0)
        ctx.line_to(width, 0)
        ctx.line_to(width, height)
        ctx.line_to(width / 2, height - width / 2)
        ctx.line_to(0, height)
        ctx.close_path()
        ctx.set_source_rgba(*self._stroke_color.get_rgba())
        ctx.fill()

    def _add_bookmark_icon(self, bookmark):
        self._xo_color = XoColor(str(bookmark.color))
        self._fill_color = style.Color(self._xo_color.get_fill_color())
        self._stroke_color = style.Color(self._xo_color.get_stroke_color())
        self._bookmark_icon = Icon(icon_name='emblem-favorite',
                                   xo_color=self._xo_color,
                                   pixel_size=style.STANDARD_ICON_SIZE)
        self._bookmark_icon.set_valign(Gtk.Align.START)

        self._bookmark_icon.props.has_tooltip = True
        self.__box_query_tooltip_cb_id = self._bookmark_icon.connect(
            'query_tooltip', self.__bookmark_query_tooltip_cb)

        self._box.append(self._bookmark_icon)

        if bookmark.is_local():
            self._is_showing_local_bookmark = True

    def __bookmark_query_tooltip_cb(self, widget, x, y, keyboard_mode, tip):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        for bookmark in self._bookmarks:

            tooltip_header = bookmark.get_note_title()
            tooltip_body = bookmark.get_note_body()
            time = timestamp_to_elapsed_string(bookmark.timestamp)
            # TRANS: This goes like Bookmark added by User 5 days ago
            # TRANS: (the elapsed string gets translated automatically)
            tooltip_footer = (
                _('Bookmark added by %(user)s %(time)s')
                % {'user': bookmark.nick,
                   'time': time})

            a = Gtk.Label(label='<big>%s</big>' % tooltip_header)
            a.set_use_markup(True)
            a.set_width_chars(40)
            a.set_wrap(True)
            vbox.append(a)

            a = Gtk.Label(label='%s' % tooltip_body)
            a.set_use_markup(True)
            a.set_xalign(0.0)
            a.set_yalign(0.0)
            a.set_margin_start(2)
            a.set_margin_end(2)
            a.set_margin_top(6)
            a.set_margin_bottom(6)
            a.set_width_chars(40)
            a.set_wrap(True)
            a.set_justify(Gtk.Justification.FILL)
            vbox.append(a)

            a = Gtk.Label(label='<small><i>%s</i></small>' % tooltip_footer)
            a.set_use_markup(True)
            a.set_width_chars(40)
            a.set_wrap(True)
            vbox.append(a)

        tip.set_custom(vbox)
        return True

    def __click_pressed_cb(self, gesture, n_press, x, y):
        # TODO: show the first bookmark
        self._dialog = BookmarkEditDialog(
            self.get_root(),
            _("Add notes for bookmark: "),
            self._bookmarks, self._page, self)
        self._dialog.present()
        return True

    def _clear_bookmarks(self):
        child = self._box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self._box.remove(child)
            child = next_child
            self._bookmark_icon = None
            self._is_showing_local_bookmark = False

    def set_bookmarkmanager(self, bookmark_manager):
        self._bookmark_manager = bookmark_manager

    def get_bookmarkmanager(self):
        return (self._bookmark_manager)

    def update_for_page(self, page):
        self._page = page
        self._clear_bookmarks()
        if self._bookmark_manager is None:
            return

        self._bookmarks = self._bookmark_manager.get_bookmarks_for_page(page)

        if self._bookmarks:
            self.set_visible(True)
        else:
            self.set_visible(False)

        for bookmark in self._bookmarks:
            self._add_bookmark_icon(bookmark)

        self.set_size_request(
            style.GRID_CELL_SIZE,
            style.GRID_CELL_SIZE * (len(self._bookmarks) + 1))

        self.notify_bookmark_change()

    def notify_bookmark_change(self):
        self.queue_draw()
        self.emit('bookmark-changed')

    def add_bookmark(self, page):
        bookmark_title = (_("%s's bookmark") % profile.get_nick_name())
        bookmark_content = (_("Bookmark for page %d") % (int(page) + 1))
        self._dialog = BookmarkAddDialog(
            parent_window=self.get_root(),
            dialog_title=_("Add notes for bookmark: "),
            bookmark_title=bookmark_title,
            bookmark_content=bookmark_content, page=page,
            sidebarinstance=self)
        self._dialog.present()

    def _real_add_bookmark(self, page, content):
        self._bookmark_manager.add_bookmark(page, str(content))
        self.update_for_page(page)

    def del_bookmark(self, page):
        self._bookmark_manager.del_bookmark(page)
        self.update_for_page(page)

    def is_showing_local_bookmark(self):
        return self._is_showing_local_bookmark
