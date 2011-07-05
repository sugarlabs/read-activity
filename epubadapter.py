import gobject
import logging

import epubview
import speech

from cStringIO import StringIO

_logger = logging.getLogger('read-activity')


class EpubViewer(epubview.EpubView):

    def __init__(self):
        epubview.EpubView.__init__(self)

    def setup(self, activity):
        self.set_screen_dpi(activity.dpi)
        self.connect('selection-changed',
                            activity._view_selection_changed_cb)

        activity._hbox.pack_start(self, expand=True, fill=True)
        self.show_all()
        # text to speech initialization
        self.current_word = 0
        self.word_tuples = []

    def load_document(self, file_path):
        self.set_document(EpubDocument(self, file_path.replace('file://', '')))
        speech.highlight_cb = self.highlight_next_word
        speech.end_text_cb = self.get_more_text

    def load_metadata(self, activity):

        self.metadata = activity.metadata

        if not self.metadata['title_set_by_user'] == '1':
            title = self._epub._info._get_title()
            if title:
                self.metadata['title'] = title

    def update_metadata(self, activity):
        pass

    def zoom_to_width(self):
        pass

    def zoom_to_best_fit(self):
        pass

    def zoom_to_actual_size(self):
        pass

    def can_zoom_to_width(self):
        return False

    def can_highlight(self):
        return False

    def can_do_text_to_speech(self):
        return True

    def get_marked_words(self):
        "Adds a mark between each word of text."
        i = self.current_word
        file_str = StringIO()
        file_str.write('<speak> ')
        end_range = i + 40
        if end_range > len(self.word_tuples):
            end_range = len(self.word_tuples)
        for word_tuple in self.word_tuples[self.current_word:end_range]:
            file_str.write('<mark name="' + str(i) + '"/>' + word_tuple[2])
            i = i + 1
        self.current_word = i
        file_str.write('</speak>')
        return file_str.getvalue()

    def get_more_text(self):
        if self.current_word < len(self.word_tuples):
            speech.stop()
            more_text = self.get_marked_words()
            speech.play(more_text)

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
        #TODO : what is this?
        return

    def set_current_page(self, n):
        # When the book is being loaded, calling this does not help
        # In such a situation, we go into a loop and try to load the
        # supplied page when the book has loaded completely
        n += 1
        if self._ready:
            self._load_page(n)
        else:
            gobject.timeout_add(200, self._try_load_page, n)

    def get_current_page(self):
        return int(self._loaded_page - 1)

    def update_toc(self, activity):
        if self._epub.has_document_links():
            activity._navigator_toolbar_button.show()
            activity._navigator.show_all()

            activity._toc_model = self._epub.get_links_model()
            activity._navigator.set_model(activity._toc_model)
            activity._navigator.set_active(0)
            return True
        else:
            return False

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
