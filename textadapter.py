import os
import zipfile
import logging
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Pango
from gi.repository import GLib
from gi.repository import GObject
import threading

from sugar4 import mime
from sugar4.graphics import style

PAGE_SIZE = 38


# remove hard line breaks, apply a simple logic to try identify
# the unneeded
def _clean_text(line):
    if line != '\r\n' and len(line) > 2:
        if line[-3] not in ('.', ',', '-', ';') and len(line) > 60:
            line = line[:-2]
    return line


class TextViewer(GObject.GObject):

    __gsignals__ = {
        'zoom-changed': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE,
                         ([int])),
        'page-changed': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE,
                         ([int, int])),
        'selection-changed': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE,
                              ([])), }

    def setup(self, activity):
        self._activity = activity

        self.__going_fwd = False
        self.__going_back = True

        self.textview = Gtk.TextView()
        self.textview.set_editable(False)
        # Cursor must be visible to draw selection
        self.textview.set_cursor_visible(True)
        self.textview.set_left_margin(50)
        self.textview.set_right_margin(50)
        self.textview.set_justification(Gtk.Justification.LEFT)
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD)
        # Connect notify::has-selection to prevent excessive firing from programmatic mark changes
        self.textview.get_buffer().connect(
            'notify::has-selection', self._view_selection_changed_cb)
        self.connect('selection-changed',
                     activity._view_selection_changed_cb)

        self._click_gesture = Gtk.GestureClick.new()
        self._click_gesture.set_button(0)
        self._click_gesture.connect('pressed', self.__touch_event_cb)
        self.textview.add_controller(self._click_gesture)

        self._sw = Gtk.ScrolledWindow()
        self._sw.set_vexpand(True)
        self._sw.set_hexpand(True)
        self._sw.set_child(self.textview)
        
        self._scroll_controller = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL)
        self._scroll_controller.connect('scroll', self._on_scroll)
        self._sw.add_controller(self._scroll_controller)
        
        self._v_vscrollbar = self._sw.get_vscrollbar()
        self._adjustment = Gtk.Adjustment()
        self._scrollbar = Gtk.Scrollbar(
            orientation=Gtk.Orientation.VERTICAL, adjustment=self._adjustment)
        self._scrollbar_change_value_cb_id = \
            self._adjustment.connect('value-changed',
                                     self._scrollbar_change_value_cb)

        overlay = Gtk.Overlay()
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        overlay.set_child(hbox)
        hbox.append(self._sw)

        self._scrollbar.props.halign = Gtk.Align.END
        self._scrollbar.props.valign = Gtk.Align.FILL
        overlay.add_overlay(self._scrollbar)
        overlay.set_visible(True)

        overlay.set_hexpand(True)
        overlay.set_vexpand(True)
        activity._hbox.append(overlay)

        self.page_index = []
        self._font_size = style.zoom(12)
        self._inverted = False
        self._css_provider = Gtk.CssProvider()
        self.textview.get_style_context().add_provider(
            self._css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        
        self._zoom = 100
        self.font_zoom_relation = self._zoom // self._font_size
        self._update_font()
        self._current_page = 0
        self._search_text = ""

        yellow = Gdk.RGBA()
        yellow.parse('yellow')
        black = Gdk.RGBA()
        black.parse('black')
        gray = Gdk.RGBA()
        gray.parse('gray')

        self.highlight_tag = self.textview.get_buffer().create_tag("highlight")
        self.highlight_tag.set_property('underline', Pango.Underline.SINGLE)
        self.highlight_tag.set_property('foreground-rgba', black)
        self.highlight_tag.set_property('background-rgba', yellow)

        self.found_tag = self.textview.get_buffer().create_tag("found")
        self.found_tag.set_property('foreground-rgba', black)
        self.found_tag.set_property('background-rgba', yellow)
        self.found_tag.set_property('weight', Pango.Weight.BOLD)

        # text to speech initialization
        self.current_word = 0
        self.word_tuples = []
        self.spoken_word_tag = self.textview.get_buffer().create_tag("spoken")
        self.spoken_word_tag.set_property('weight', Pango.Weight.BOLD)
        self.normal_tag = self.textview.get_buffer().create_tag("normal")
        self.normal_tag.set_property('weight', Pango.Weight.NORMAL)

    def load_document(self, file_path):

        file_name = file_path.replace('file://', '')
        mimetype = mime.get_for_file(file_path)
        if mimetype == 'application/zip':
            logging.debug('opening zip file')
            self.zf = zipfile.ZipFile(file_path.replace('file://', ''), 'r')
            self.book_files = self.zf.namelist()
            extract_path = os.path.join(self._activity.get_activity_root(),
                                        'instance')
            for book_file in self.book_files:
                if (book_file != 'annotations.pkl'):
                    self.zf.extract(book_file, extract_path)
                    file_name = os.path.join(extract_path, book_file)

        logging.debug('opening file_name %s' % file_name)
        self._etext_file = open(file_name, 'r')

        self.page_index = [0]
        pagecount = 0
        linecount = 0
        while self._etext_file:
            line = self._etext_file.readline()
            if not line:
                break
            line_increment = (len(line) // 80) + 1
            linecount = linecount + line_increment
            if linecount >= PAGE_SIZE:
                position = self._etext_file.tell()
                self.page_index.append(position)
                linecount = 0
                pagecount = pagecount + 1
        self._pagecount = pagecount + 1
        self.set_current_page(0)
        self._adjustment.configure(0.0, 0.0, self._pagecount - 1.0,
                                   1.0, 1.0, 0.0)

        # TODO: now that sugar4.speech has word signals
        # call self.highlight_next_word on each word
        # call self.reset_text_to_speech at end

    def _show_page(self, page_number):
        position = self.page_index[page_number]
        self._etext_file.seek(position)
        linecount = 0
        label_text = '\n\n\n'
        while linecount < PAGE_SIZE:
            line = self._etext_file.readline()
            if not line:
                break
            else:
                line = _clean_text(line)
                label_text = label_text + line
            line_increment = (len(line) // 80) + 1
            linecount = linecount + line_increment
        textbuffer = self.textview.get_buffer()
        label_text = label_text + '\n\n\n'
        textbuffer.set_text(label_text)
        self._prepare_text_to_speech(label_text)

    def _on_scroll(self, controller, dx, dy):
        adjustment = self._sw.get_vadjustment()
        scrollval = adjustment.get_value()
        scroll_upper = adjustment.props.upper - adjustment.props.page_size
        
        # dy > 0 means scrolling down
        if dy > 0 and scrollval >= scroll_upper - 1.0:
            if self._current_page < self._pagecount - 1:
                self.next_page()
                return True
        elif dy < 0 and scrollval <= 1.0:
            if self._current_page > 0:
                self.previous_page()
                return True
        return False

    def _scrollbar_change_value_cb(self, adjustment):
        """
        This is the fake scrollbar visible, used to show the length of the book
        """
        value = adjustment.get_value()
        old_page = self._current_page
        
        if value > old_page:
            self.__going_fwd = True
            self.__going_back = False
        elif value < old_page:
            self.__going_fwd = False
            self.__going_back = True

        if value > adjustment.props.upper:
            value = self._pagecount - 1
            
        new_page = int(value)
        if new_page != old_page:
            
            # Reset inner scroll position to the top of the new page
            v_adjustment = self._sw.get_vadjustment()
            v_adjustment.set_value(0.0)
            
            self._show_page(new_page)
            self._current_page = new_page
            self.emit('page-changed', old_page, self._current_page)

    def __touch_event_cb(self, gesture, n_press, x, y):
        device = gesture.get_current_event_device()
        if not device or device.get_source() != Gdk.InputSource.TOUCHSCREEN:
            return
            
        view_width = self.textview.get_width()
        if x > view_width * 3 / 4:
            self.scroll(Gtk.ScrollType.PAGE_FORWARD, False)
        elif x < view_width * 1 / 4:
            self.scroll(Gtk.ScrollType.PAGE_BACKWARD, False)

    def can_highlight(self):
        return True

    def get_selection_bounds(self):
        if self.textview.get_buffer().get_selection_bounds():
            begin, end = self.textview.get_buffer().get_selection_bounds()
            return [begin.get_offset(), end.get_offset()]
        else:
            return []

    def get_cursor_position(self):
        insert_mark = self.textview.get_buffer().get_insert()
        return self.textview.get_buffer().get_iter_at_mark(
            insert_mark).get_offset()

    def in_highlight(self):
        # Verify if the selection already exist or the cursor
        # is in a highlighted area
        tuples_list = self._activity._bookmarkmanager.get_highlights(
            self.get_current_page())

        selection_tuple = self.get_selection_bounds()
        in_bounds = False
        highlight_found = None
        for highlight_tuple in tuples_list:
            logging.debug('control tuple  %s' % str(highlight_tuple))
            if selection_tuple:
                if selection_tuple[0] >= highlight_tuple[0] and \
                   selection_tuple[1] <= highlight_tuple[1]:
                    in_bounds = True
                    highlight_found = highlight_tuple
                    break

        return in_bounds, highlight_found

    def show_highlights(self, page):
        tuples_list = self._activity._bookmarkmanager.get_highlights(page)
        textbuffer = self.textview.get_buffer()
        bounds = textbuffer.get_bounds()
        textbuffer.remove_all_tags(bounds[0], bounds[1])
        for highlight_tuple in tuples_list:
            iterStart = textbuffer.get_iter_at_offset(highlight_tuple[0])
            iterEnd = textbuffer.get_iter_at_offset(highlight_tuple[1])
            textbuffer.apply_tag(self.highlight_tag, iterStart, iterEnd)

    def toggle_highlight(self, highlight):
        found, old_highlight_found = self.in_highlight()

        if highlight:
            selection_tuple = self.get_selection_bounds()
            self._activity._bookmarkmanager.add_highlight(
                self.get_current_page(), selection_tuple)
        else:
            self._activity._bookmarkmanager.del_highlight(
                self.get_current_page(), old_highlight_found)

        self.show_highlights(self.get_current_page())

    def connect_page_changed_handler(self, handler):
        self.connect('page-changed', handler)

    def can_do_text_to_speech(self):
        return True

    def get_marked_words(self):
        "Adds a mark between each word of text."
        i = self.current_word
        marked_up_text = '<speak> '
        while i < len(self.word_tuples):
            word_tuple = self.word_tuples[i]
            marked_up_text = marked_up_text + \
                ' <mark name="' + str(i) + '"/>' + word_tuple[2]
            i = i + 1
        print(marked_up_text)
        return marked_up_text + '</speak>'

    def reset_text_to_speech(self):
        self.current_word = 0

    def _prepare_text_to_speech(self, page_text):
        i = 0
        j = 0
        word_begin = 0
        word_end = 0
        ignore_chars = [' ', '\n', '\r', '_', '[', '{', ']', '}', '|',
                        '<', '>', '*', '+', '/', '\\']
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
                if word_tuple[2] != '\r':
                    self.word_tuples.append(word_tuple)
            i = i + 1

    def highlight_next_word(self, word_count):
        if word_count < len(self.word_tuples):
            word_tuple = self.word_tuples[word_count]
            textbuffer = self.textview.get_buffer()
            iterStart = textbuffer.get_iter_at_offset(word_tuple[0])
            iterEnd = textbuffer.get_iter_at_offset(word_tuple[1])
            bounds = textbuffer.get_bounds()
            textbuffer.apply_tag(self.normal_tag, bounds[0], iterStart)
            textbuffer.apply_tag(self.spoken_word_tag, iterStart, iterEnd)
            v_adjustment = self._sw.get_vadjustment()
            max_pos = v_adjustment.get_upper() - v_adjustment.get_page_size()
            max_pos = max_pos * word_count
            max_pos = max_pos // len(self.word_tuples)
            v_adjustment.set_value(max_pos)
            self.current_word = word_count
        return True

    def update_metadata(self, activity):
        self.metadata = activity.metadata
        self.metadata['Read_zoom'] = str(self.get_zoom())

    def load_metadata(self, activity):
        self.metadata = activity.metadata
        if 'Read_zoom' in self.metadata:
            try:
                logging.debug('Loading zoom %s', self.metadata['Read_zoom'])
                self.set_zoom(float(self.metadata['Read_zoom']))
            except Exception:
                pass

    def set_current_page(self, page):
        old_page = self._current_page
        self._current_page = page
        self._show_page(self._current_page)
        self._adjustment.handler_block(self._scrollbar_change_value_cb_id)
        self._adjustment.set_value(self._current_page)
        self._adjustment.handler_unblock(self._scrollbar_change_value_cb_id)
        self.emit('page-changed', old_page, self._current_page)

    def scroll(self, scrolltype, horizontal):
        v_adjustment = self._sw.get_vadjustment()
        v_value = v_adjustment.get_value()
        if scrolltype in (Gtk.ScrollType.PAGE_BACKWARD,
                          Gtk.ScrollType.PAGE_FORWARD):
            step = v_adjustment.get_page_increment()
        else:
            step = v_adjustment.get_step_increment()

        if scrolltype in (Gtk.ScrollType.PAGE_BACKWARD,
                          Gtk.ScrollType.STEP_BACKWARD):
            self.__going_fwd = False
            self.__going_back = True
            if v_value <= v_adjustment.get_lower():
                self.previous_page()
                v_adjustment.set_value(v_adjustment.get_upper()
                                       - v_adjustment.get_page_size())
                return
            if v_value > v_adjustment.get_lower():
                new_value = v_value - step
                if new_value < v_adjustment.get_lower():
                    new_value = v_adjustment.get_lower()
                v_adjustment.set_value(new_value)
        elif scrolltype in (Gtk.ScrollType.PAGE_FORWARD,
                            Gtk.ScrollType.STEP_FORWARD):
            self.__going_fwd = True
            self.__going_back = False

            if v_value >= v_adjustment.get_upper() - \
                    v_adjustment.get_page_size():
                self.next_page()
                return
            if v_value < v_adjustment.get_upper() - \
                    v_adjustment.get_page_size():
                new_value = v_value + step
                if new_value > v_adjustment.get_upper() - \
                        v_adjustment.get_page_size():
                    new_value = v_adjustment.get_upper() - \
                        v_adjustment.get_page_size()
                v_adjustment.set_value(new_value)
        elif scrolltype == Gtk.ScrollType.START:
            self.set_current_page(0)
        elif scrolltype == Gtk.ScrollType.END:
            self.set_current_page(self._pagecount - 1)

    def previous_page(self):
        v_adjustment = self._sw.get_vadjustment()
        v_adjustment.set_value(v_adjustment.get_upper()
                               - v_adjustment.get_page_size())
        self.set_current_page(max(0, self.get_current_page() - 1))

    def next_page(self):
        v_adjustment = self._sw.get_vadjustment()
        v_adjustment.set_value(v_adjustment.get_lower())
        self.set_current_page(
            min(self._pagecount - 1, self.get_current_page() + 1))

    def get_current_page(self):
        return self._current_page

    def get_pagecount(self):
        return self._pagecount

    def update_toc(self, activity):
        pass

    def handle_link(self, link):
        pass

    def get_current_file(self):
        pass

    def get_current_link(self):
        return ""

    def get_link_iter(self, link):
        return None

    def copy(self):
        clipboard = self.textview.get_clipboard()
        self.textview.get_buffer().copy_clipboard(clipboard)

    def _view_selection_changed_cb(self, buffer, pspec=None):
        self._has_selection = buffer.get_has_selection()
        self.emit('selection-changed')

    def get_has_selection(self):
        return self._has_selection

    def find_set_highlight_search(self, boolean):
        pass

    def start_search(self, text, updated_cb=None):
        if text != self._search_text:
            self._search_text = text
            self._find_job = _JobFind(self._etext_file, start_page=0,
                                      n_pages=self._pagecount,
                                      text=text, case_sensitive=False)
        if updated_cb:
            self._find_updated_handler = self._find_job.connect(
                'updated', updated_cb)
        
        # Trigger highlighting when a match is found
        self._find_job.connect('updated', self.find_changed)
        
        return self._find_job

    def clear_search(self):
        if hasattr(self, '_find_job') and self._find_job:
            self._find_job.cancel()
            self._find_job = None

    def has_search_results(self):
        return hasattr(self, '_find_job') and self._find_job is not None

    def find_next(self):
        self._find_job.find_next()

    def find_previous(self):
        self._find_job.find_previous()

    def find_changed(self, job):
        self.set_current_page(job.get_page())
        self._show_found_text(job.get_founded_tuple())

    def _show_found_text(self, founded_tuple):
        if not founded_tuple:
            return
            
        textbuffer = self.textview.get_buffer()
        bounds = textbuffer.get_bounds()
        textbuffer.remove_tag(self.found_tag, bounds[0], bounds[1])
        
        iterStart = textbuffer.get_iter_at_offset(founded_tuple[1])
        iterEnd = textbuffer.get_iter_at_offset(founded_tuple[2])
        
        # Guaranteed-visible highlight, independent of focus/theme
        textbuffer.apply_tag(self.found_tag, iterStart, iterEnd)
        
        # Real selection too, so copy/bookmark still work off get_selection_bounds()
        textbuffer.select_range(iterStart, iterEnd)
        self.textview.grab_focus()
        
        # Ensure the found text is scrolled into view
        self.textview.scroll_to_iter(iterStart, 0.1, True, 0.5, 0.5)

    def get_zoom(self):
        return self.font_zoom_relation * self._font_size

    def connect_zoom_handler(self, handler):
        self._view_notify_zoom_handler = self.connect('zoom-changed',
                                                      handler)
        return self._view_notify_zoom_handler

    def set_zoom(self, value):
        self._zoom = value
        self._font_size = self._zoom // self.font_zoom_relation
        self._update_font()

    def zoom_in(self):
        self._set_font_size(self._font_size + 1)

    def zoom_out(self):
        self._set_font_size(self._font_size - 1)

    def _set_font_size(self, size):
        self._font_size = size
        self._update_font()
        self._zoom = self.font_zoom_relation * self._font_size
        self.emit('zoom-changed', self._zoom)

    def _update_font(self):
        fg = "white" if self._inverted else "black"
        bg = "black" if self._inverted else "white"
        css = f"""
        textview {{ 
            font-family: monospace; 
            font-size: {self._font_size}pt; 
            color: {fg};
            background-color: {bg}; 
            caret-color: transparent;
        }}
        textview text {{
            font-family: monospace; 
            font-size: {self._font_size}pt; 
            background-color: transparent; 
        }}
        textview selection, textview text selection {{
            background-color: yellow;
            color: black;
        }}
        """
        self._css_provider.load_from_data(css.encode('utf-8'))

    def set_inverted_colors(self, inverted):
        if self._inverted != inverted:
            self._inverted = inverted
            self._update_font()

    def zoom_to_width(self):
        pass

    def can_zoom_in(self):
        return True

    def can_zoom_out(self):
        return self._font_size > 1

    def can_zoom_to_width(self):
        return False

    def zoom_to_best_fit(self):
        return False

    def zoom_to_actual_size(self):
        return False

    def can_rotate(self):
        return False


class _JobFind(GObject.GObject):

    __gsignals__ = {
        'updated': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, ([])), }

    def __init__(self, text_file, start_page, n_pages, text,
                 case_sensitive=False):
        super().__init__()

        self._finished = False
        self._text_file = text_file
        self._start_page = start_page
        self._n_pages = n_pages
        self._text = text
        self._case_sensitive = case_sensitive
        self.threads = []

        s_thread = _SearchThread(self)
        self.threads.append(s_thread)
        s_thread.start()

    def cancel(self):
        '''
        Cancels the search job
        '''
        for s_thread in self.threads:
            s_thread.stop()

    def is_finished(self):
        '''
        Returns True if the entire search job has been finished
        '''
        return self._finished

    def get_search_text(self):
        '''
        Returns the search text
        '''
        return self._text

    def get_case_sensitive(self):
        '''
        Returns True if the search is case-sensitive
        '''
        return self._case_sensitive

    def find_next(self):
        self.threads[-1].find_next()

    def find_previous(self):
        self.threads[-1].find_previous()

    def get_page(self):
        return self.threads[-1].get_page()

    def get_founded_tuple(self):
        return self.threads[-1].get_founded_tuple()


class _SearchThread(threading.Thread):

    def __init__(self, obj):
        threading.Thread.__init__(self)
        self.obj = obj
        self.stopthread = threading.Event()

    def _start_search(self):
        pagecount = 0
        linecount = 0
        charcount = 0
        self._found_records = []
        self._current_found_item = -1
        self.obj._text_file.seek(0)
        while self.obj._text_file:
            line = self.obj._text_file.readline()
            line = _clean_text(line)
            line_length = len(line)
            if not line:
                break
            line_increment = (len(line) // 80) + 1
            linecount = linecount + line_increment
            positions = self._allindices(line.lower(), self.obj._text.lower())
            for position in positions:
                found_pos = charcount + position + 3
                found_tuple = (pagecount, found_pos,
                               len(self.obj._text) + found_pos)
                self._found_records.append(found_tuple)
                self._current_found_item = 0
            charcount = charcount + line_length
            if linecount >= PAGE_SIZE:
                linecount = 0
                charcount = 0
                pagecount = pagecount + 1
        if self._current_found_item == 0:
            self.current_found_tuple = \
                self._found_records[self._current_found_item]
            self._page = self.current_found_tuple[0]

        GLib.idle_add(self._emit_updated)
        return False

    def _emit_updated(self):
        self.obj._finished = True
        self.obj.emit('updated')
        return False

    def _allindices(self, line, search, listindex=None, offset=0):
        if listindex is None:
            listindex = []
        if (line.find(search) == -1):
            return listindex
        else:
            offset = line.index(search) + offset
            listindex.append(offset)
            line = line[(line.index(search) + 1):]
            return self._allindices(line, search, listindex, offset + 1)

    def run(self):
        self._start_search()

    def stop(self):
        self.stopthread.set()

    def find_next(self):
        if not self._found_records:
            return
        self._current_found_item = self._current_found_item + 1
        if self._current_found_item >= len(self._found_records):
            self._current_found_item = 0
        self.current_found_tuple =  \
            self._found_records[self._current_found_item]
        self._page = self.current_found_tuple[0]
        self.obj.emit('updated')

    def find_previous(self):
        if not self._found_records:
            return
        self._current_found_item = self._current_found_item - 1
        if self._current_found_item < 0:
            self._current_found_item = len(self._found_records) - 1
        self.current_found_tuple = \
            self._found_records[self._current_found_item]
        self._page = self.current_found_tuple[0]
        self.obj.emit('updated')

    def get_page(self):
        return self._page

    def get_founded_tuple(self):
        return self.current_found_tuple
