import gobject
import logging

import os, sys

sys.path.append(os.path.join(os.environ['SUGAR_BUNDLE_PATH'], 'epubview'))
import epubview

_logger = logging.getLogger('read-activity')

class View(epubview.EpubView):
    def __init__(self):
        epubview.EpubView.__init__(self)

    def _try_load_page(self, n):
        if self._ready:
            self._load_page(n)
            return False
        else:
            return True

    def set_screen_dpi(self, dpi):
        return

    def find_set_highlight_search(self, set_highlight_search):
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

    def find_changed(self, job, page = None):
        self._find_changed(job)

    def handle_link(self, link):
        self._load_file(link)


class EpubDocument(epubview.Epub):
    def __init__(self, view, docpath):
        epubview.Epub.__init__(self, docpath)
        self._page_cache = view

    def get_page_cache(self):
        return self._page_cache

    def get_n_pages(self):
        return int(self._page_cache.get_pagecount())

    def has_document_links(self):
        return True

    def get_links_model(self):
        return self.get_toc_model()

class JobFind(epubview.JobFind):
    def __init__(self, document, start_page, n_pages, text, case_sensitive=False):
        epubview.JobFind.__init__(self, document, start_page, n_pages, text, case_sensitive=False)
