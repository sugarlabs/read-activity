# Copyright (C) 2006, Red Hat, Inc.
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

from gettext import gettext as _
import logging

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Gdk

from sugar3.graphics.toolbutton import ToolButton
from sugar3.graphics.toggletoolbutton import ToggleToolButton
from sugar3.graphics import iconentry
from sugar3.activity.widgets import EditToolbar as BaseEditToolbar


class EditToolbar(BaseEditToolbar):

    __gtype_name__ = 'EditToolbar'

    def __init__(self):
        BaseEditToolbar.__init__(self)

        self._view = None

        self._find_job = None

        search_item = Gtk.ToolItem()

        self._search_entry = iconentry.IconEntry()
        self._search_entry.set_icon_from_name(iconentry.ICON_ENTRY_PRIMARY,
                                              'entry-search')
        self._search_entry.add_clear_button()
        self._search_entry.connect('activate', self._search_entry_activate_cb)
        self._search_entry.connect('changed', self._search_entry_changed_cb)
        self._search_entry_changed = True

        width = int(Gdk.Screen.width() / 3)
        self._search_entry.set_size_request(width, -1)

        search_item.add(self._search_entry)
        self._search_entry.show()

        self.insert(search_item, -1)
        search_item.show()

        self._prev = ToolButton('go-previous-paired')
        self._prev.set_tooltip(_('Previous'))
        self._prev.props.sensitive = False
        self._prev.connect('clicked', self._find_prev_cb)
        self.insert(self._prev, -1)
        self._prev.show()

        self._next = ToolButton('go-next-paired')
        self._next.set_tooltip(_('Next'))
        self._next.props.sensitive = False
        self._next.connect('clicked', self._find_next_cb)
        self.insert(self._next, -1)
        self._next.show()

        separator = Gtk.SeparatorToolItem()
        separator.show()
        self.insert(separator, -1)

        self.highlight = ToggleToolButton('format-text-underline')
        self.highlight.set_tooltip(_('Highlight'))
        self.highlight.props.sensitive = False
        self.insert(self.highlight, -1)

    def set_view(self, view):
        self._view = view
        self._view.find_set_highlight_search(True)

    def _clear_find_job(self):
        if self._find_job is None:
            return
        if not self._find_job.is_finished():
            self._find_job.cancel()
        self._find_job.disconnect(self._find_updated_handler)
        self._find_job = None

    def _search_find_first(self):
        self._clear_find_job()
        text = self._search_entry.props.text
        if text != "":
            self._find_job, self._find_updated_handler = \
                self._view.setup_find_job(text, self._find_updated_cb)
        else:
            # FIXME: highlight nothing
            pass

        self._search_entry_changed = False
        self._update_find_buttons()

    def _search_find_next(self):
        self._view.find_next()

    def _search_find_last(self):
        # FIXME: does Evince support find last?
        return

    def _search_find_prev(self):
        self._view.find_previous()

    def _search_entry_activate_cb(self, entry):
        if self._search_entry_changed:
            self._search_find_first()
        else:
            self._search_find_next()

    def _search_entry_changed_cb(self, entry):
        logging.debug('Search entry: %s' % (entry.props.text))
        self._search_entry_changed = True
        self._update_find_buttons()

    #    GObject.timeout_add(500, self._search_entry_timeout_cb)
    #
    # def _search_entry_timeout_cb(self):
    #    self._clear_find_job()
    #    self._search_find_first()
    #    return False

    def _find_changed_cb(self, page, spec):
        self._update_find_buttons()

    def _find_updated_cb(self, job, page=None):
        self._view.find_changed(job, page)

    def _find_prev_cb(self, button):
        if self._search_entry_changed:
            self._search_find_last()
        else:
            self._search_find_prev()

    def _find_next_cb(self, button):
        if self._search_entry_changed:
            self._search_find_first()
        else:
            self._search_find_next()

    def _update_find_buttons(self):
        if self._search_entry_changed:
            if self._search_entry.props.text != "":
                self._prev.props.sensitive = False
#                self._prev.set_tooltip(_('Find last'))
                self._next.props.sensitive = True
                self._next.set_tooltip(_('Find first'))
            else:
                self._prev.props.sensitive = False
                self._next.props.sensitive = False
        else:
            self._prev.props.sensitive = True
            self._prev.set_tooltip(_('Find previous'))
            self._next.props.sensitive = True
            self._next.set_tooltip(_('Find next'))


