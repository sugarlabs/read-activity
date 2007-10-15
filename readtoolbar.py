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

import logging
from gettext import gettext as _
import re

import pango
import gobject
import gtk
import evince

from sugar.graphics.toolbutton import ToolButton
from sugar.graphics.menuitem import MenuItem
from sugar.activity import activity

class EditToolbar(activity.EditToolbar):
    __gtype_name__ = 'EditToolbar'

    def __init__(self, evince_view):
        activity.EditToolbar.__init__(self)

        self._evince_view = evince_view
        self._document = None

        separator = gtk.SeparatorToolItem()
        separator.set_draw(False)
        separator.set_expand(True)
        self.insert(separator, -1)
        separator.show()

        search_item = gtk.ToolItem()

        self._search_entry = gtk.Entry()
        self._search_entry.connect('activate', self._search_entry_activate_cb)

        width = int(gtk.gdk.screen_width() / 3)
        self._search_entry.set_size_request(width, -1)

        search_item.add(self._search_entry)
        self._search_entry.show()

        self.insert(search_item, -1)
        search_item.show()

        self._prev = ToolButton('go-previous')
        self._prev.set_tooltip(_('Previous'))
        self._prev.props.sensitive = False
        self._prev.connect('clicked', self._find_prev_cb)
        self.insert(self._prev, -1)
        self._prev.show()

        self._next = ToolButton('go-next')
        self._next.set_tooltip(_('Next'))
        self._next.props.sensitive = False
        self._next.connect('clicked', self._find_next_cb)
        self.insert(self._next, -1)
        self._next.show()

    def set_document(self, document):
        self._document = document
        self._document.connect('find_changed', self._find_changed_cb)  

    def _search_entry_activate_cb(self, entry):
        current_page = self._document.get_page_cache().get_current_page()
        self._document.find_begin(0, entry.props.text, False)
        self._update_find_buttons()

    def _find_changed_cb(self, page, spec):
        self._update_find_buttons()
        
    def _find_prev_cb(self, button):
        self._evince_view.find_previous()
    
    def _find_next_cb(self, button):
        self._evince_view.find_next()

    def _update_find_buttons(self):
        self._prev.props.sensitive = self._evince_view.can_find_previous()
        self._next.props.sensitive = self._evince_view.can_find_next()

class ReadToolbar(gtk.Toolbar):
    __gtype_name__ = 'ReadToolbar'

    def __init__(self, evince_view):
        gtk.Toolbar.__init__(self)

        self._evince_view = evince_view
        self._document = None
                
        self._back = ToolButton('go-previous')
        self._back.set_tooltip(_('Back'))
        self._back.props.sensitive = False
        self._back.connect('clicked', self._go_back_cb)
        self.insert(self._back, -1)
        self._back.show()

        self._forward = ToolButton('go-next')
        self._forward.set_tooltip(_('Forward'))
        self._forward.props.sensitive = False
        self._forward.connect('clicked', self._go_forward_cb)
        self.insert(self._forward, -1)
        self._forward.show()

        num_page_item = gtk.ToolItem()

        self._num_page_entry = gtk.Entry()
        self._num_page_entry.set_text('0')
        self._num_page_entry.set_alignment(1)
        self._num_page_entry.connect('insert-text',
                                     self._num_page_entry_insert_text_cb)
        self._num_page_entry.connect('activate',
                                     self._num_page_entry_activate_cb)

        self._num_page_entry.set_width_chars(4)

        num_page_item.add(self._num_page_entry)
        self._num_page_entry.show()

        self.insert(num_page_item, -1)
        num_page_item.show()

        total_page_item = gtk.ToolItem()

        self._total_page_label = gtk.Label()

        label_attributes = pango.AttrList()
        label_attributes.insert(pango.AttrSize(14000, 0, -1))
        label_attributes.insert(pango.AttrForeground(65535, 65535, 65535, 0, -1))
        self._total_page_label.set_attributes(label_attributes)

        self._total_page_label.set_text(' / 0')
        total_page_item.add(self._total_page_label)
        self._total_page_label.show()

        self.insert(total_page_item, -1)
        total_page_item.show()

    def set_document(self, document):
        self._document = document
        page_cache = self._document.get_page_cache()
        page_cache.connect('page-changed', self._page_changed_cb)    
        self._update_nav_buttons()

    def _num_page_entry_insert_text_cb(self, entry, text, length, position):
        if not re.match('[0-9]', text):
            entry.emit_stop_by_name('insert-text')
            return True
        return False

    def _num_page_entry_activate_cb(self, entry):
        if entry.props.text:
            page = int(entry.props.text) - 1
        else:
            page = 0

        if page >= self._document.get_n_pages():
            page = self._document.get_n_pages() - 1
        elif page < 0:
            page = 0

        self._document.get_page_cache().set_current_page(page)
        entry.props.text = str(page + 1)
        
    def _go_back_cb(self, button):
        self._evince_view.previous_page()
    
    def _go_forward_cb(self, button):
        self._evince_view.next_page()
    
    def _page_changed_cb(self, page, proxy):
        self._update_nav_buttons()

    def _update_nav_buttons(self):
        current_page = self._document.get_page_cache().get_current_page()
        self._back.props.sensitive = current_page > 0
        self._forward.props.sensitive = \
            current_page < self._document.get_n_pages() - 1
        
        self._num_page_entry.props.text = str(current_page + 1)
        self._total_page_label.props.label = \
            ' / ' + str(self._document.get_n_pages())

