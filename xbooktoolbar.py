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

import hippo
import gobject

from sugar.graphics import font
from sugar.graphics import color
from sugar.graphics import units
from sugar.graphics.toolbar import Toolbar
from sugar.graphics.iconbutton import IconButton
from sugar.graphics.entry import Entry

class XbookToolbar(Toolbar):
    __gtype_name__ = "XbookToolbar"

    __gsignals__ = {
        'open-document':  (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
                            ([]))
    }

    def __init__(self, evince_view):
        Toolbar.__init__(self)

        self._evince_view = evince_view
        self._document = None
                
        self._insert_opensave_items()
        self._insert_spring()       
        self._insert_nav_items()
        self._insert_spring()       
        self._insert_search_items()

    def set_document(self, document):
        self._document = document
        self._document.connect("find_changed", self._find_changed_cb)  
        
        page_cache = self._document.get_page_cache()
        page_cache.connect("page-changed", self._page_changed_cb)    
        self._update_nav_buttons()

    def _insert_spring(self):
        separator = hippo.CanvasBox()
        self.append(separator, hippo.PACK_EXPAND)

    def _insert_opensave_items(self):
        self._open = IconButton(icon_name='theme:stock-open', active=True)
        self._open.connect("activated", self._open_cb)
        self.append(self._open)

    def _insert_nav_items(self):
        self._back = IconButton(icon_name='theme:stock-back', active=False)
        self._back.connect("activated", self._go_back_cb)
        self.append(self._back)

        self._forward = IconButton(icon_name='theme:stock-forward', active=False)
        self._forward.connect("activated", self._go_forward_cb)
        self.append(self._forward)
        
        self._num_page_entry = Entry(text='0', box_width=units.grid_to_pixels(1))
        self._num_page_entry.connect("activated",
            self._num_page_entry_activated_cb)
        self.append(self._num_page_entry)

        self._total_page_label = hippo.CanvasText(text=' / 0',
            font_desc=font.DEFAULT.get_pango_desc(),
            color=color.WHITE.get_int())
        self.append(self._total_page_label)
        
    def _insert_search_items(self):
        self._search_entry = Entry()
        self._search_entry.connect("activated", self._search_entry_activated_cb)
        
        self.append(self._search_entry, hippo.PACK_EXPAND)

        self._prev = IconButton(icon_name='theme:stock-back', active=False)
        self._prev.connect("activated", self._find_prev_cb)
        self.append(self._prev)

        self._next = IconButton(icon_name='theme:stock-forward', active=False)
        self._next.connect("activated", self._find_next_cb)
        self.append(self._next)

    def _num_page_entry_activated_cb(self, entry):
        page = int(entry.props.text) - 1
        self._document.get_page_cache().set_current_page(page)
        
    def _search_entry_activated_cb(self, entry):
        current_page = self._document.get_page_cache().get_current_page()
        self._document.find_begin(0, entry.props.text, False)
        self._update_find_buttons()
        
    def _find_prev_cb(self, button):
        self._evince_view.find_previous()
    
    def _find_next_cb(self, button):
        self._evince_view.find_next()
        
    def _go_back_cb(self, button):
        self._evince_view.previous_page()
    
    def _go_forward_cb(self, button):
        self._evince_view.next_page()
    
    def _page_changed_cb(self, page, proxy):
        self._update_nav_buttons()
    
    def _find_changed_cb(self, page, spec):
        self._update_find_buttons()

    def _update_nav_buttons(self):
        current_page = self._document.get_page_cache().get_current_page()
        self._back.props.active = current_page > 0
        self._forward.props.active = \
            current_page < self._document.get_n_pages() - 1
        
        self._num_page_entry.props.text = str(current_page + 1)
        self._total_page_label.props.text = \
            ' / ' + str(self._document.get_n_pages())

    def _update_find_buttons(self):
        self._prev.props.active = self._evince_view.can_find_previous()
        self._next.props.active = self._evince_view.can_find_next()

    def _open_cb(self, button):
        self.emit('open-document')
