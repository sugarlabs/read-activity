from gi.repository import GObject
import logging

import epubview

# import speech

from cStringIO import StringIO

_logger = logging.getLogger('read-activity')


class EpubViewer(epubview.EpubView):

    def __init__(self):
        epubview.EpubView.__init__(self)

    def setup(self, activity):
        self.set_screen_dpi(activity.dpi)
        self.connect('selection-changed',
                     activity._view_selection_changed_cb)

        activity._hbox.pack_start(self, True, True, 0)
        self.show_all()
        self._modified_files = []

        # text to speech initialization
        self.current_word = 0
        self.word_tuples = []

    def load_document(self, file_path):
        self.set_document(EpubDocument(self, file_path.replace('file://', '')))
        # speech.highlight_cb = self.highlight_next_word
        # speech.reset_cb = self.reset_text_to_speech
        # speech.end_text_cb = self.get_more_text

    def load_metadata(self, activity):

        self.metadata = activity.metadata

        if not self.metadata['title_set_by_user'] == '1':
            title = self._epub._info._get_title()
            if title:
                self.metadata['title'] = title
        if 'Read_zoom' in self.metadata:
            try:
                logging.error('Loading zoom %s', self.metadata['Read_zoom'])
                self.set_zoom(float(self.metadata['Read_zoom']))
            except:
                pass

    def update_metadata(self, activity):
        self.metadata = activity.metadata
        logging.error('Saving zoom %s', self.get_zoom())
        self.metadata['Read_zoom'] = self.get_zoom()

    def zoom_to_width(self):
        pass

    def zoom_to_best_fit(self):
        pass

    def zoom_to_actual_size(self):
        pass

    def can_zoom_to_width(self):
        return False

    def can_highlight(self):
        return True

    def show_highlights(self, page):
        # we save the highlights in the page as html
        pass

    def toggle_highlight(self, highlight):
        self._view.set_editable(True)

        if highlight:
            self._view.execute_script(
                'document.execCommand("backColor", false, "yellow");')
        else:
            # need remove the highlight nodes
            js = """
                var selObj = window.getSelection();
                var range  = selObj.getRangeAt(0);
                var node = range.startContainer;
                while (node.parentNode != null) {
                  if (node.localName == "span") {
                    if (node.hasAttributes()) {
                      var attrs = node.attributes;
                      for(var i = attrs.length - 1; i >= 0; i--) {
                        if (attrs[i].name == "style" &&
                            attrs[i].value == "background-color: yellow;") {
                          node.removeAttribute("style");
                          break;
                        };
                      };
                    };
                  };
                  node = node.parentNode;
                };"""
            self._view.execute_script(js)

        self._view.set_editable(False)
        # mark the file as modified
        current_file = self.get_current_file()
        logging.error('file %s was modified', current_file)
        if current_file not in self._modified_files:
            self._modified_files.append(current_file)
        GObject.idle_add(self._save_page)

    def _save_page(self):
        oldtitle = self._view.get_title()
        self._view.execute_script(
            "document.title=document.documentElement.innerHTML;")
        html = self._view.get_title()
        file_path = self.get_current_file().replace('file:///', '/')
        logging.error(html)
        with open(file_path, 'w') as fd:
            header = """<?xml version="1.0" encoding="utf-8" standalone="no"?>
                <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"
                 "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
                <html xmlns="http://www.w3.org/1999/xhtml">"""
            fd.write(header)
            fd.write(html)
            fd.write('</html>')
        self._view.execute_script('document.title=%s;' % oldtitle)

    def save(self, file_path):
        if self._modified_files:
            self._epub.write(file_path)
            return True

        return False

    def in_highlight(self):
        # Verify if the selection already exist or the cursor
        # is in a highlighted area
        page_title = self._view.get_title()
        js = """
            var selObj = window.getSelection();
            var range  = selObj.getRangeAt(0);
            var node = range.startContainer;
            var onHighlight = false;
            while (node.parentNode != null) {
              if (node.localName == "span") {
                if (node.hasAttributes()) {
                  var attrs = node.attributes;
                  for(var i = attrs.length - 1; i >= 0; i--) {
                    if (attrs[i].name == "style" &&
                        attrs[i].value == "background-color: yellow;") {
                      onHighlight = true;
                    };
                  };
                };
              };
              node = node.parentNode;
            };
            document.title=onHighlight;"""
        self._view.execute_script(js)
        on_highlight = self._view.get_title() == 'true'
        self._view.execute_script('document.title = "%s";' % page_title)
        # the second parameter is only used in the text backend
        return on_highlight, None

    def can_do_text_to_speech(self):
        return False

    def can_rotate(self):
        return False

    def get_marked_words(self):
        "Adds a mark between each word of text."
        i = self.current_word
        file_str = StringIO()
        file_str.write('<speak> ')
        end_range = i + 40
        if end_range > len(self.word_tuples):
            end_range = len(self.word_tuples)
        for word_tuple in self.word_tuples[self.current_word:end_range]:
            file_str.write('<mark name="' + str(i) + '"/>' +
                           word_tuple[2].encode('utf-8'))
            i = i + 1
        self.current_word = i
        file_str.write('</speak>')
        return file_str.getvalue()

    def get_more_text(self):
        pass
        """
        if self.current_word < len(self.word_tuples):
            speech.stop()
            more_text = self.get_marked_words()
            speech.play(more_text)
        else:
            if speech.reset_buttons_cb is not None:
                speech.reset_buttons_cb()
        """

    def reset_text_to_speech(self):
        self.current_word = 0

    def highlight_next_word(self,  word_count):
        pass
        """
        TODO: disabled because javascript can't be executed
        with the velocity needed
        self.current_word = word_count
        self._view.highlight_next_word()
        return True
        """

    def connect_zoom_handler(self, handler):
        self._zoom_handler = handler
        self._view_notify_zoom_handler = \
            self.connect('notify::scale', handler)
        return self._view_notify_zoom_handler

    def connect_page_changed_handler(self, handler):
        self.connect('page-changed', handler)

    def _try_load_page(self, n):
        if self._ready:
            self._load_page(n)
            return False
        else:
            return True

    def set_screen_dpi(self, dpi):
        return

    def find_set_highlight_search(self, set_highlight_search):
        self._view.set_highlight_text_matches(set_highlight_search)

    def set_current_page(self, n):
        # When the book is being loaded, calling this does not help
        # In such a situation, we go into a loop and try to load the
        # supplied page when the book has loaded completely
        n += 1
        if self._ready:
            self._load_page(n)
        else:
            GObject.timeout_add(200, self._try_load_page, n)

    def get_current_page(self):
        return int(self._loaded_page) - 1

    def get_current_link(self):
        # the _loaded_filename include all the path,
        # need only the part included in the link
        return self._loaded_filename[len(self._epub._tempdir) + 1:]

    def update_toc(self, activity):
        if self._epub.has_document_links():
            activity.show_navigator_button()
            activity.set_navigator_model(self._epub.get_links_model())
            return True
        else:
            return False

    def get_link_iter(self, current_link):
        """
        Returns the iter related to a link
        """
        link_iter = self._epub.get_links_model().get_iter_first()

        while link_iter is not None and \
                self._epub.get_links_model().get_value(link_iter, 1) \
                != current_link:
            link_iter = self._epub.get_links_model().iter_next(link_iter)
        return link_iter

    def find_changed(self, job, page=None):
        self._find_changed(job)

    def handle_link(self, link):
        self._load_file(link)

    def setup_find_job(self, text, updated_cb):
        self._find_job = JobFind(document=self._epub,
                                 start_page=0, n_pages=self.get_pagecount(),
                                 text=text, case_sensitive=False)
        self._find_updated_handler = self._find_job.connect('updated',
                                                            updated_cb)
        return self._find_job, self._find_updated_handler


class EpubDocument(epubview.Epub):

    def __init__(self, view, docpath):
        epubview.Epub.__init__(self, docpath)
        self._page_cache = view

    def get_n_pages(self):
        return int(self._page_cache.get_pagecount())

    def has_document_links(self):
        return True

    def get_links_model(self):
        return self.get_toc_model()


class JobFind(epubview.JobFind):

    def __init__(self, document, start_page, n_pages, text,
                 case_sensitive=False):
        epubview.JobFind.__init__(self, document, start_page, n_pages, text,
                                  case_sensitive=False)