class ViewToolbar(gtk.Toolbar):
    __gtype_name__ = 'ViewToolbar'

    def __init__(self, evince_view):
        gtk.Toolbar.__init__(self)

        self._evince_view = evince_view
        self._document = None
            
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
            
        self._zoom_to_width = ToolButton('zoom-best-fit')
        self._zoom_to_width.set_tooltip(_('Zoom to width'))
        self._zoom_to_width.connect('clicked', self._zoom_to_width_cb)
        self.insert(self._zoom_to_width, -1)
        self._zoom_to_width.show()

        palette = self._zoom_to_width.get_palette()
        menu_item = MenuItem(_('Zoom to fit'))
        menu_item.connect('activate', self._zoom_to_fit_menu_item_activate_cb)
        palette.menu.append(menu_item)
        menu_item.show()

        menu_item = MenuItem(_('Actual size'))
        menu_item.connect('activate', self._actual_size_menu_item_activate_cb)
        palette.menu.append(menu_item)
        menu_item.show()

        tool_item = gtk.ToolItem()
        self.insert(tool_item, -1)
        tool_item.show()

        self._zoom_spin = gtk.SpinButton()
        self._zoom_spin.set_range(5.409, 400)
        self._zoom_spin.set_increments(1, 10)
        self._zoom_spin.props.value = self._evince_view.props.zoom * 100
        self._zoom_spin_notify_value_handler = self._zoom_spin.connect(
                'notify::value', self._zoom_spin_notify_value_cb)
        tool_item.add(self._zoom_spin)
        self._zoom_spin.show()

        zoom_perc_label = gtk.Label(_("%"))
        zoom_perc_label.show()
        tool_item_zoom_perc_label = gtk.ToolItem()
        tool_item_zoom_perc_label.add(zoom_perc_label)
        self.insert(tool_item_zoom_perc_label, -1)
        tool_item_zoom_perc_label.show()

        self._view_notify_zoom_handler = self._evince_view.connect(
                'notify::zoom', self._view_notify_zoom_cb)

        self._update_zoom_buttons()

    def _zoom_spin_notify_value_cb(self, zoom_spin, pspec):
        self._evince_view.disconnect(self._view_notify_zoom_handler)
        try:
            self._evince_view.props.sizing_mode = evince.SIZING_FREE
            self._evince_view.props.zoom = zoom_spin.props.value / 100.0
        finally:
            self._view_notify_zoom_handler = self._evince_view.connect(
                    'notify::zoom', self._view_notify_zoom_cb)

    def _view_notify_zoom_cb(self, evince_view, pspec):
        self._zoom_spin.disconnect(self._zoom_spin_notify_value_handler)
        try:
            self._zoom_spin.props.value = round(evince_view.props.zoom * 100.0)
        finally:
            self._zoom_spin_notify_value_handler = self._zoom_spin.connect(
                    'notify::value', self._zoom_spin_notify_value_cb)

    def _zoom_in_cb(self, button):
        self._evince_view.props.sizing_mode = evince.SIZING_FREE
        self._evince_view.zoom_in()
        self._update_zoom_buttons()
        
    def _zoom_out_cb(self, button):
        self._evince_view.props.sizing_mode = evince.SIZING_FREE
        self._evince_view.zoom_out()
        self._update_zoom_buttons()

    def _zoom_to_width_cb(self, button):
        self._evince_view.props.sizing_mode = evince.SIZING_FIT_WIDTH
        self._update_zoom_buttons()

    def _update_zoom_buttons(self):
        self._zoom_in.props.sensitive = self._evince_view.can_zoom_in()
        self._zoom_out.props.sensitive = self._evince_view.can_zoom_out()

    def _zoom_to_fit_menu_item_activate_cb(self, menu_item):
        self._evince_view.props.sizing_mode = evince.SIZING_BEST_FIT
        self._update_zoom_buttons()

    def _actual_size_menu_item_activate_cb(self, menu_item):
        self._evince_view.props.sizing_mode = evince.SIZING_FREE
        self._evince_view.props.zoom = 1.0
        self._update_zoom_buttons()

