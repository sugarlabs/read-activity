# Copyright (C) 2014, Sam Parkinson
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

import zipfile
from gettext import gettext as _
from gi.repository import GObject
from gi.repository import Gtk

from sugar3.graphics.alert import Alert

from imageview import ImageViewer

IMAGE_ENDINGS = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif')


class ComicViewer(GObject.GObject):

    __gsignals__ = {
        'zoom-changed': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE,
                         ([int])),
        'page-changed': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE,
                         ([int, int]))
    }

    def setup(self, activity):
        self._activity = activity
        self._zip = None
        self._images = []
        self._index = 0
        self._rotate = 0
        self._old_zoom = 1.0

        self._sw = Gtk.ScrolledWindow()
        self._sw.set_policy(Gtk.PolicyType.ALWAYS, Gtk.PolicyType.ALWAYS)
        self._activity._hbox.pack_start(self._sw, True, True, 0)
        self._sw.show()

        self._view = ImageViewer()
        self._view.set_zoom(1.0)
        self._view.connect('setup-new-surface', self.__new_surface_cb)
        self._sw.add(self._view)
        self._view.show()

    def load_document(self, file_path):
        try:
            self._zip = zipfile.ZipFile(file_path.replace('file://', ''))
        except (zipfile.BadZipfile, IOError):
            pass

        files = self._zip.namelist()
        files.sort()
        self._images = [i for i in files if i.endswith(IMAGE_ENDINGS)]

        if len(self._images) == 0:
            alert = Alert()
            alert.props.title = _('Can not read Comic Book Archive')
            alert.props.msg = _('No readable images were found')
            self._activity.add_alert(alert)
            return

        self.set_current_page(0)

    def load_metadata(self, activity):
        if activity.metadata.get('view-zoom'):
            self.set_zoom(activity.metadata.get('view-zoom'))

    def update_metadata(self, activity):
        activity.metadata['view-zoom'] = self.get_zoom()

    def get_current_page(self):
        return self._index

    def set_current_page(self, page):
        if len(self._images) == 0:
            return

        from_ = self._index
        self._index = page

        filename = self._images[page]
        data = self._zip.read(filename)
        self._view.set_data(data)

        self.emit('page-changed', from_, self._index)

    def __new_surface_cb(self, view):
        self._view.set_rotate(self._rotate)
        self._view.update_adjustments()

        self._sw.get_hadjustment().set_value(0)
        self._sw.get_vadjustment().set_value(0)

        self._view.update_adjustments()
        self._view.queue_draw()

    def next_page(self):
        if self._index + 1 < self.get_pagecount():
            self.set_current_page(self._index + 1)

    def previous_page(self):
        if self._index - 1 >= 0:
            self.set_current_page(self._index - 1)

    def can_rotate(self):
        return True

    def rotate_left(self):
        self._view.rotate_anticlockwise()
        self._rotate -= 1
        if self._rotate == -4:
            self._rotate = 0

    def rotate_right(self):
        self._view.rotate_clockwise()
        self._rotate += 1
        if self._rotate == 4:
            self._rotate = 0

    def get_pagecount(self):
        return len(self._images)

    def connect_zoom_handler(self, handler):
        self.connect('zoom-changed', handler)

    def _zoom_changed(self):
        self.emit('zoom-changed', self.get_zoom())

    def get_zoom(self):
        return self._view.get_zoom()

    def set_zoom(self, value):
        self._view.set_zoom(value)
        self._zoom_changed()

    def zoom_in(self):
        self._view.zoom_in()
        self._zoom_changed()

    def can_zoom_in(self):
        return self._view.can_zoom_in()

    def zoom_out(self):
        self._view.zoom_out()
        self._zoom_changed()

    def can_zoom_out(self):
        return self._view.can_zoom_out()

    def can_zoom_to_width(self):
        return True

    def zoom_to_width(self):
        self._view.zoom_to_width()
        self._zoom_changed()

    def zoom_to_best_fit(self):
        self._view.zoom_to_fit()
        self._zoom_changed()

    def can_zoom_to_actual_size(self):
        return True

    def zoom_to_actual_size(self):
        self._view.zoom_original()
        self._zoom_changed()

    def connect_page_changed_handler(self, handler):
        self.connect('page-changed', handler)

    def scroll(self, scrolltype, horizontal):
        if scrolltype == Gtk.ScrollType.PAGE_BACKWARD:
            self.previous_page()
        elif scrolltype == Gtk.ScrollType.PAGE_FORWARD:
            self.next_page()
        elif scrolltype == Gtk.ScrollType.STEP_BACKWARD:
            self._scroll_step(False, horizontal)
        elif scrolltype == Gtk.ScrollType.STEP_FORWARD:
            self._scroll_step(True, horizontal)
        elif scrolltype == Gtk.ScrollType.START:
            self.set_current_page(1)
        elif scrolltype == Gtk.ScrollType.END:
            self.set_current_page(self._document.get_n_pages())
        else:
            pass

    def _scroll_step(self, forward, horizontal):
        if horizontal:
            adj = self._sw.get_hadjustment()
        else:
            adj = self._sw.get_vadjustment()

        value = adj.get_value()
        step = adj.get_step_increment()

        if forward:
            adj.set_value(value + step)
        else:
            adj.set_value(value - step)

    # Not relevant for non-text documents

    def can_highlight(self):
        return False

    def can_do_text_to_speech(self):
        return False

    def find_set_highlight_search(self, set_highlight_search):
        pass

    def find_next(self):
        pass

    def find_previous(self):
        pass

    def update_toc(self, activity):
        pass

    def handle_link(self, link):
        pass

    def get_current_link(self):
        return ''

    def get_link_iter(self, link):
        return None

    def copy(self):
        # Copy is for the selected text
        pass
