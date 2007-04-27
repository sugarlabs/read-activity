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

import pango
import gobject
import gtk

from sugar.graphics.toolbutton import ToolButton

class XbookToolbar(gtk.Toolbar):
    __gtype_name__ = 'XbookToolbar'

    __gsignals__ = {
        'open-document':  (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
                            ([]))
    }

    def __init__(self, evince_view):
        gtk.Toolbar.__init__(self)

        self._evince_view = evince_view
        self._document = None
                
#        self._insert_opensave_items()
#        self._insert_spring()       
        self._insert_nav_items()
        self._insert_spring()       
        self._insert_search_items()

    def set_document(self, document):
        self._document = document
        self._document.connect('find_changed', self._find_changed_cb)  
        
        page_cache = self._document.get_page_cache()
        page_cache.connect('page-changed', self._page_changed_cb)    
        self._update_nav_buttons()

    def _insert_spring(self):
        separator = gtk.SeparatorToolItem()
        separator.set_draw(False)
        separator.set_expand(True)
        self.insert(separator, -1)
        separator.show()

    def _insert_opensave_items(self):
        self._open = ToolButton()
        self._open.set_icon_name('stock-open')
        self._open.connect('clicked', self._open_cb)
        self.insert(self._open, -1)
        self._open.show()

    def _insert_nav_items(self):
        self._back = ToolButton()
        self._back.props.sensitive = False
        self._back.set_icon_name('stock-back')
        self._back.connect('clicked', self._go_back_cb)
        self.insert(self._back, -1)
        self._back.show()

        self._forward = ToolButton()
        self._back.props.sensitive = False
        self._forward.set_icon_name('stock-forward')
        self._forward.connect('clicked', self._go_forward_cb)
        self.insert(self._forward, -1)
        self._forward.show()

        num_page_item = gtk.ToolItem()

        self._num_page_entry = gtk.Entry()
        self._num_page_entry.set_text('0')
        self._num_page_entry.set_alignment(1)
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

    def _insert_search_items(self):
        search_item = gtk.ToolItem()

        self._search_entry = gtk.Entry()
        self._search_entry.connect('activate', self._search_entry_activate_cb)

        width = int(gtk.gdk.screen_width() / 3)
        self._search_entry.set_size_request(width, -1)

        search_item.add(self._search_entry)
        self._search_entry.show()

        self.insert(search_item, -1)
        search_item.show()

        self._prev = ToolButton()
        self._prev.props.sensitive = False
        self._prev.set_icon_name('stock-back')
        self._prev.connect('clicked', self._find_prev_cb)
        self.insert(self._prev, -1)
        self._prev.show()

        self._next = ToolButton()
        self._next.props.sensitive = False
        self._next.set_icon_name('stock-forward')
        self._next.connect('clicked', self._find_next_cb)
        self.insert(self._next, -1)
        self._next.show()

    def _num_page_entry_activate_cb(self, entry):
        page = int(entry.props.text) - 1
        self._document.get_page_cache().set_current_page(page)
        
    def _search_entry_activate_cb(self, entry):
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
        self._back.props.sensitive = current_page > 0
        self._forward.props.sensitive = \
            current_page < self._document.get_n_pages() - 1
        
        self._num_page_entry.props.text = str(current_page + 1)
        self._total_page_label.props.label = \
            ' / ' + str(self._document.get_n_pages())

    def _update_find_buttons(self):
        self._prev.props.sensitive = self._evince_view.can_find_previous()
        self._next.props.sensitive = self._evince_view.can_find_next()

    def _open_cb(self, button):
        self.emit('open-document')
