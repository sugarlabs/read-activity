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

from sugar4.graphics.toolbutton import ToolButton
from sugar4.graphics.toggletoolbutton import ToggleToolButton
from sugar4.graphics import iconentry
from sugar4.activity.widgets import EditToolbar as BaseEditToolbar


class EditToolbar(BaseEditToolbar):

    __gtype_name__ = 'EditToolbar'

    def __init__(self):
        super().__init__()
        self.add_css_class("toolbar")

        self._view = None

        search_item = Gtk.Box()

        self._search_entry = iconentry.IconEntry()
        self._search_entry.set_icon_from_name(iconentry.ICON_ENTRY_PRIMARY,
                                              'entry-search')
        self._search_entry.add_clear_button()
        self._search_entry.connect('activate', self._search_entry_activate_cb)
        self._search_entry.connect('changed', self._search_entry_changed_cb)
        self._search_entry_changed = True

        from readactivity import get_screen_width
        width = int(get_screen_width() / 3)
        self._search_entry.set_size_request(width, -1)

        search_item.append(self._search_entry)
        self._search_entry.set_visible(True)

        self.append(search_item)
        search_item.set_visible(True)

        self._nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self._nav_box.add_css_class('linked')

        self._prev = ToolButton('go-previous-paired')
        self._prev.set_tooltip(_('Previous'))
        self._prev.props.sensitive = False
        self._prev.connect('clicked', self._find_prev_cb)
        self._nav_box.append(self._prev)
        self._prev.set_visible(True)

        self._next = ToolButton('go-next-paired')
        self._next.set_tooltip(_('Next'))
        self._next.props.sensitive = False
        self._next.connect('clicked', self._find_next_cb)
        self._nav_box.append(self._next)
        self._next.set_visible(True)

        self.append(self._nav_box)
        self._nav_box.set_visible(True)

        separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        separator.set_visible(True)
        self.append(separator)

        self.highlight = ToggleToolButton('format-text-underline')
        self.highlight.set_tooltip(_('Highlight'))
        self.highlight.props.sensitive = False
        self.append(self.highlight)

    def set_view(self, view):
        self._view = view
        if hasattr(self._view, 'find_set_highlight_search'):
            self._view.find_set_highlight_search(True)

    def _clear_find_job(self):
        if self._view and hasattr(self._view, 'clear_search'):
            self._view.clear_search()

    def _search_find_first(self):
        self._clear_find_job()
        text = self._search_entry.props.text
        if text != "" and hasattr(self._view, 'start_search'):
            self._view.start_search(text, self._find_updated_cb)
        else:
            # FIXME: highlight nothing
            pass

        self._search_entry_changed = False
        self._update_find_buttons()

    def _search_find_next(self):
        if hasattr(self._view, 'find_next'):
            self._view.find_next()
        self._update_find_buttons()

    def _search_find_last(self):
        # FIXME: does Papers support find last?
        return

    def _search_find_prev(self):
        if hasattr(self._view, 'find_previous'):
            self._view.find_previous()
        self._update_find_buttons()

    def _search_entry_activate_cb(self, entry):
        if self._search_entry_changed:
            self._search_find_first()
        else:
            self._search_find_next()

    def _search_entry_changed_cb(self, entry):
        logging.debug('Search entry: %s' % (entry.props.text))
        self._search_entry_changed = True
        if entry.props.text == "":
            self._clear_find_job()
        self._update_find_buttons()

    #    GLib.timeout_add(500, self._search_entry_timeout_cb)
    #
    # def _search_entry_timeout_cb(self):
    #    self._clear_find_job()
    #    self._search_find_first()
    #    return False

    def _find_changed_cb(self, page, spec):
        self._update_find_buttons()

    def _find_updated_cb(self, job=None, page=None):
        self._update_find_buttons()

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
        has_results = False
        if self._view and hasattr(self._view, 'has_search_results'):
            has_results = self._view.has_search_results()

        if self._search_entry_changed:
            if self._search_entry.props.text != "":
                self._prev.props.sensitive = False
                self._next.props.sensitive = True
                self._next.set_tooltip(_('Find first'))
            else:
                self._prev.props.sensitive = False
                self._next.props.sensitive = False
        else:
            # Enable previous/next if we actually found results
            self._prev.props.sensitive = has_results
            self._prev.set_tooltip(_('Find previous'))
            self._next.props.sensitive = has_results
            self._next.set_tooltip(_('Find next'))


