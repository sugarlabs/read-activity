from gettext import gettext as _
import os
import logging
import time

import gi
gi.require_version('PapersDocument', '4.0')
gi.require_version('PapersView', '4.0')

from gi.repository import GObject
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Gdk

from gi.repository import PapersDocument
from gi.repository import PapersView

from sugar4 import profile
from sugar4.activity.activity import get_activity_root, show_object_in_journal
from sugar4.datastore import datastore

_logger = logging.getLogger('read-activity')


class PapersViewer():

    def __init__(self):
        self._view_notify_zoom_handler = None
        PapersDocument.init()
        self._document = None
        self._model = PapersView.DocumentModel()
        
        if hasattr(PapersView, 'SearchContext'):
            self._search_context = PapersView.SearchContext.new(self._model)
        else:
            self._search_context = None

        self._view = PapersView.View()
        
        if self._search_context:
            self._view.set_search_context(self._search_context)
            
        self._view.set_model(self._model)
        self._view.set_caret_navigation_enabled(False)

    def setup(self, activity):
        self._activity = activity
        self._view.connect('selection-changed',
                           activity._view_selection_changed_cb)
        self._view.connect('external-link', self.__handle_link_cb)

        activity._scrolled = Gtk.ScrolledWindow()
        activity._scrolled.set_policy(Gtk.PolicyType.AUTOMATIC,
                                      Gtk.PolicyType.AUTOMATIC)
        activity._scrolled.set_kinetic_scrolling(False)
        activity._scrolled.set_overflow(Gtk.Overflow.HIDDEN)

        activity._scrolled.set_child(self._view)
        self._view.set_overflow(Gtk.Overflow.HIDDEN)
        self._view.show()

        # WORKAROUND: PapersView fails to properly reset
        # its internal gesture states when a touch drag is claimed by the parent 
        # ScrolledWindow. This leaves an active pointer grab and a stuck cursor.
        # We add a dummy gesture to detect when the sequence is cancelled by the 
        # ScrolledWindow, and manually force all internal controllers to reset.
        self._grab_breaker = Gtk.GestureDrag.new()
        def _on_sequence_cancelled(gesture, sequence):
            if sequence is None:
                # Ignore pointer/mouse events. We only want to reset on touch sequences.
                # If a mouse drag cancels this gesture, it's likely because PapersView
                # successfully claimed it for text selection.
                return

            # 1. Fix the cosmetic issue (stuck I-beam cursor)
            self._view.set_cursor(None)
            
            # 2. Fix the functional issue (unreleased implicit grab)
            # Force reset all internal controllers on PapersView
            controllers = self._view.observe_controllers()
            for i in range(controllers.get_n_items()):
                c = controllers.get_item(i)
                if c != gesture and isinstance(c, (Gtk.GestureClick, Gtk.GestureDrag)) and hasattr(c, 'reset'):
                    c.reset()
        
        self._grab_breaker.connect('cancel', _on_sequence_cancelled)
        self._view.add_controller(self._grab_breaker)

        try:
            if hasattr(PapersView, 'UndoContext') and hasattr(PapersView, 'AnnotationsContext'):
                undo = PapersView.UndoContext.new(self._model)
                annot = PapersView.AnnotationsContext.new(self._model, undo)
                self._view.set_annotations_context(annot)
        except Exception as e:
            _logger.error("Failed to set annotations context: %s", e)

        self._click_gesture = Gtk.GestureClick.new()
        self._click_gesture.set_touch_only(True)
        self._click_gesture.set_propagation_phase(Gtk.PropagationPhase.BUBBLE)
        self._click_gesture.connect('pressed', self.__view_touch_event_cb)
        self._view.add_controller(self._click_gesture)

        activity._scrolled.set_hexpand(True)
        activity._scrolled.set_vexpand(True)
        activity._hbox.append(activity._scrolled)
        activity._scrolled.show()

        self.dpi = activity.dpi

    def load_document(self, file_path):
        if file_path.startswith('file://'):
            uri = file_path
        else:
            from gi.repository import Gio
            uri = Gio.File.new_for_path(file_path).get_uri()
        try:
            self._document = \
                PapersDocument.Document.factory_get_document(uri)
            if not self._document.load(uri):
                _logger.error('Document.load() returned False for %s', uri)
                self._document = None
                return
        except GLib.Error as e:
            _logger.error('Can not load document backend: %s', e)
            self._document = None
            return
        
        self._document.setup_cache()
        self._model.set_document(self._document)

        # set dpi
        # TODO why we need set this?
        """
        min_scale = self._model.get_min_scale()
        max_scale = self._model.get_max_scale()
        logging.error("min scale %s max_scale %s", min_scale, max_scale)
        logging.error("setting min scale %s", min_scale * self.dpi / 72.0)
        logging.error("setting max scale %s", max_scale * self.dpi / 72.0)
        self._model.set_min_scale(min_scale * self.dpi / 72.0)
        self._model.set_max_scale(max_scale * self.dpi / 72.0)
        """

    def __view_touch_event_cb(self, gesture, n_press, x, y):
        view_width = self._view.get_width()
        if x > view_width * 3 / 4:
            self.next_page()
        elif x < view_width * 1 / 4:
            self.previous_page()

    def __handle_link_cb(self, widget, url_object):
        url = url_object.get_uri()
        logging.debug('Create journal entry for URL: %s', url)
        jobject = datastore.create()
        metadata = {
            'title': "%s: %s" % (_('URL from Read'), url),
            'title_set_by_user': '1',
            'icon-color': profile.get_color().to_string(),
            'mime_type': 'text/uri-list', }

        for k, v in list(metadata.items()):
            jobject.metadata[k] = v
        file_path = os.path.join(get_activity_root(),
                                 'instance', '%i_' % time.time())
        open(file_path, 'w').write(url + '\r\n')
        os.chmod(file_path, 0o755)
        jobject.set_file_path(file_path)
        datastore.write(jobject)
        show_object_in_journal(jobject.object_id)
        jobject.destroy()
        os.unlink(file_path)

    def get_current_page(self):
        return max(0, self._model.props.page)

    def set_current_page(self, page):
        if page < 0 or page >= self._document.get_n_pages():
            return
        self._model.props.page = page

    def next_page(self):
        if hasattr(self._view, 'next_page'):
            self._view.next_page()
        else:
            self.set_current_page(self.get_current_page() + 1)

    def previous_page(self):
        if hasattr(self._view, 'previous_page'):
            self._view.previous_page()
        else:
            self.set_current_page(self.get_current_page() - 1)

    def rotate_left(self):
        rotation = self._model.get_rotation()
        self._model.set_rotation(rotation - 90)

    def rotate_right(self):
        rotation = self._model.get_rotation()
        self._model.set_rotation(rotation + 90)

    def can_rotate(self):
        return True

    def get_pagecount(self):
        '''
        Returns the pagecount of the loaded file
        '''
        return self._document.get_n_pages()

    def load_metadata(self, activity):
        if not self._document:
            return

        self.metadata = activity.metadata

        if not self.metadata['title_set_by_user'] == '1':
            title = self._document.get_title()
            if title:
                self.metadata['title'] = title

        sizing_mode = self.metadata.get('Read_sizing_mode', 'fit-width')
        _logger.debug('Found sizing mode: %s', sizing_mode)
        if sizing_mode == "best-fit":
            self._model.set_sizing_mode(PapersView.SizingMode.FIT_PAGE)
        elif sizing_mode == "free":
            self._model.set_sizing_mode(PapersView.SizingMode.FREE)
            self._model.set_scale(float(self.metadata.get('Read_zoom', '1.0')))
            _logger.debug('Set zoom to %f', self._model.props.scale)
        elif sizing_mode == "fit-width":
            self._model.set_sizing_mode(PapersView.SizingMode.FIT_WIDTH)
        else:
            # this may happen when we get a document from a buddy with a later
            # version of Read, for example.
            _logger.warning("Unknown sizing_mode state '%s'", sizing_mode)
            if self.metadata.get('Read_zoom', None) is not None:
                self._model.set_scale(float(self.metadata['Read_zoom']))

    def update_metadata(self, activity):
        self.metadata = activity.metadata
        self.metadata['Read_zoom'] = str(self._model.props.scale)

        if self._model.get_sizing_mode() == PapersView.SizingMode.FIT_PAGE:
            self.metadata['Read_sizing_mode'] = "best-fit"
        elif self._model.get_sizing_mode() == PapersView.SizingMode.FREE:
            self.metadata['Read_sizing_mode'] = "free"
        elif self._model.get_sizing_mode() == PapersView.SizingMode.FIT_WIDTH:
            self.metadata['Read_sizing_mode'] = "fit-width"
        else:
            _logger.error("Don't know how to save sizing_mode state '%s'" %
                          self._model.get_sizing_mode())

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
        self._model.props.sizing_mode = PapersView.SizingMode.FREE

        if not self._view_notify_zoom_handler:
            self._model.props.scale = value / 100.0
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
        self._model.props.sizing_mode = PapersView.SizingMode.FREE
        self._view.zoom_in()

    def zoom_out(self):
        '''
        Zooms out (decreases zoom level by 0.1)
        '''
        self._model.props.sizing_mode = PapersView.SizingMode.FREE
        self._view.zoom_out()

    def zoom_to_width(self):
        self._model.props.sizing_mode = PapersView.SizingMode.FIT_WIDTH

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
        self._model.props.sizing_mode = PapersView.SizingMode.FIT_PAGE

    def zoom_to_actual_size(self):
        self._model.props.sizing_mode = PapersView.SizingMode.FREE
        self._model.props.scale = 1.0

    def connect_zoom_handler(self, handler):
        self._zoom_handler = handler
        self._view_notify_zoom_handler = \
            self._model.connect('notify::scale', handler)
        return self._view_notify_zoom_handler

    def start_search(self, text, updated_cb=None):
        if not self._search_context:
            return
        if getattr(self, '_search_finished_handler', None):
            self._search_context.disconnect(self._search_finished_handler)
            self._search_finished_handler = None
        def _on_finished(context, first_match_page):
            sel = context.get_result_model()
            if sel and sel.get_n_items() > 0 and \
                    sel.get_selected() == Gtk.INVALID_LIST_POSITION:
                sel.set_selected(0)          # <-- makes the view jump to the first match
            if updated_cb:
                updated_cb(context, first_match_page)
        self._search_finished_handler = \
            self._search_context.connect('finished', _on_finished)
        self._search_context.set_search_term(text)
        
        if not self._search_context.get_active():   # avoid use-count inflation
            self._search_context.activate()

    def clear_search(self):
        if not self._search_context:
            return
        self._search_context.set_search_term("")
        if self._search_context.get_active():
            self._search_context.release()

    def find_next(self):
        if not self._search_context:
            return
        sel = self._search_context.get_result_model()
        if not sel or sel.get_n_items() == 0:
            return
        pos = sel.get_selected()
        if pos == Gtk.INVALID_LIST_POSITION:
            sel.set_selected(0)
        elif pos < sel.get_n_items() - 1:
            sel.set_selected(pos + 1)
        else:
            sel.set_selected(0)
        # no activate() here

    def find_previous(self):
        if not self._search_context:
            return
        sel = self._search_context.get_result_model()
        if not sel or sel.get_n_items() == 0:
            return
        pos = sel.get_selected()
        if pos == Gtk.INVALID_LIST_POSITION:
            sel.set_selected(0)
        elif pos != 0:
            sel.set_selected(pos - 1)
        else:
            sel.set_selected(sel.get_n_items() - 1)
        # no activate() here

    def has_search_results(self):
        if not self._search_context:
            return False
        sel = self._search_context.get_result_model()
        return bool(sel and sel.get_n_items() > 0)

    def connect_page_changed_handler(self, handler):
        self._model.connect('page-changed', handler)

    def update_toc(self, activity):
        # TODO: TOC loading disabled for now. Papers 4.0 changed the TOC
        # model from GtkTreeModel to GListModel, and calling
        # has_document_links() causes a segfault in poppler_index_iter_new.
        # This needs a full rewrite using the new Papers TOC API.
        _logger.warning('TOC loading is currently disabled (Papers 4.0 GListModel migration required)')
        return False

    def handle_link(self, link):
        self._view.handle_link(link)

    def get_current_link(self):
        if not hasattr(self, '_index_model') or self._index_model is None:
            return None
        _iter = self._index_model.get_iter_first()
        link_found = ""
        current_page = self._model.props.page
        while True:
            link = self._index_model.get_value(_iter, 1)
            if self._document.get_link_page(link) > current_page:
                break
            else:
                link_found = link
                _iter = self._index_model.iter_next(_iter)
                if _iter is None:
                    break
        return link_found

    def get_link_iter(self, link):
        if not hasattr(self, '_index_model') or self._index_model is None:
            return None
        _iter = self._index_model.get_iter_first()
        while True:
            value = self._index_model.get_value(_iter, 1)
            if value == link:
                break
            else:
                _iter = self._index_model.iter_next(_iter)
                if _iter is None:
                    break
        return _iter

    def scroll(self, scrolltype, horizontal):
        '''
        Scrolls through the pages.
        Scrolling is horizontal if horizontal is set to True
        Valid scrolltypes are:
        Gtk.ScrollType.PAGE_BACKWARD, Gtk.ScrollType.PAGE_FORWARD,
        Gtk.ScrollType.STEP_BACKWARD, Gtk.ScrollType.STEP_FORWARD,
        Gtk.ScrollType.START and Gtk.ScrollType.END
        '''
        _logger.debug('scroll: %s', scrolltype)

        if scrolltype == Gtk.ScrollType.PAGE_BACKWARD:
            self.previous_page()
        elif scrolltype == Gtk.ScrollType.PAGE_FORWARD:
            self.next_page()
        elif scrolltype == Gtk.ScrollType.STEP_BACKWARD:
            self._scroll_step(False, horizontal)
        elif scrolltype == Gtk.ScrollType.STEP_FORWARD:
            self._scroll_step(True, horizontal)
        elif scrolltype == Gtk.ScrollType.START:
            self.set_current_page(0)
        elif scrolltype == Gtk.ScrollType.END:
            self.set_current_page(self._document.get_n_pages())
        else:
            print('Got unsupported scrolltype %s' % str(scrolltype))

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
        if hasattr(self._view, 'get_selected_text'):
            text = self._view.get_selected_text()
            if text:
                clipboard = self._view.get_clipboard()
                
                try:
                    clipboard.set(text)
                except TypeError:
                    try:
                        clipboard.set(str, text)
                    except Exception:
                        pass
                except AttributeError:
                    try:
                        clipboard.set_text(text)
                    except Exception:
                        pass
                
                try:
                    primary = self._view.get_primary_clipboard()
                    try:
                        primary.set(text)
                    except TypeError:
                        primary.set(str, text)
                    except AttributeError:
                        primary.set_text(text)
                except Exception:
                    pass
        else:
            self._view.copy()
