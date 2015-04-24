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

from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import Gdk
import widgets

import logging
import os.path
import math
import shutil

from jobs import _JobPaginator as _Paginator

LOADING_HTML = '''
<div style="width:100%;height:100%;text-align:center;padding-top:50%;">
    <h1>Loading...</h1>
</div>
'''


class _View(Gtk.HBox):

    __gproperties__ = {
        'scale': (GObject.TYPE_FLOAT, 'the zoom level',
                  'the zoom level of the widget',
                  0.5, 4.0, 1.0, GObject.PARAM_READWRITE),
    }
    __gsignals__ = {
        'page-changed': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE,
                         ([int, int])),
        'selection-changed': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE,
                              ([])),
    }

    def __init__(self):
        GObject.threads_init()
        Gtk.HBox.__init__(self)

        self.connect("destroy", self._destroy_cb)

        self._ready = False
        self._paginator = None
        self._loaded_page = -1
        self._file_loaded = True
        # self._old_scrollval = -1
        self._loaded_filename = None
        self._pagecount = -1
        self.__going_fwd = True
        self.__going_back = False
        self.__page_changed = False
        self._has_selection = False
        self.scale = 1.0
        self._epub = None
        self._findjob = None
        self.__in_search = False
        self.__search_fwd = True
        self._filelist = None
        self._internal_link = None

        self._sw = Gtk.ScrolledWindow()
        self._view = widgets._WebView()
        self._view.load_string(LOADING_HTML, 'text/html', 'utf-8', '/')
        settings = self._view.get_settings()
        settings.props.default_font_family = 'DejaVu LGC Serif'
        settings.props.enable_plugins = False
        settings.props.default_encoding = 'utf-8'
        self._view.connect('load-finished', self._view_load_finished_cb)
        self._view.connect('scroll-event', self._view_scroll_event_cb)
        self._view.connect('key-press-event', self._view_keypress_event_cb)
        self._view.connect('selection-changed',
                           self._view_selection_changed_cb)
        self._view.connect_after('populate-popup',
                                 self._view_populate_popup_cb)
        self._view.connect('touch-change-page', self.__touch_page_changed_cb)

        self._sw.add(self._view)
        self._v_vscrollbar = self._sw.get_vscrollbar()
        self._v_scrollbar_value_changed_cb_id = self._v_vscrollbar.connect(
            'value-changed', self._v_scrollbar_value_changed_cb)
        self._scrollbar = Gtk.VScrollbar()
        self._scrollbar_change_value_cb_id = self._scrollbar.connect(
            'change-value', self._scrollbar_change_value_cb)

        overlay = Gtk.Overlay()
        hbox = Gtk.HBox()
        overlay.add(hbox)
        hbox.add(self._sw)

        self._scrollbar.props.halign = Gtk.Align.END
        self._scrollbar.props.valign = Gtk.Align.FILL
        overlay.add_overlay(self._scrollbar)

        self.pack_start(overlay, True, True, 0)

        self._view.set_can_default(True)
        self._view.set_can_focus(True)

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
        return self._view.can_copy_clipboard()

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
        return self._v_vscrollbar.get_adjustment().get_value()

    def set_vertical_pos(self, position):
        """
        Used to save the scrolled position and restore when needed
        """
        self._v_vscrollbar.get_adjustment().set_value(position)

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
        Gtk.ScrollType.STEP_START and Gtk.ScrollType.STEP_STOP
        '''
        if scrolltype == Gtk.ScrollType.PAGE_BACKWARD:
            self.__going_back = True
            self.__going_fwd = False
            if not self._do_page_transition():
                self._view.move_cursor(Gtk.MovementStep.PAGES, -1)
        elif scrolltype == Gtk.ScrollType.PAGE_FORWARD:
            self.__going_back = False
            self.__going_fwd = True
            if not self._do_page_transition():
                self._view.move_cursor(Gtk.MovementStep.PAGES, 1)
        elif scrolltype == Gtk.ScrollType.STEP_BACKWARD:
            self.__going_fwd = False
            self.__going_back = True
            if not self._do_page_transition():
                self._view.move_cursor(Gtk.MovementStep.DISPLAY_LINES, -1)
        elif scrolltype == Gtk.ScrollType.STEP_FORWARD:
            self.__going_fwd = True
            self.__going_back = False
            if not self._do_page_transition():
                self._view.move_cursor(Gtk.MovementStep.DISPLAY_LINES, 1)
        elif scrolltype == Gtk.ScrollType.START:
            self.__going_back = True
            self.__going_fwd = False
            if not self._do_page_transition():
                self.set_current_page(1)
        elif scrolltype == Gtk.ScrollType.END:
            self.__going_back = False
            self.__going_fwd = True
            if not self._do_page_transition():
                self.set_current_page(self._pagecount - 1)
        else:
            print ('Got unsupported scrolltype %s' % str(scrolltype))

    def __touch_page_changed_cb(self, widget, forward):
        if forward:
            self.scroll(Gtk.ScrollType.PAGE_FORWARD, False)
        else:
            self.scroll(Gtk.ScrollType.PAGE_BACKWARD, False)

    def copy(self):
        '''
        Copies the current selection to clipboard.
        '''
        self._view.copy_clipboard()

    def find_next(self):
        '''
        Highlights the next matching item for current search
        '''
        self._view.grab_focus()

        if self._view.search_text(self._findjob.get_search_text(),
                                  self._findjob.get_case_sensitive(),
                                  True, False):
            return
        else:
            path = os.path.join(self._epub.get_basedir(),
                                self._findjob.get_next_file())
            self.__in_search = True
            self.__search_fwd = True
            self._load_file(path)

    def find_previous(self):
        '''
        Highlights the previous matching item for current search
        '''
        self._view.grab_focus()

        if self._view.search_text(self._findjob.get_search_text(),
                                  self._findjob.get_case_sensitive(),
                                  False, False):
            return
        else:
            path = os.path.join(self._epub.get_basedir(),
                                self._findjob.get_prev_file())
            self.__in_search = True
            self.__search_fwd = False
            self._load_file(path)

    def _find_changed(self, job):
        self._view.grab_focus()
        self._findjob = job
        self._mark_found_text()
        self.find_next()

    def _mark_found_text(self):
        self._view.unmark_text_matches()
        self._view.mark_text_matches(
            self._findjob.get_search_text(),
            case_sensitive=self._findjob.get_case_sensitive(), limit=0)
        self._view.set_highlight_text_matches(True)

    def __set_zoom(self, value):
        self._view.set_zoom_level(value)
        self.scale = value

    def _view_populate_popup_cb(self, view, menu):
        menu.destroy()  # HACK
        return

    def _view_selection_changed_cb(self, view):
        self.emit('selection-changed')

    def _view_keypress_event_cb(self, view, event):
        name = Gdk.keyval_name(event.keyval)
        if name == 'Page_Down' or name == 'Down':
            self.__going_back = False
            self.__going_fwd = True
        elif name == 'Page_Up' or name == 'Up':
            self.__going_back = True
            self.__going_fwd = False

        self._do_page_transition()

    def _view_scroll_event_cb(self, view, event):
        if event.direction == Gdk.ScrollDirection.DOWN:
            self.__going_back = False
            self.__going_fwd = True
        elif event.direction == Gdk.ScrollDirection.UP:
            self.__going_back = True
            self.__going_fwd = False

        self._do_page_transition()

    def _do_page_transition(self):
        if self.__going_fwd:
            if self._v_vscrollbar.get_value() >= \
                self._v_vscrollbar.props.adjustment.props.upper - \
                    self._v_vscrollbar.props.adjustment.props.page_size:
                self._load_page(self._loaded_page + 1)
                return True
        elif self.__going_back:
            if self._v_vscrollbar.get_value() == \
                    self._v_vscrollbar.props.adjustment.props.lower:
                self._load_page(self._loaded_page - 1)
                return True

        return False

    def _view_load_finished_cb(self, v, frame):

        self._file_loaded = True
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

        if self.__in_search:
            self._mark_found_text()
            self._view.search_text(self._findjob.get_search_text(),
                                   self._findjob.get_case_sensitive(),
                                   self.__search_fwd, False)
            self.__in_search = False
        else:
            if self.__going_back:
                # We need to scroll to the last page
                self._scroll_page_end()
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
            if vertical_pos > self._view.get_page_height() - one_page_height:
                logging.error('bottom page link, go to next file')
                next_file = self._paginator.get_next_filename(filename)
                if next_file is not None:
                    logging.error('load next file %s', next_file)
                    self.__in_search = False
                    self.__going_back = False
                    # process_file = False
                    GObject.idle_add(self._load_file, next_file)

#        if process_file:
#            # prepare text to speech
#            html_file = open(self._loaded_filename)
#            soup = BeautifulSoup.BeautifulSoup(html_file)
#            body = soup.find('body')
#            tags = body.findAll(text=True)
#            self._all_text = ''.join([tag for tag in tags])
#            self._prepare_text_to_speech(self._all_text)

    def _prepare_text_to_speech(self, page_text):
        i = 0
        j = 0
        word_begin = 0
        word_end = 0
        ignore_chars = [' ',  '\n',  u'\r',  '_',  '[', '{', ']', '}', '|',
                        '<',  '>',  '*',  '+',  '/',  '\\']
        ignore_set = set(ignore_chars)
        self.word_tuples = []
        len_page_text = len(page_text)
        while i < len_page_text:
            if page_text[i] not in ignore_set:
                word_begin = i
                j = i
                while j < len_page_text and page_text[j] not in ignore_set:
                    j = j + 1
                    word_end = j
                    i = j
                word_tuple = (word_begin, word_end,
                              page_text[word_begin: word_end])
                if word_tuple[2] != u'\r':
                    self.word_tuples.append(word_tuple)
            i = i + 1

    def _scroll_page_end(self):
        v_upper = self._v_vscrollbar.props.adjustment.props.upper
        # v_page_size = self._v_vscrollbar.props.adjustment.props.page_size
        self._v_vscrollbar.set_value(v_upper)

    def _scroll_page(self):
        pageno = self._loaded_page

        v_upper = self._v_vscrollbar.props.adjustment.props.upper
        v_page_size = self._v_vscrollbar.props.adjustment.props.page_size

        scrollfactor = self._paginator.get_scrollfactor_pos_for_pageno(pageno)
        self._v_vscrollbar.set_value((v_upper - v_page_size) * scrollfactor)

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

    def _v_scrollbar_value_changed_cb(self, scrollbar):
        if self._loaded_page < 1:
            return
        scrollval = scrollbar.get_value()
        scroll_upper = self._v_vscrollbar.props.adjustment.props.upper
        scroll_page_size = self._v_vscrollbar.props.adjustment.props.page_size

        if self.__going_fwd and not self._loaded_page == self._pagecount:
            if self._paginator.get_file_for_pageno(self._loaded_page) != \
                    self._paginator.get_file_for_pageno(self._loaded_page + 1):
                # We don't need this if the next page is in another file
                return

            scrollfactor_next = \
                self._paginator.get_scrollfactor_pos_for_pageno(
                    self._loaded_page + 1)
            if scrollval > 0:
                scrollfactor = scrollval / (scroll_upper - scroll_page_size)
            else:
                scrollfactor = 0
            if scrollfactor >= scrollfactor_next:
                self._on_page_changed(self._loaded_page, self._loaded_page + 1)
        elif self.__going_back and self._loaded_page > 1:
            if self._paginator.get_file_for_pageno(self._loaded_page) != \
                    self._paginator.get_file_for_pageno(self._loaded_page - 1):
                return

            scrollfactor_cur = \
                self._paginator.get_scrollfactor_pos_for_pageno(
                    self._loaded_page)
            if scrollval > 0:
                scrollfactor = scrollval / (scroll_upper - scroll_page_size)
            else:
                scrollfactor = 0

            if scrollfactor <= scrollfactor_cur:
                self._on_page_changed(self._loaded_page, self._loaded_page - 1)

    def _on_page_changed(self, oldpage, pageno):
        if oldpage == pageno:
            return
        self.__page_changed = True
        self._loaded_page = pageno
        self._scrollbar.handler_block(self._scrollbar_change_value_cb_id)
        self._scrollbar.set_value(pageno)
        self._scrollbar.handler_unblock(self._scrollbar_change_value_cb_id)
        # the indexes in read activity are zero based
        self.emit('page-changed', (oldpage - 1), (pageno - 1))

    def _load_page(self, pageno):
        if pageno > self._pagecount or pageno < 1:
            # TODO: Cause an exception
            return
        if self._loaded_page == pageno:
            return

        filename = self._paginator.get_file_for_pageno(pageno)
        filename = filename.replace('file://', '')

        if filename != self._loaded_filename:
            self._loaded_filename = filename
            if not self._file_loaded:
                # wait until the file is loaded
                return
            self._file_loaded = False

            """
            TODO: disabled because javascript can't be executed
            with the velocity needed
            # Copy javascript to highligth text to speech
            destpath, destname = os.path.split(filename.replace('file://', ''))
            shutil.copy('./epubview/highlight_words.js', destpath)
            self._insert_js_reference(filename.replace('file://', ''),
                    destpath)
            IMPORTANT: Find a way to do this without modify the files
            now text highlight is implemented and the epub file is saved
            """

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
        self._on_page_changed(self._loaded_page, pageno)

    def _insert_js_reference(self, file_name, path):
        js_reference = '<script type="text/javascript" ' + \
            'src="./highlight_words.js"></script>'
        o = open(file_name + '.tmp', 'a')
        for line in open(file_name):
            line = line.replace('</head>', js_reference + '</head>')
            o.write(line + "\n")
        o.close()
        shutil.copy(file_name + '.tmp', file_name)

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

    def _scrollbar_change_value_cb(self, range, scrolltype, value):
        if scrolltype == Gtk.ScrollType.STEP_FORWARD:
            self.__going_fwd = True
            self.__going_back = False
            if not self._do_page_transition():
                self._view.move_cursor(Gtk.MovementStep.DISPLAY_LINES, 1)
        elif scrolltype == Gtk.ScrollType.STEP_BACKWARD:
            self.__going_fwd = False
            self.__going_back = True
            if not self._do_page_transition():
                self._view.move_cursor(Gtk.MovementStep.DISPLAY_LINES, -1)
        elif scrolltype == Gtk.ScrollType.JUMP or \
            scrolltype == Gtk.ScrollType.PAGE_FORWARD or \
                scrolltype == Gtk.ScrollType.PAGE_BACKWARD:
            if value > self._scrollbar.props.adjustment.props.upper:
                self._load_page(self._pagecount)
            else:
                self._load_page(round(value))
        else:
            print 'Warning: unknown scrolltype %s with value %f' \
                % (str(scrolltype), value)

        # FIXME: This should not be needed here
        self._scrollbar.set_value(self._loaded_page)

        if self.__page_changed:
            self.__page_changed = False
            return False
        else:
            return True

    def _paginated_cb(self, object):
        self._ready = True

        self._pagecount = self._paginator.get_total_pagecount()
        self._scrollbar.set_range(1.0, self._pagecount - 1.0)
        self._scrollbar.set_increments(1.0, 1.0)
        self._view.grab_focus()
        self._view.grab_default()

    def _destroy_cb(self, widget):
        self._epub.close()
