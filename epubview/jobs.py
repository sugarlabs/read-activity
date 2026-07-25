# Copyright 2009 One Laptop Per Child
# Author: Sayamindu Dasgupta <sayamindu@laptop.org>
# WebKit2 port Copyright (C) 2018 Lubomir Rintel <lkundrak@v3.sk>
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

"""
Note: The legacy cross-chapter SearchThread and _JobFind infrastructure was 
removed. The old design relied on synchronous background threading to parse 
and search chapters. Modern WebKit requires using FindController, which 
operates asynchronously and strictly on the active WebView's DOM. A multi-page 
search across EPUB chapters now requires sequentially loading each chapter into 
a WebView and waiting for async callbacks, necessitating a complete redesign.
"""

import gi
gi.require_version('WebKit', '6.0')

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import WebKit
from . import widgets
import math
import os.path


PAGE_WIDTH = 135
PAGE_HEIGHT = 216


def _pixel_to_mm(pixel, dpi):
    inches = pixel / dpi
    return int(inches / 0.03937)


def _mm_to_pixel(mm, dpi):
    inches = mm * 0.03937
    return int(inches * dpi)


class _JobPaginator(GObject.GObject):

    __gsignals__ = {
        'paginated': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, ([])),
    }

    def __init__(self, filelist):
        super().__init__()

        self._filelist = filelist
        self._filedict = {}
        self._pagemap = {}

        self._bookheight = 0
        self._count = 0
        self._pagecount = 0

        self._temp_win = Gtk.Window()
        self._temp_view = widgets._WebView()

        settings = self._temp_view.get_settings()
        settings.props.default_font_family = 'DejaVu LGC Serif'
        settings.props.sans_serif_font_family = 'DejaVu LGC Sans'
        settings.props.serif_font_family = 'DejaVu LGC Serif'
        settings.props.monospace_font_family = 'DejaVu LGC Sans Mono'
        # FIXME: This does not seem to work
        # settings.props.auto_shrink_images = False
        settings.props.default_font_size = 16
        settings.props.default_monospace_font_size = 13
        settings.props.default_charset = 'utf-8'

        gtk_settings = Gtk.Settings.get_default()
        if gtk_settings and gtk_settings.get_property('gtk-xft-dpi') > 0:
            self._dpi = float(gtk_settings.get_property('gtk-xft-dpi') / 1024)
        else:
            self._dpi = 96.0
        self._single_page_height = _mm_to_pixel(PAGE_HEIGHT, self._dpi)
        self._temp_view.set_size_request(
            _mm_to_pixel(PAGE_WIDTH, self._dpi), self._single_page_height)

        self._temp_win.set_child(self._temp_view)
        self._temp_view.connect('load-changed', self._page_load_changed_cb)

        self._temp_win.set_visible(True)
        self._temp_win.unmap()

        self._temp_view.load_uri('file://' + self._filelist[self._count])

    def get_single_page_height(self):
        """
        Returns the height in pixels of a single page
        """
        return self._single_page_height

    def get_next_filename(self, actual_filename):
        for n in range(len(self._filelist)):
            filename = self._filelist[n]
            if filename == actual_filename:
                if n + 1 < len(self._filelist):
                    return self._filelist[n + 1]
        return None

    def _page_load_changed_cb(self, v, load_event):
        if load_event != WebKit.LoadEvent.FINISHED:
            return True

        pageheight = v.get_page_height()

        if pageheight <= self._single_page_height:
            pages = 1
        else:
            pages = pageheight / float(self._single_page_height)
        for i in range(1, int(math.ceil(pages) + 1)):
            if pages - i < 0:
                pagelen = (pages - math.floor(pages)) / pages
            else:
                pagelen = 1 / pages
            self._pagemap[float(self._pagecount + i)] = \
                (v.get_uri(), (i - 1) / math.ceil(pages), pagelen)

        self._pagecount += int(math.ceil(pages))
        self._filedict[v.get_uri().replace('file://', '')] = \
            (math.ceil(pages), math.ceil(pages) - pages)
        self._bookheight += pageheight

        if self._count + 1 >= len(self._filelist):
            self.emit('paginated')
            GObject.idle_add(self._cleanup)

        else:
            self._count += 1
            self._temp_view.load_uri('file://' + self._filelist[self._count])

    def _cleanup(self):
        self._temp_win.destroy()

    def get_file_for_pageno(self, pageno):
        '''
        Returns the file in which pageno occurs
        '''
        return self._pagemap[pageno][0]

    def get_scrollfactor_pos_for_pageno(self, pageno):
        '''
        Returns the position scrollfactor (fraction) for pageno
        '''
        return self._pagemap[pageno][1]

    def get_scrollfactor_len_for_pageno(self, pageno):
        '''
        Returns the length scrollfactor (fraction) for pageno
        '''
        return self._pagemap[pageno][2]

    def get_pagecount_for_file(self, filename):
        '''
        Returns the number of pages in file
        '''
        return self._filedict[filename][0]

    def get_base_pageno_for_file(self, filename):
        '''
        Returns the pageno which begins in filename
        '''
        for key in list(self._pagemap.keys()):
            if self._pagemap[key][0].replace('file://', '') == filename:
                return key

        return None

    def get_remfactor_for_file(self, filename):
        '''
        Returns the remainder
        factor (1 - fraction length of last page in file)
        '''
        return self._filedict[filename][1]

    def get_total_pagecount(self):
        '''
        Returns the total pagecount for the Epub file
        '''
        return self._pagecount

    def get_total_height(self):
        '''
        Returns the total height of the Epub in pixels
        '''
        return self._bookheight
