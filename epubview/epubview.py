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

import gi
gi.require_version('WebKit', '6.0')

from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import Gdk
from gi.repository import WebKit
from . import widgets

import logging
import os.path
import math
import shutil

from .jobs import _JobPaginator as _Paginator

LOADING_HTML = '''
<html style="height: 100%; margin: 0; padding: 0; width: 100%;">
    <body style="display: table; height: 100%; margin: 0; padding: 0;
        width: 100%;">
        <div style="display: table-cell; text-align: center;
            vertical-align: middle;">
            <h1>Loading...</h1>
        </div>
    </body>
</html>
'''


class _View(Gtk.Box):

    __gproperties__ = {
        'scale': (GObject.TYPE_DOUBLE, 'the zoom level',
                  'the zoom level of the widget',
                  0.01, 10.0, 1.0, GObject.PARAM_READWRITE),
    }
    __gsignals__ = {
        'page-changed': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE,
                         ([int, int])),
        'selection-changed': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE,
                              ([])),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)

        self.connect("destroy", self._destroy_cb)

        self._ready = False
        self._paginator = None
        self._loaded_page = -1
        # self._old_scrollval = -1
        self._loaded_filename = None
        self._pagecount = -1
        self.__scroll_to_end = False
        self.__page_changed = False
        self._has_selection = False
        self._scrollval = 0.0
        self.scale = 1.0
        self._epub = None
        self._findjob = None
        self.__in_search = False
        self.__search_fwd = True
        self.__has_active_search = False
        self._filelist = None
        self._internal_link = None

        self._view = widgets._WebView()
        self._view.load_html(LOADING_HTML, '/')
        settings = self._view.get_settings()
        settings.props.default_font_family = 'DejaVu LGC Serif'
        settings.props.default_charset = 'utf-8'
        self._view.connect('load-changed', self._view_load_changed_cb)
        self._view.connect('scrolled', self._view_scrolled_cb)
        self._view.connect('scrolled-top', self._view_scrolled_top_cb)
        self._view.connect('scrolled-bottom', self._view_scrolled_bottom_cb)
        self._view.connect(
            'selection-changed', self._view_selection_changed_cb)

        find = self._view.get_find_controller()
        find.connect('failed-to-find-text', self._find_failed_cb)

        self._eventbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        scroll_ctrl = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
        scroll_ctrl.connect('scroll', self._eventbox_scroll_event_cb)
        self._eventbox.add_controller(scroll_ctrl)
        self._eventbox.append(self._view)

        adj = Gtk.Adjustment()
        self._scrollbar = Gtk.Scrollbar(orientation=Gtk.Orientation.VERTICAL, adjustment=adj)
        self._scrollbar_change_value_cb_id = self._scrollbar.get_adjustment().connect(
            'value-changed', self._scrollbar_change_value_cb)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self._eventbox.set_hexpand(True)
        self._eventbox.set_vexpand(True)
        hbox.append(self._eventbox)
        hbox.append(self._scrollbar)

        hbox.set_hexpand(True)
        hbox.set_vexpand(True)
        self.append(hbox)
        self._view.set_receives_default(True)
        self._view.set_focusable(True)

        def map_cp(widget):
            widget.setup_touch()
            widget.disconnect(self._setup_handle)

        self._setup_handle = self._view.connect('map', map_cp)

    def set_document(self, epubdocumentinstance):
        '''
        Sets document (should be a Epub instance)
        '''
        self._epub = epubdocumentinstance
        GObject.idle_add(self._paginate)

    def do_get_property(self, property):
        if property.name == 'has-selection':
            return self._has_selection
        elif property.name == 'scale':
            return self.scale
        else:
            raise AttributeError('unknown property %s' % property.name)

    def do_set_property(self, property, value):
        if property.name == 'scale':
            self.__set_zoom(value)
        else:
            raise AttributeError('unknown property %s' % property.name)

    def get_has_selection(self):
        '''
        Returns True if any part of the content is selected
        '''
        return self._has_selection

    def get_zoom(self):
        '''
        Returns the current zoom level
        '''
        return self.get_property('scale') * 100.0

    def set_zoom(self, value):
        '''
        Sets the current zoom level
        '''
        scrollbar_pos = self.get_vertical_pos()
        self._view.set_zoom_level(value / 100.0)
        self.set_vertical_pos(scrollbar_pos)

    def _get_scale(self):
        '''
        Returns the current zoom level
        '''
        return self.get_property('scale')

    def _set_scale(self, value):
        '''
        Sets the current zoom level
        '''
        self.set_property('scale', value)

    def zoom_in(self):
        '''
        Zooms in (increases zoom level by 0.1)
        '''
        if self.can_zoom_in():
            scrollbar_pos = self.get_vertical_pos()
            self._set_scale(self._get_scale() + 0.1)
            self.set_vertical_pos(scrollbar_pos)
            return True
        else:
            return False

    def zoom_out(self):
        '''
        Zooms out (decreases zoom level by 0.1)
        '''
        if self.can_zoom_out():
            scrollbar_pos = self.get_vertical_pos()
            self._set_scale(self._get_scale() - 0.1)
            self.set_vertical_pos(scrollbar_pos)
            return True
        else:
            return False

    def get_vertical_pos(self):
        """
        Used to save the scrolled position and restore when needed
        """
        return self._scrollval

    def set_vertical_pos(self, position):
        """
        Used to save the scrolled position and restore when needed
        """
        self._view.scroll_to(position)

    def can_zoom_in(self):
        '''
        Returns True if it is possible to zoom in further
        '''
        if self.scale < 4:
            return True
        else:
            return False

    def can_zoom_out(self):
        '''
        Returns True if it is possible to zoom out further
        '''
        if self.scale > 0.5:
            return True
        else:
            return False

    def get_current_page(self):
        '''
        Returns the currently loaded page
        '''
        return self._loaded_page

    def get_current_file(self):
        '''
        Returns the currently loaded XML file
        '''
        # return self._loaded_filename
        if self._paginator:
            return self._paginator.get_file_for_pageno(self._loaded_page)
        else:
            return None

    def get_pagecount(self):
        '''
        Returns the pagecount of the loaded file
        '''
        return self._pagecount

    def set_current_page(self, n):
        '''
        Loads page number n
        '''
        if n < 1 or n > self._pagecount:
            return False
        self._load_page(n)
        return True

    def next_page(self):
        '''
        Loads next page if possible
        Returns True if transition to next page is possible and done
        '''
        if self._loaded_page == self._pagecount:
            return False
        self._load_next_page()
        return True

    def previous_page(self):
        '''
        Loads previous page if possible
        Returns True if transition to previous page is possible and done
        '''
        if self._loaded_page == 1:
            return False
        self._load_prev_page()
        return True

    def scroll(self, scrolltype, horizontal):
        '''
        Scrolls through the pages.
        Scrolling is horizontal if horizontal is set to True
        Valid scrolltypes are:
        Gtk.ScrollType.PAGE_BACKWARD, Gtk.ScrollType.PAGE_FORWARD,
        Gtk.ScrollType.STEP_BACKWARD, Gtk.ScrollType.STEP_FORWARD
        Gtk.ScrollType.STEP_START and Gtk.ScrollType.STEP_END
        '''
        if scrolltype == Gtk.ScrollType.PAGE_BACKWARD:
            pages = self._paginator.get_pagecount_for_file(
                self._loaded_filename)
            self._view.scroll_by(self._page_height / pages * -1)
        elif scrolltype == Gtk.ScrollType.PAGE_FORWARD:
            pages = self._paginator.get_pagecount_for_file(
                self._loaded_filename)
            self._view.scroll_by(self._page_height / pages * 1)
        elif scrolltype == Gtk.ScrollType.STEP_BACKWARD:
            self._view.scroll_by(
                self._view.get_settings().get_default_font_size() * -3)
        elif scrolltype == Gtk.ScrollType.STEP_FORWARD:
            self._view.scroll_by(
                self._view.get_settings().get_default_font_size() * 3)
        elif scrolltype == Gtk.ScrollType.START:
            self.set_current_page(0)
        elif scrolltype == Gtk.ScrollType.END:
            self.__scroll_to_end = True
            self.set_current_page(self._pagecount - 1)
        else:
            print('Got unsupported scrolltype %s' % str(scrolltype))

    def __touch_page_changed_cb(self, widget, forward):
        if forward:
            self.scroll(Gtk.ScrollType.PAGE_FORWARD, False)
        else:
            self.scroll(Gtk.ScrollType.PAGE_BACKWARD, False)

    def copy(self):
        '''
        Copies the current selection to clipboard.
        '''
        self._view.evaluate_javascript('document.execCommand("copy")', -1, None, None, None, None, None)

    def find_next(self):
        '''
        Highlights the next matching item for current search
        '''
        self._view.grab_focus()
        self.__search_fwd = True
        self._view.get_find_controller().search_next()

    def find_previous(self):
        '''
        Highlights the previous matching item for current search
        '''
        self._view.grab_focus()
        self.__search_fwd = False
        self._view.get_find_controller().search_previous()

    def clear_search(self):
        '''
        Clears the current search
        '''
        self._view.get_find_controller().search_finish()
        self.__has_active_search = False

    def _find_failed_cb(self, find_controller):
        # TODO: Implement cross-page search navigation when a term is not found on the current page
        pass

    def has_search_results(self):
        '''
        Returns True if there is an active search with results
        '''
        return self.__has_active_search

    def start_search(self, text, updated_cb=None):
        self._view.grab_focus()
        self.__in_search = True
        self.__search_fwd = True
        self.__has_active_search = True
        find = self._view.get_find_controller()
        options = WebKit.FindOptions.CASE_INSENSITIVE | WebKit.FindOptions.WRAP_AROUND
        find.search(text, options, GObject.G_MAXUINT)

    def set_inverted_colors(self, active):
        '''
        Invert colors in the EPUB view via CSS filter injection
        '''
        if active:
            js = 'document.documentElement.style.filter = "invert(1) hue-rotate(180deg)";'
        else:
            js = 'document.documentElement.style.filter = "none";'
        self._view.evaluate_javascript(js, -1, None, None, None, None, None)

    def __set_zoom(self, value):
        self._view.set_zoom_level(value)
        self.scale = value

    def _view_scrolled_cb(self, view, scrollval):
        if self._loaded_page < 1:
            return

        self._scrollval = scrollval
        scroll_upper = self._page_height
        scroll_page_size = self._view.get_allocated_height()

        if scrollval > 0:
            try:
                scrollfactor = scrollval / (scroll_upper - scroll_page_size)
            except ZeroDivisionError:
                scrollfactor = 0
        else:
            scrollfactor = 0

        if not self._loaded_page == self._pagecount and \
            not self._paginator.get_file_for_pageno(self._loaded_page) != \
                self._paginator.get_file_for_pageno(self._loaded_page + 1):

            scrollfactor_next = \
                self._paginator.get_scrollfactor_pos_for_pageno(
                    self._loaded_page + 1)
            if scrollfactor >= scrollfactor_next:
                self._on_page_changed(self._loaded_page, self._loaded_page + 1)
                return

        if self._loaded_page > 1 and \
            not self._paginator.get_file_for_pageno(self._loaded_page) != \
                self._paginator.get_file_for_pageno(self._loaded_page - 1):

            scrollfactor_cur = \
                self._paginator.get_scrollfactor_pos_for_pageno(
                    self._loaded_page)
            if scrollfactor <= scrollfactor_cur:
                self._on_page_changed(self._loaded_page, self._loaded_page - 1)
                return

    def _view_scrolled_top_cb(self, view):
        if self._loaded_page > 1:
            self.__scroll_to_end = True
            self._load_prev_page()

    def _view_scrolled_bottom_cb(self, view):
        if self._loaded_page < self._pagecount:
            self._load_next_page()

    def _view_selection_changed_cb(self, view, has_selection):
        self._has_selection = has_selection
        self.emit('selection-changed')

    def _eventbox_scroll_event_cb(self, controller, dx, dy):
        if dy > 0:
            self.scroll(Gtk.ScrollType.STEP_FORWARD, False)
        elif dy < 0:
            self.scroll(Gtk.ScrollType.STEP_BACKWARD, False)

    def _view_load_changed_cb(self, v, load_event):
        if load_event != WebKit.LoadEvent.FINISHED:
            return True

        filename = self._view.props.uri.replace('file://', '')
        if os.path.exists(filename.replace('xhtml', 'xml')):
            # Hack for making javascript work
            filename = filename.replace('xhtml', 'xml')

        filename = filename.split('#')[0]  # Get rid of anchors

        if self._loaded_page < 1 or filename is None:
            return False

        self._loaded_filename = filename

        remfactor = self._paginator.get_remfactor_for_file(filename)
        pages = self._paginator.get_pagecount_for_file(filename)
        extra = int(math.ceil(
            remfactor * self._view.get_page_height() / (pages - remfactor)))
        if extra > 0:
            self._view.add_bottom_padding(extra)
        self._page_height = self._view.get_page_height()

        if self.__in_search:
            self.__in_search = False
            find = self._view.get_find_controller()
            options = WebKit.FindOptions.CASE_INSENSITIVE | WebKit.FindOptions.WRAP_AROUND
            if not self.__search_fwd:
                options |= WebKit.FindOptions.BACKWARDS
            find.search(find.get_search_text(),
                        options,
                        GObject.G_MAXUINT)
        else:
            self._scroll_page()

        # process_file = True
        if self._internal_link is not None:
            self._view.go_to_link(self._internal_link)
            vertical_pos = \
                self._view.get_vertical_position_element(self._internal_link)
            # set the page number based in the vertical position
            initial_page = self._paginator.get_base_pageno_for_file(filename)
            self._loaded_page = initial_page + int(
                vertical_pos / self._paginator.get_single_page_height())

            # There are epub files, created with Calibre,
            # where the link in the index points to the end of the previos
            # file to the needed chapter.
            # if the link is at the bottom of the page, we open the next file
            one_page_height = self._paginator.get_single_page_height()
            self._internal_link = None
            if vertical_pos > self._page_height - one_page_height:
                logging.error('bottom page link, go to next file')
                next_file = self._paginator.get_next_filename(filename)
                if next_file is not None:
                    logging.error('load next file %s', next_file)
                    self.__in_search = False
                    self.__scroll_to_end = False
                    # process_file = False
                    GObject.idle_add(self._load_file, next_file)

    def _scroll_page(self):
        v_upper = self._page_height
        if self.__scroll_to_end:
            # We need to scroll to the last page
            scrollval = v_upper
            self.__scroll_to_end = False
        else:
            pageno = self._loaded_page
            scrollfactor = self._paginator.get_scrollfactor_pos_for_pageno(
                pageno)
            scrollval = math.ceil(v_upper * scrollfactor)
        self._view.scroll_to(scrollval)

    def _paginate(self):
        filelist = []
        for i in self._epub._navmap.get_flattoc():
            filelist.append(os.path.join(self._epub._tempdir, i))
        # init files info
        self._filelist = filelist
        self._paginator = _Paginator(filelist)
        self._paginator.connect('paginated', self._paginated_cb)

    def get_filelist(self):
        return self._filelist

    def get_tempdir(self):
        return self._epub._tempdir

    def _load_next_page(self):
        self._load_page(self._loaded_page + 1)

    def _load_prev_page(self):
        self._load_page(self._loaded_page - 1)

    def _on_page_changed(self, oldpage, pageno):
        if oldpage == pageno:
            return
        self.__page_changed = True
        self._loaded_page = pageno
        self._scrollbar.get_adjustment().handler_block(self._scrollbar_change_value_cb_id)
        self._scrollbar.get_adjustment().set_value(pageno)
        self._scrollbar.get_adjustment().handler_unblock(self._scrollbar_change_value_cb_id)
        # the indexes in read activity are zero based
        self.emit('page-changed', (oldpage - 1), (pageno - 1))

    def _load_page(self, pageno):
        if pageno > self._pagecount or pageno < 1:
            # TODO: Cause an exception
            return
        if self._loaded_page == pageno:
            return

        oldpage = self._loaded_page

        filename = self._paginator.get_file_for_pageno(pageno)
        filename = filename.replace('file://', '')

        if filename != self._loaded_filename:
            self._loaded_filename = filename



            self._view.stop_loading()
            if filename.endswith('xml'):
                dest = filename.replace('xml', 'xhtml')
                if not os.path.exists(dest):
                    os.symlink(filename, dest)
                self._view.load_uri('file://' + dest)
            else:
                self._view.load_uri('file://' + filename)
        else:
            self._loaded_page = pageno
            self._scroll_page()
        self._on_page_changed(oldpage, pageno)

    def _load_file(self, path):
        self._internal_link = None
        if path.find('#') > -1:
            self._internal_link = path[path.find('#'):]
            path = path[:path.find('#')]

        for filepath in self._filelist:
            if filepath.endswith(path):
                self._view.load_uri('file://' + filepath)
                oldpage = self._loaded_page
                self._loaded_page = \
                    self._paginator.get_base_pageno_for_file(filepath)
                self._scroll_page()
                self._on_page_changed(oldpage, self._loaded_page)
                break

    def _scrollbar_change_value_cb(self, adjustment):
        value = adjustment.get_value()
        if value > adjustment.props.upper:
            self._load_page(self._pagecount)
        else:
            self._load_page(int(value))

        # FIXME: This should not be needed here
        adjustment.set_value(self._loaded_page)

        if self.__page_changed:
            self.__page_changed = False
            return False
        else:
            return True

    def _paginated_cb(self, object):
        self._ready = True

        self._pagecount = self._paginator.get_total_pagecount()
        adj = self._scrollbar.get_adjustment()
        adj.props.lower = 1.0
        adj.props.upper = self._pagecount
        adj.props.step_increment = 1.0
        adj.props.page_increment = 1.0
        self._view.grab_focus()

    def _destroy_cb(self, widget):
        if self._epub:
            self._epub.close()