class ViewToolbar(Gtk.Toolbar):
    __gtype_name__ = 'ViewToolbar'

    __gsignals__ = {
        'go-fullscreen': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE,
                          ([])),
        'toggle-index-show': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE,
                              ([bool])),
        'toggle-tray-show': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE,
                             ([bool])), }

    def __init__(self):
        Gtk.Toolbar.__init__(self)

        self._view = None

        self._navigator_button = ToggleToolButton('view-list')
        self._navigator_button.set_tooltip(_('Table of contents'))
        self._navigator_button.connect('toggled', self.__navigator_toggled_cb)
        self.insert(self._navigator_button, -1)

        self._spacer_navigator = Gtk.SeparatorToolItem()
        self._spacer_navigator.props.draw = False
        self.insert(self._spacer_navigator, -1)

        self._zoom_out = ToolButton('zoom-out')
        self._zoom_out.set_tooltip(_('Zoom out'))
        self._zoom_out.connect('clicked', self._zoom_out_cb)
        self.insert(self._zoom_out, -1)
        self._zoom_out.show()

        self._zoom_in = ToolButton('zoom-in')
        self._zoom_in.set_tooltip(_('Zoom in'))
        self._zoom_in.connect('clicked', self._zoom_in_cb)
        self.insert(self._zoom_in, -1)
        self._zoom_in.show()

        self._zoom_to_width = ToolButton('zoom-to-width')
        self._zoom_to_width.set_tooltip(_('Zoom to width'))
        self._zoom_to_width.connect('clicked', self._zoom_to_width_cb)
        self.insert(self._zoom_to_width, -1)
        self._zoom_to_width.show()

        self._zoom_to_fit = ToolButton('zoom-best-fit')
        self._zoom_to_fit.set_tooltip(_('Zoom to fit'))
        self._zoom_to_fit.connect('clicked', self._zoom_to_fit_cb)
        self.insert(self._zoom_to_fit, -1)
        self._zoom_to_fit.show()

        self._zoom_to_original = ToolButton('zoom-original')
        self._zoom_to_original.set_tooltip(_('Actual size'))
        self._zoom_to_original.connect('clicked', self._actual_size_cb)
        self.insert(self._zoom_to_original, -1)
        self._zoom_to_original.show()

        spacer = Gtk.SeparatorToolItem()
        spacer.props.draw = True
        self.insert(spacer, -1)
        spacer.show()

        self._fullscreen = ToolButton('view-fullscreen')
        self._fullscreen.set_tooltip(_('Fullscreen'))
        self._fullscreen.connect('clicked', self._fullscreen_cb)
        self.insert(self._fullscreen, -1)
        self._fullscreen.show()

        self.traybutton = ToggleToolButton('tray-show')
        self.traybutton.set_icon_name('tray-favourite')
        self.traybutton.connect('toggled', self.__tray_toggled_cb)
        self.traybutton.props.active = False
        self.insert(self.traybutton, -1)
        self.traybutton.show()

        self._view_notify_zoom_handler = None

        spacer = Gtk.SeparatorToolItem()
        spacer.props.draw = True
        self.insert(spacer, -1)
        spacer.show()

        self._rotate_left = ToolButton('rotate_anticlockwise')
        self._rotate_left.set_tooltip(_('Rotate left'))
        self._rotate_left.connect('clicked', self._rotate_left_cb)
        self.insert(self._rotate_left, -1)
        self._rotate_left.show()

        self._rotate_right = ToolButton('rotate_clockwise')
        self._rotate_right.set_tooltip(_('Rotate right'))
        self._rotate_right.connect('clicked', self._rotate_right_cb)
        self.insert(self._rotate_right, -1)
        self._rotate_right.show()

    def set_view(self, view):
        self._view = view
        self._update_zoom_buttons()

    def show_nav_button(self):
        self._navigator_button.show()
        self._spacer_navigator.show()

    def zoom_in(self):
        self._view.zoom_in()
        self._update_zoom_buttons()

    def _zoom_in_cb(self, button):
        self.zoom_in()

    def _rotate_left_cb(self, button):
        self._view.rotate_left()

    def _rotate_right_cb(self, button):
        self._view.rotate_right()

    def zoom_out(self):
        self._view.zoom_out()
        self._update_zoom_buttons()

    def _zoom_out_cb(self, button):
        self.zoom_out()

    def zoom_to_width(self):
        self._view.zoom_to_width()
        self._update_zoom_buttons()

    def _zoom_to_width_cb(self, button):
        self.zoom_to_width()

    def __navigator_toggled_cb(self, button):
        self.emit('toggle-index-show', button.get_active())

    def _update_zoom_buttons(self):
        self._zoom_in.props.sensitive = self._view.can_zoom_in()
        self._zoom_out.props.sensitive = self._view.can_zoom_out()
        self._zoom_to_width.props.sensitive = self._view.can_zoom_to_width()
        self._zoom_to_fit.props.sensitive = self._view.can_zoom_to_width()
        self._zoom_to_original.props.sensitive = self._view.can_zoom_to_width()
        self._rotate_left.props.sensitive = self._view.can_rotate()
        self._rotate_right.props.sensitive = self._view.can_rotate()

    def _zoom_to_fit_cb(self, menu_item):
        self._view.zoom_to_best_fit()
        self._update_zoom_buttons()

    def _actual_size_cb(self, menu_item):
        self._view.zoom_to_actual_size()
        self._update_zoom_buttons()

    def _fullscreen_cb(self, button):
        self.emit('go-fullscreen')

    def __tray_toggled_cb(self, button):
        self.emit('toggle-tray-show', button.get_active())
        if button.props.active:
            self.traybutton.set_tooltip(_('Show Tray'))
        else:
            self.traybutton.set_tooltip(_('Hide Tray'))