class ViewToolbar(Gtk.Box):
    __gtype_name__ = 'ViewToolbar'

    __gsignals__ = {
        'go-fullscreen': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE,
                          ([])),
        'toggle-index-show': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE,
                              ([bool])),
        'toggle-tray-show': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE,
                             ([bool])),
        'toggle-inverted-colors': (GObject.SignalFlags.RUN_FIRST,
                                   GObject.TYPE_NONE, ([bool])), }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.add_css_class("toolbar")

        self._view = None

        self._navigator_button = ToggleToolButton('view-list')
        self._navigator_button.set_tooltip(_('Table of contents'))
        self._navigator_button.connect('toggled', self.__navigator_toggled_cb)
        self.append(self._navigator_button)

        self._spacer_navigator = Gtk.Separator(
            orientation=Gtk.Orientation.VERTICAL)
        self._spacer_navigator.set_opacity(0)
        self.append(self._spacer_navigator)

        self._zoom_out = ToolButton('zoom-out')
        self._zoom_out.set_tooltip(_('Zoom out'))
        self._zoom_out.connect('clicked', self._zoom_out_cb)
        self.append(self._zoom_out)
        self._zoom_out.set_visible(True)

        self._zoom_in = ToolButton('zoom-in')
        self._zoom_in.set_tooltip(_('Zoom in'))
        self._zoom_in.connect('clicked', self._zoom_in_cb)
        self.append(self._zoom_in)
        self._zoom_in.set_visible(True)

        self._zoom_to_width = ToolButton('zoom-to-width')
        self._zoom_to_width.set_tooltip(_('Zoom to width'))
        self._zoom_to_width.connect('clicked', self._zoom_to_width_cb)
        self.append(self._zoom_to_width)
        self._zoom_to_width.set_visible(True)

        self._zoom_to_fit = ToolButton('zoom-best-fit')
        self._zoom_to_fit.set_tooltip(_('Zoom to fit'))
        self._zoom_to_fit.connect('clicked', self._zoom_to_fit_cb)
        self.append(self._zoom_to_fit)
        self._zoom_to_fit.set_visible(True)

        self._zoom_to_original = ToolButton('zoom-original')
        self._zoom_to_original.set_tooltip(_('Actual size'))
        self._zoom_to_original.connect('clicked', self._actual_size_cb)
        self.append(self._zoom_to_original)
        self._zoom_to_original.set_visible(True)

        spacer = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self.append(spacer)
        spacer.set_visible(True)

        self._fullscreen = ToolButton('view-fullscreen')
        self._fullscreen.set_tooltip(_('Fullscreen'))
        self._fullscreen.connect('clicked', self._fullscreen_cb)
        self.append(self._fullscreen)
        self._fullscreen.set_visible(True)

        self.traybutton = ToggleToolButton('tray-show')
        self.traybutton.set_icon_name('tray-favourite')
        self.traybutton.connect('toggled', self.__tray_toggled_cb)
        self.traybutton.props.active = False
        self.append(self.traybutton)
        self.traybutton.set_visible(True)

        self._view_notify_zoom_handler = None

        spacer = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self.append(spacer)
        spacer.set_visible(True)

        self._rotate_left = ToolButton('rotate_anticlockwise')
        self._rotate_left.set_tooltip(_('Rotate left'))
        self._rotate_left.connect('clicked', self._rotate_left_cb)
        self.append(self._rotate_left)
        self._rotate_left.set_visible(True)

        self._rotate_right = ToolButton('rotate_clockwise')
        self._rotate_right.set_tooltip(_('Rotate right'))
        self._rotate_right.connect('clicked', self._rotate_right_cb)
        self.append(self._rotate_right)
        self._rotate_right.set_visible(True)

        spacer = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self.append(spacer)
        spacer.set_visible(True)

        self._inverted_colors = ToggleToolButton(icon_name='dark-theme')
        self._inverted_colors.set_tooltip(_('Inverted Colors'))
        self._inverted_colors.set_accelerator('<Ctrl>i')
        self._inverted_colors.connect(
            'toggled', self.__inverted_colors_toggled_cb)
        self.append(self._inverted_colors)

    def set_view(self, view):
        self._view = view
        self._update_zoom_buttons()

    def show_nav_button(self):
        self._navigator_button.set_visible(True)
        self._spacer_navigator.set_visible(True)

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

    def __inverted_colors_toggled_cb(self, button):
        self.emit('toggle-inverted-colors', button.props.active)
        if button.props.active:
            button.set_icon_name('light-theme')
            button.set_tooltip(_('Normal Colors'))
        else:
            button.set_icon_name('dark-theme')
            button.set_tooltip(_('Inverted Colors'))

    def show_inverted_colors_button(self):
        self._inverted_colors.set_visible(True)

    def toggle_inverted_colors(self):
        self._inverted_colors.set_active(
            not self._inverted_colors.get_active())
