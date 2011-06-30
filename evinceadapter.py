import gobject
import logging
import gtk

import evince

_logger = logging.getLogger('read-activity')


class EvinceViewer():

    def __init__(self):
        self._view_notify_zoom_handler = None
        self._view = evince.View()

    def setup(self, activity):
        self._activity = activity
        self._view.connect('selection-changed',
                            activity._view_selection_changed_cb)

        activity._scrolled = gtk.ScrolledWindow()
        activity._scrolled.set_policy(gtk.POLICY_AUTOMATIC,
                gtk.POLICY_AUTOMATIC)
        activity._scrolled.props.shadow_type = gtk.SHADOW_NONE

        activity._scrolled.add(self._view)
        self._view.show()

        activity._hbox.pack_start(activity._scrolled, expand=True, fill=True)
        activity._scrolled.show()

        self.dpi = activity.dpi

    def load_document(self, file_path):
        try:
            self._document = evince.document_factory_get_document(file_path)
        except gobject.GError, e:
            _logger.error('Can not load document: %s', e)
            return
        else:
            self._model = evince.DocumentModel()
            self._model.set_document(self._document)
            self._view.set_model(self._model)

            # set dpi
            min_scale = self._model.get_min_scale()
            max_scale = self._model.get_max_scale()
            self._model.set_min_scale(min_scale * self.dpi / 72.0)
            self._model.set_max_scale(max_scale * self.dpi / 72.0)

    def get_current_page(self):
        return self._model.props.page

    def set_current_page(self, page):
        if page >= self._document.get_n_pages():
            page = self._document.get_n_pages() - 1
        elif page < 0:
            page = 0
        self._model.props.page = page

    def get_pagecount(self):
        '''
        Returns the pagecount of the loaded file
        '''
        return self._document.get_n_pages()

    def load_metadata(self, activity):

        self.metadata = activity.metadata

        if not self.metadata['title_set_by_user'] == '1':
            title = self._document.get_title()
            if title:
                self.metadata['title'] = title

        sizing_mode = self.metadata.get('Read_sizing_mode', 'fit-width')
        _logger.debug('Found sizing mode: %s', sizing_mode)
        if sizing_mode == "best-fit":
            self._model.props.sizing_mode = evince.SIZING_BEST_FIT
            if hasattr(self._view, 'update_view_size'):
                self._view.update_view_size(self._scrolled)
        elif sizing_mode == "free":
            self._model.props.sizing_mode = evince.SIZING_FREE
            self._model.props.scale = \
                    float(self.metadata.get('Read_zoom', '1.0'))
            _logger.debug('Set zoom to %f', self._model.props.scale)
        elif sizing_mode == "fit-width":
            self._model.props.sizing_mode = evince.SIZING_FIT_WIDTH
            if hasattr(self._view, 'update_view_size'):
                self._view.update_view_size(self._scrolled)
        else:
            # this may happen when we get a document from a buddy with a later
            # version of Read, for example.
            _logger.warning("Unknown sizing_mode state '%s'", sizing_mode)
            if self.metadata.get('Read_zoom', None) is not None:
                self._model.props.scale = float(self.metadata['Read_zoom'])

    def update_metadata(self, activity):
        self.metadata = activity.metadata
        self.metadata['Read_zoom'] = str(self._model.props.scale)

        if self._model.props.sizing_mode == evince.SIZING_BEST_FIT:
            self.metadata['Read_sizing_mode'] = "best-fit"
        elif self._model.props.sizing_mode == evince.SIZING_FREE:
            self.metadata['Read_sizing_mode'] = "free"
        elif self._model.props.sizing_mode == evince.SIZING_FIT_WIDTH:
            self.metadata['Read_sizing_mode'] = "fit-width"
        else:
            _logger.error("Don't know how to save sizing_mode state '%s'" %
                          self._model.props.sizing_mode)
        self.metadata['Read_sizing_mode'] = "fit-width"

    def can_highlight(self):
        return False

    def can_do_text_to_speech(self):
        return False

    def get_zoom(self):
        '''
        Returns the current zoom level
        '''
        return self._model.props.scale * 100

    def set_zoom(self, value):
        '''
        Sets the current zoom level
        '''
        self._model.props.sizing_mode = evince.SIZING_FREE

        if not self._view_notify_zoom_handler:
            return

        self._model.disconnect(self._view_notify_zoom_handler)
        try:
            self._model.props.scale = value / 100.0
        finally:
            self._view_notify_zoom_handler = self._model.connect(
                'notify::scale', self._zoom_handler)

    def zoom_in(self):
        '''
        Zooms in (increases zoom level by 0.1)
        '''
        self._model.props.sizing_mode = evince.SIZING_FREE
        self._view.zoom_in()

    def zoom_out(self):
        '''
        Zooms out (decreases zoom level by 0.1)
        '''
        self._model.props.sizing_mode = evince.SIZING_FREE
        self._view.zoom_out()

    def zoom_to_width(self):
        self._model.props.sizing_mode = evince.SIZING_FIT_WIDTH

    def can_zoom_in(self):
        '''
        Returns True if it is possible to zoom in further
        '''
        return self._view.can_zoom_in()

    def can_zoom_out(self):
        '''
        Returns True if it is possible to zoom out further
        '''
        return self._view.can_zoom_out()

    def can_zoom_to_width(self):
        return True

    def zoom_to_best_fit(self):
        self._model.props.sizing_mode = evince.SIZING_BEST_FIT

    def zoom_to_actual_size(self):
        self._model.props.sizing_mode = evince.SIZING_FREE
        self._model.props.scale = 1.0

    def connect_zoom_handler(self, handler):
        self._zoom_handler = handler
        self._view_notify_zoom_handler = \
                self._model.connect('notify::scale', handler)
        return self._view_notify_zoom_handler

    def setup_find_job(self, text, updated_cb):
        self._find_job = evince.JobFind(document=self._document, start_page=0,
                n_pages=self._document.get_n_pages(),
                text=text, case_sensitive=False)
        self._find_updated_handler = self._find_job.connect('updated',
                updated_cb)
        evince.Job.scheduler_push_job(self._find_job,
                evince.JOB_PRIORITY_NONE)
        return self._find_job, self._find_updated_handler

    def connect_page_changed_handler(self, handler):
        self._model.connect('page-changed', handler)

    def update_toc(self, activity):
        return False

    def find_set_highlight_search(self, set_highlight_search):
        self._view.find_set_highlight_search(set_highlight_search)

    def find_next(self):
        '''
        Highlights the next matching item for current search
        '''
        self._view.find_next()

    def find_previous(self):
        '''
        Highlights the previous matching item for current search
        '''
        self._view.find_previous()

    def find_changed(self, job, page=None):
        self._view.find_changed(job, page)

    def scroll(self, scrolltype, horizontal):
        '''
        Scrolls through the pages.
        Scrolling is horizontal if horizontal is set to True
        Valid scrolltypes are:
        gtk.SCROLL_PAGE_BACKWARD, gtk.SCROLL_PAGE_FORWARD,
        gtk.SCROLL_STEP_BACKWARD, gtk.SCROLL_STEP_FORWARD,
        gtk.SCROLL_START and gtk.SCROLL_END
        '''
        _logger.error('scroll: %s', scrolltype)

        if scrolltype == gtk.SCROLL_PAGE_BACKWARD:
            self._view.scroll(gtk.SCROLL_PAGE_BACKWARD, horizontal)
        elif scrolltype == gtk.SCROLL_PAGE_FORWARD:
            self._view.scroll(gtk.SCROLL_PAGE_FORWARD, horizontal)
        elif scrolltype == gtk.SCROLL_STEP_BACKWARD:
            self._scroll_step(False, horizontal)
        elif scrolltype == gtk.SCROLL_STEP_FORWARD:
            self._scroll_step(True, horizontal)
        elif scrolltype == gtk.SCROLL_START:
            self.set_current_page(0)
        elif scrolltype == gtk.SCROLL_END:
            self.set_current_page(self._document.get_n_pages())
        else:
            print ('Got unsupported scrolltype %s' % str(scrolltype))

    def _scroll_step(self, forward, horizontal):
        if horizontal:
            adj = self._activity._scrolled.get_hadjustment()
        else:
            adj = self._activity._scrolled.get_vadjustment()
        value = adj.get_value()
        step = adj.get_step_increment()
        if forward:
            adj.set_value(value + step)
        else:
            adj.set_value(value - step)

    def copy(self):
        self._view.copy()
