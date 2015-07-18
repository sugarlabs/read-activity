# Copyright (C) 2007, Red Hat, Inc.
# Copyright (C) 2007 Collabora Ltd. <http://www.collabora.co.uk/>
# Copyright 2008 One Laptop Per Child
# Copyright 2009 Simon Schampijer
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

import logging
import os
import time
from gettext import gettext as _
import re
import md5
import StringIO
import cairo
import json

import emptypanel

import dbus
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Gio

GObject.threads_init()

import telepathy

from sugar3.activity import activity
from sugar3.graphics.toolbutton import ToolButton
from sugar3.graphics.toolbarbox import ToolbarBox
from sugar3.graphics.toolbarbox import ToolbarButton
from sugar3.graphics.toggletoolbutton import ToggleToolButton
from sugar3.graphics.alert import ConfirmationAlert
from sugar3.graphics.alert import Alert
from sugar3.activity.widgets import ActivityToolbarButton
from sugar3.activity.widgets import StopButton
from sugar3.graphics.tray import HTray
from sugar3 import network
from sugar3 import mime
from sugar3 import profile

from sugar3.datastore import datastore
from sugar3.graphics.objectchooser import ObjectChooser
try:
    from sugar3.graphics.objectchooser import FILTER_TYPE_MIME_BY_ACTIVITY
except:
    FILTER_TYPE_MIME_BY_ACTIVITY = 'mime_by_activity'

from sugar3.graphics import style

from readtoolbar import EditToolbar
from readtoolbar import ViewToolbar
from bookmarkview import BookmarkView
from readdb import BookmarkManager
from sugar3.graphics.menuitem import MenuItem
from linkbutton import LinkButton

_HARDWARE_MANAGER_INTERFACE = 'org.laptop.HardwareManager'
_HARDWARE_MANAGER_SERVICE = 'org.laptop.HardwareManager'
_HARDWARE_MANAGER_OBJECT_PATH = '/org/laptop/HardwareManager'

_TOOLBAR_READ = 2

_logger = logging.getLogger('read-activity')


def _get_screen_dpi():
    xft_dpi = Gtk.Settings.get_default().get_property('gtk-xft-dpi')
    _logger.debug('Setting dpi to %f', float(xft_dpi / 1024))
    return float(xft_dpi / 1024)


def get_md5(filename):
    # FIXME: Should be moved somewhere else
    filename = filename.replace('file://', '')  # XXX: hack
    fh = open(filename)
    digest = md5.new()
    while 1:
        buf = fh.read(4096)
        if buf == "":
            break
        digest.update(buf)
    fh.close()
    return digest.hexdigest()


class ReadHTTPRequestHandler(network.ChunkedGlibHTTPRequestHandler):
    """HTTP Request Handler for transferring document while collaborating.

    RequestHandler class that integrates with Glib mainloop. It writes
    the specified file to the client in chunks, returning control to the
    mainloop between chunks.

    """

    def translate_path(self, path):
        """Return the filepath to the shared document."""
        if path.endswith('document'):
            return self.server.filepath
        if path.endswith('metadata'):
            return self.server.get_metadata_path()


class ReadHTTPServer(network.GlibTCPServer):
    """HTTP Server for transferring document while collaborating."""

    def __init__(self, server_address, filepath, create_metadata_cb):
        """Set up the GlibTCPServer with the ReadHTTPRequestHandler.

        filepath -- path to shared document to be served.
        """
        self.filepath = filepath
        self._create_metadata_cb = create_metadata_cb
        network.GlibTCPServer.__init__(self, server_address,
                                       ReadHTTPRequestHandler)

    def get_metadata_path(self):
        return self._create_metadata_cb()


class ReadURLDownloader(network.GlibURLDownloader):
    """URLDownloader that provides content-length and content-type."""

    def get_content_length(self):
        """Return the content-length of the download."""
        if self._info is not None:
            return int(self._info.headers.get('Content-Length'))

    def get_content_type(self):
        """Return the content-type of the download."""
        if self._info is not None:
            return self._info.headers.get('Content-type')
        return None


READ_STREAM_SERVICE = 'read-activity-http'


class ProgressAlert(Alert):
    """
    Progress alert with a progressbar - to show the advance of a task
    """

    def __init__(self, timeout=5, **kwargs):
        Alert.__init__(self, **kwargs)

        self._pb = Gtk.ProgressBar()
        self._msg_box.pack_start(self._pb, False, False, 0)
        self._pb.set_size_request(int(Gdk.Screen.width() * 9. / 10.), -1)
        self._pb.set_fraction(0.0)
        self._pb.show()

    def set_fraction(self, fraction):
        # update only by 10% fractions
        if int(fraction * 100) % 10 == 0:
            self._pb.set_fraction(fraction)
            self._pb.queue_draw()
            # force updating the progressbar
            while Gtk.events_pending():
                Gtk.main_iteration_do(True)


class ReadActivity(activity.Activity):
    """The Read sugar activity."""

    def __init__(self, handle):
        activity.Activity.__init__(self, handle)

        self.max_participants = 1
        self._document = None
        self._fileserver = None
        self._object_id = handle.object_id
        self._toc_model = None
        self.filehash = None

        self.connect('key-press-event', self._key_press_event_cb)
        self.connect('key-release-event', self._key_release_event_cb)

        _logger.debug('Starting Read...')

        self._view = None
        self.dpi = _get_screen_dpi()
        self._bookmark_view = BookmarkView()
        self._bookmark_view.connect('bookmark-changed',
                                    self._update_bookmark_cb)

        tray = HTray()
        self.set_tray(tray, Gtk.PositionType.BOTTOM)

        toolbar_box = ToolbarBox()

        self.activity_button = ActivityToolbarButton(self)
        toolbar_box.toolbar.insert(self.activity_button, 0)
        self.activity_button.show()

        self._edit_toolbar = EditToolbar()
        self._edit_toolbar.undo.props.visible = False
        self._edit_toolbar.redo.props.visible = False
        self._edit_toolbar.separator.props.visible = False
        self._edit_toolbar.copy.set_sensitive(False)
        self._edit_toolbar.copy.connect('clicked', self._edit_toolbar_copy_cb)
        self._edit_toolbar.paste.props.visible = False

        edit_toolbar_button = ToolbarButton(page=self._edit_toolbar,
                                            icon_name='toolbar-edit')
        self._edit_toolbar.show()
        toolbar_box.toolbar.insert(edit_toolbar_button, -1)
        edit_toolbar_button.show()

        self._highlight = self._edit_toolbar.highlight
        self._highlight_id = self._highlight.connect('clicked',
                                                     self.__highlight_cb)

        self._view_toolbar = ViewToolbar()
        self._view_toolbar.connect('go-fullscreen',
                                   self.__view_toolbar_go_fullscreen_cb)
        self._view_toolbar.connect('toggle-index-show',
                                   self.__toogle_navigator_cb)
        self._view_toolbar.connect('toggle-tray-show',
                                   self.__toogle_tray_cb)
        view_toolbar_button = ToolbarButton(page=self._view_toolbar,
                                            icon_name='toolbar-view')
        self._view_toolbar.show()
        toolbar_box.toolbar.insert(view_toolbar_button, -1)
        view_toolbar_button.show()

        self._back_button = self._create_back_button()
        toolbar_box.toolbar.insert(self._back_button, -1)
        self._back_button.show()

        self._forward_button = self._create_forward_button()
        toolbar_box.toolbar.insert(self._forward_button, -1)
        self._forward_button.show()

        num_page_item = Gtk.ToolItem()
        self._num_page_entry = self._create_search()
        num_page_item.add(self._num_page_entry)
        self._num_page_entry.show()
        toolbar_box.toolbar.insert(num_page_item, -1)
        num_page_item.show()

        total_page_item = Gtk.ToolItem()
        self._total_page_label = Gtk.Label()
        total_page_item.add(self._total_page_label)
        self._total_page_label.show()
        self._total_page_label.set_margin_right(5)
        toolbar_box.toolbar.insert(total_page_item, -1)
        total_page_item.show()

        self._bookmarker = ToggleToolButton('emblem-favorite')
        self._bookmarker_toggle_handler_id = self._bookmarker.connect(
            'toggled', self.__bookmarker_toggled_cb)
        self._bookmarker.show()
        toolbar_box.toolbar.insert(self._bookmarker, -1)

        self.speech_toolbar_button = ToolbarButton(icon_name='speak')
        toolbar_box.toolbar.insert(self.speech_toolbar_button, -1)

        separator = Gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_size_request(0, -1)
        separator.set_expand(True)
        toolbar_box.toolbar.insert(separator, -1)
        separator.show()

        stop_button = StopButton(self)
        toolbar_box.toolbar.insert(stop_button, -1)
        stop_button.show()

        self.set_toolbar_box(toolbar_box)
        toolbar_box.show()

        # This is needed to prevent the call of read_file on
        # canvas map, becuase interact in a bad way with the emptypanel
        # the program takes responsability of this task.
        self._read_file_called = True

        self._vbox = Gtk.VBox()
        self._vbox.show()

        overlay = Gtk.Overlay()

        self._hbox = Gtk.HBox()
        self._hbox.show()
        overlay.add(self._hbox)

        self._bookmark_view.props.halign = Gtk.Align.END
        self._bookmark_view.props.valign = Gtk.Align.START
        # HACK: This is to calculate the scrollbar width
        # defined in sugar-artwork gtk-widgets.css.em
        if style.zoom(1):
            scrollbar_width = 15
        else:
            scrollbar_width = 11

        self._bookmark_view.props.margin_right = scrollbar_width
        overlay.add_overlay(self._bookmark_view)
        overlay.show()
        self._vbox.pack_start(overlay, True, True, 0)
        self.set_canvas(self._vbox)

        self._navigator = self._create_navigator()

        # Set up for idle suspend
        self._idle_timer = 0
        self._service = None

        # start with sleep off
        self._sleep_inhibit = True

        self.unused_download_tubes = set()
        self._want_document = True
        self._download_content_length = 0
        self._download_content_type = None
        # Status of temp file used for write_file:
        self._tempfile = None
        self._close_requested = False

        fname = os.path.join('/etc', 'inhibit-ebook-sleep')

        if not os.path.exists(fname):
            try:
                bus = dbus.SystemBus()
                proxy = bus.get_object(_HARDWARE_MANAGER_SERVICE,
                                       _HARDWARE_MANAGER_OBJECT_PATH)
                self._service = dbus.Interface(proxy,
                                               _HARDWARE_MANAGER_INTERFACE)
                self._scrolled.props.vadjustment.connect("value-changed",
                                                         self._user_action_cb)
                self._scrolled.props.hadjustment.connect("value-changed",
                                                         self._user_action_cb)
                self.connect("focus-in-event", self._focus_in_event_cb)
                self.connect("focus-out-event", self._focus_out_event_cb)
                self.connect("notify::active", self._now_active_cb)

                _logger.debug('Suspend on idle enabled')
            except dbus.DBusException:
                _logger.info(
                    'Hardware manager service not found, no idle suspend.')
        else:
            _logger.debug('Suspend on idle disabled')

        self.connect("shared", self._shared_cb)

        h = hash(self._activity_id)
        self.port = 1024 + (h % 64511)

        self._progress_alert = None

        if self._jobject.file_path is not None and \
                self._jobject.file_path != '':
            self.read_file(self._jobject.file_path)
        elif handle.uri:
            self._load_document(handle.uri)
            # TODO: we need trasfer the metadata and uodate
            # bookmarks and urls

        elif self.shared_activity:
            # We're joining
            if self.get_shared():
                # Already joined for some reason, just get the document
                self._joined_cb(self)
            else:
                self._progress_alert = ProgressAlert()
                self._progress_alert.props.title = _('Please wait')
                self._progress_alert.props.msg = _('Starting connection...')
                self.add_alert(self._progress_alert)

                # Wait for a successful join before trying to get the document
                self.connect("joined", self._joined_cb)
        else:
            # Not joining, not resuming or resuming session without file
            emptypanel.show(self, 'activity-read',
                            _('No book'), _('Choose something to read'),
                            self._show_journal_object_picker_cb)

    def _create_back_button(self):
        back = ToolButton('go-previous-paired')
        back.set_tooltip(_('Back'))
        back.props.sensitive = False
        palette = back.get_palette()

        previous_page = MenuItem(text_label=_("Previous page"))
        previous_page.show()
        previous_bookmark = MenuItem(text_label=_("Previous bookmark"))
        previous_bookmark.show()
        palette.menu.append(previous_page)
        palette.menu.append(previous_bookmark)

        back.connect('clicked', self.__go_back_cb)
        previous_page.connect('activate', self.__go_back_page_cb)
        previous_bookmark.connect('activate', self.__prev_bookmark_activate_cb)
        return back

    def _create_forward_button(self):
        forward = ToolButton('go-next-paired')
        forward.set_tooltip(_('Forward'))
        forward.props.sensitive = False
        palette = forward.get_palette()

        next_page = MenuItem(text_label=_("Next page"))
        next_page.show()
        next_bookmark = MenuItem(text_label=_("Next bookmark"))
        next_bookmark.show()

        palette.menu.append(next_page)
        palette.menu.append(next_bookmark)

        forward.connect('clicked', self.__go_forward_cb)
        next_page.connect('activate', self.__go_forward_page_cb)
        next_bookmark.connect('activate', self.__next_bookmark_activate_cb)
        return forward

    def _create_search(self):
        num_page_entry = Gtk.Entry()
        num_page_entry.set_text('0')
        num_page_entry.set_alignment(1)
        num_page_entry.connect('insert-text',
                               self.__num_page_entry_insert_text_cb)
        num_page_entry.connect('activate',
                               self.__num_page_entry_activate_cb)
        num_page_entry.set_width_chars(4)
        return num_page_entry

    def _set_total_page_label(self, value):
        self._total_page_label.set_text(' / %s' % value)

    def show_navigator_button(self):
        self._view_toolbar.show_nav_button()

    def _create_navigator(self):
        def __cursor_changed_cb(treeview):
            selection = treeview.get_selection()
            store, index_iter = selection.get_selected()
            if index_iter is None:
                # Nothing selected. This happens at startup
                return
            if store.iter_has_child(index_iter):
                path = store.get_path(index_iter)
                if treeview.row_expanded(path):
                    treeview.collapse_row(path)
                else:
                    treeview.expand_row(path, False)

        self._toc_visible = False
        self._update_toc_view = False
        toc_navigator = Gtk.TreeView()
        toc_navigator.set_enable_search(False)
        toc_navigator.connect('cursor-changed', __cursor_changed_cb)
        toc_selection = toc_navigator.get_selection()
        toc_selection.set_mode(Gtk.SelectionMode.SINGLE)

        cell = Gtk.CellRendererText()
        self.treecol_toc = Gtk.TreeViewColumn(_('Index'), cell, text=0)
        toc_navigator.append_column(self.treecol_toc)

        self._toc_scroller = Gtk.ScrolledWindow(hadjustment=None,
                                                vadjustment=None)
        self._toc_scroller.set_policy(Gtk.PolicyType.AUTOMATIC,
                                      Gtk.PolicyType.AUTOMATIC)
        self._toc_scroller.add(toc_navigator)
        self._hbox.pack_start(self._toc_scroller, expand=False, fill=False,
                              padding=0)
        self._toc_separator = Gtk.VSeparator()
        self._hbox.pack_start(self._toc_separator, expand=False, fill=False,
                              padding=1)
        return toc_navigator

    def set_navigator_model(self, model):
        self._toc_model = model
        self._navigator.set_model(model)

    def __toogle_navigator_cb(self, button, visible):
        scrollbar_pos = -1
        if hasattr(self._view, 'get_vertical_pos'):
            scrollbar_pos = self._view.get_vertical_pos()
        if visible:
            self._toc_visible = True
            self._update_toc_view = True
            self._toc_select_active_page()
            self._toc_scroller.set_size_request(int(Gdk.Screen.width() / 4),
                                                -1)
            self._toc_scroller.show_all()
            self._toc_separator.show()
        else:
            self._toc_visible = False
            self._toc_scroller.hide()
            self._toc_separator.hide()
        if scrollbar_pos > -1:
            self._view.set_vertical_pos(scrollbar_pos)

    def __toogle_tray_cb(self, button, visible):
        if visible:
            logging.error('Show tray')
            self.tray.show()
        else:
            logging.error('Hide tray')
            self.tray.hide()

    def __num_page_entry_insert_text_cb(self, entry, text, length, position):
        if not re.match('[0-9]', text):
            entry.emit_stop_by_name('insert-text')
            return True
        return False

    def __num_page_entry_activate_cb(self, entry):
        if entry.props.text:
            page = int(entry.props.text) - 1
        else:
            page = 0

        self._view.set_current_page(page)
        entry.props.text = str(page + 1)

    def __go_back_cb(self, button):
        self._view.scroll(Gtk.ScrollType.PAGE_BACKWARD, False)

    def __go_forward_cb(self, button):
        self._view.scroll(Gtk.ScrollType.PAGE_FORWARD, False)

    def __go_back_page_cb(self, button):
        self._view.previous_page()

    def __go_forward_page_cb(self, button):
        self._view.next_page()

    def __highlight_cb(self, button):
        self._view.toggle_highlight(button.get_active())

    def __prev_bookmark_activate_cb(self, menuitem):
        page = self._view.get_current_page()

        prev_bookmark = self._bookmarkmanager.get_prev_bookmark_for_page(page)
        if prev_bookmark is not None:
            self._view.set_current_page(prev_bookmark.page_no)

    def __next_bookmark_activate_cb(self, menuitem):
        page = self._view.get_current_page()

        next_bookmark = self._bookmarkmanager.get_next_bookmark_for_page(page)
        if next_bookmark is not None:
            self._view.set_current_page(next_bookmark.page_no)

    def __bookmarker_toggled_cb(self, button):
        page = self._view.get_current_page()
        if self._bookmarker.props.active:
            self._bookmark_view.add_bookmark(page)
        else:
            alert = ConfirmationAlert()
            alert.props.title = _('Delete bookmark')
            alert.props.msg = _('All the information related '
                                'with this bookmark will be lost')
            self.add_alert(alert)
            alert.connect('response', self.__alert_response_cb, page)
            alert.show()

    def __alert_response_cb(self, alert, response_id, page):
        self.remove_alert(alert)

        if response_id is Gtk.ResponseType.OK:
            self._bookmark_view.del_bookmark(page)
        elif response_id is Gtk.ResponseType.CANCEL:
            self._bookmarker.handler_block(self._bookmarker_toggle_handler_id)
            self._bookmarker.props.active = True
            self._bookmarker.handler_unblock(
                self._bookmarker_toggle_handler_id)

    def __page_changed_cb(self, model, page_from, page_to):
        self._update_nav_buttons(page_to)
        if self._toc_model is not None:
            self._toc_select_active_page()

        self._bookmark_view.update_for_page(page_to)
        self.update_bookmark_button()

        if self._view.can_highlight():
            self._view.show_highlights(page_to)

    def _update_bookmark_cb(self, sidebar):
        logging.error('update bookmark event')
        self.update_bookmark_button()

    def update_bookmark_button(self):
        self._bookmarker.handler_block(self._bookmarker_toggle_handler_id)
        self._bookmarker.props.active = \
            self._bookmark_view.is_showing_local_bookmark()
        self._bookmarker.handler_unblock(self._bookmarker_toggle_handler_id)

    def _update_nav_buttons(self, current_page):
        self._back_button.props.sensitive = current_page > 0
        self._forward_button.props.sensitive = \
            current_page < self._view.get_pagecount() - 1

        self._num_page_entry.props.text = str(current_page + 1)
        self._set_total_page_label(self._view.get_pagecount())

    def _update_toc(self):
        if self._view.update_toc(self):
            self._navigator_changed_handler_id = \
                self._navigator.connect('cursor-changed',
                                        self.__navigator_cursor_changed_cb)

    def __navigator_cursor_changed_cb(self, toc_treeview):
        if toc_treeview.get_selection() is None:
            return
        treestore, toc_selected = toc_treeview.get_selection().get_selected()

        if toc_selected is not None:
            link = self._toc_model.get(toc_selected, 1)[0]
            logging.debug('View handle link %s', link)
            self._update_toc_view = False
            self._view.handle_link(link)
            self._update_toc_view = True

    def _toc_select_active_page(self):
        if not self._toc_visible or not self._update_toc_view:
            return

        _store, toc_selected = self._navigator.get_selection().get_selected()

        if toc_selected is not None:
            selected_link = self._toc_model.get(toc_selected, 1)[0]
        else:
            selected_link = ""
        current_link = self._view.get_current_link()

        if current_link == selected_link:
            return

        link_iter = self._view.get_link_iter(current_link)

        if link_iter is not None:
            self._navigator.handler_block(self._navigator_changed_handler_id)
            toc_selection = self._navigator.get_selection()
            toc_selection.select_iter(link_iter)
            self._navigator.handler_unblock(self._navigator_changed_handler_id)
        else:
            logging.debug('link "%s" not found in the toc model', current_link)

    def _show_journal_object_picker_cb(self, button):
        """Show the journal object picker to load a document.

        This is for if Read is launched without a document.
        """
        if not self._want_document:
            return

        try:
            chooser = ObjectChooser(parent=self,
                                    what_filter=self.get_bundle_id(),
                                    filter_type=FILTER_TYPE_MIME_BY_ACTIVITY)
        except:
            chooser = ObjectChooser(parent=self,
                                    what_filter=mime.GENERIC_TYPE_TEXT)

        try:
            result = chooser.run()
            if result == Gtk.ResponseType.ACCEPT:
                logging.debug('ObjectChooser: %r' %
                              chooser.get_selected_object())
                jobject = chooser.get_selected_object()
                if jobject and jobject.file_path:
                    for key in jobject.metadata.keys():
                        self.metadata[key] = jobject.metadata[key]
                    self.read_file(jobject.file_path)
                    jobject.object_id = self._object_id
        finally:
            chooser.destroy()
            del chooser

    def _now_active_cb(self, widget, pspec):
        if self.props.active:
            # Now active, start initial suspend timeout
            if self._idle_timer > 0:
                GObject.source_remove(self._idle_timer)
            self._idle_timer = GObject.timeout_add_seconds(15,
                                                           self._suspend_cb)
            self._sleep_inhibit = False
        else:
            # Now inactive
            self._sleep_inhibit = True

    def _focus_in_event_cb(self, widget, event):
        """Enable ebook mode idle sleep since Read has focus."""
        self._sleep_inhibit = False
        self._user_action_cb(self)

    def _focus_out_event_cb(self, widget, event):
        """Disable ebook mode idle sleep since Read lost focus."""
        self._sleep_inhibit = True

    def _user_action_cb(self, widget):
        """Set a timer for going back to ebook mode idle sleep."""
        if self._idle_timer > 0:
            GObject.source_remove(self._idle_timer)
        self._idle_timer = GObject.timeout_add_seconds(5, self._suspend_cb)

    def _suspend_cb(self):
        """Go into ebook mode idle sleep."""
        # If the machine has been idle for 5 seconds, suspend
        self._idle_timer = 0
        if not self._sleep_inhibit and not self.get_shared():
            self._service.set_kernel_suspend()
        return False

    def read_file(self, file_path):
        """Load a file from the datastore on activity start."""
        _logger.debug('ReadActivity.read_file: %s', file_path)
        # enable collaboration
        self.activity_button.page.share.props.sensitive = True

        # we need copy the file to a new place, the file_path disappear
        extension = os.path.splitext(file_path)[1]
        tempfile = os.path.join(self.get_activity_root(), 'instance',
                                'tmp%i%s' % (time.time(), extension))
        os.link(file_path, tempfile)

        self._load_document('file://' + tempfile)

        # FIXME: This should obviously be fixed properly
        GObject.timeout_add_seconds(
            1, self.__view_toolbar_needs_update_size_cb, None)

    def write_file(self, file_path):
        """Write into datastore for Keep.

        The document is saved by hardlinking from the temporary file we
        keep around instead of "saving".

        The metadata is updated, including current page, view settings,
        search text.

        """
        if self._tempfile is None:
            # Workaround for closing Read with no document loaded
            raise NotImplementedError

        try:
            self.metadata['Read_current_page'] = \
                str(self._view.get_current_page())

            self._view.update_metadata(self)

            self.metadata['Read_search'] = \
                self._edit_toolbar._search_entry.props.text

        except Exception, e:
            _logger.error('write_file(): %s', e)

        self.metadata['Read_search'] = \
            self._edit_toolbar._search_entry.props.text
        self.metadata['activity'] = self.get_bundle_id()

        # the file is only saved if modified
        saved = False
        if hasattr(self._view, 'save'):
            saved = self._view.save(file_path)

        if saved:
            self.filehash = get_md5(file_path)
            self.metadata['filehash'] = self.filehash
        else:
            os.link(self._tempfile, file_path)

        if self.filehash is None:
            self.filehash = get_md5(file_path)
        self.metadata['filehash'] = self.filehash

        self._save_bookmars_in_metadata()

        if self._close_requested:
            _logger.debug("Removing temp file %s because we will close",
                          self._tempfile)
            os.unlink(self._tempfile)

            # remove file used to transmit the metadata if exits
            try:
                metadata_file_path = self._tempfile + '.json'
                os.unlink(metadata_file_path)
            except OSError:
                pass

            self._tempfile = None

    def _save_bookmars_in_metadata(self):
        # save bookmarks in the metadata
        bookmarks = []
        for bookmark in self._bookmarkmanager.get_bookmarks():
            bookmarks.append(bookmark.get_as_dict())
        self.metadata['bookmarks'] = json.dumps(bookmarks)
        self.metadata['highlights'] = json.dumps(
            self._bookmarkmanager.get_all_highlights())

    def can_close(self):
        """Prepare to cleanup on closing.

        Called from self.close()
        """
        self._close_requested = True
        return True

    def _download_result_cb(self, getter, tempfile, suggested_name, tube_id,
                            tube_ip, tube_port):
        if self._download_content_type == 'text/html':
            # got an error page instead
            self._download_error_cb(getter, 'HTTP Error', tube_id)
            return

        del self.unused_download_tubes

        # Use the suggested file, the mime is not recognized if the extension
        # is wrong in some cases (epub)
        temp_dir = os.path.dirname(tempfile)
        new_name = os.path.join(temp_dir, suggested_name)
        os.rename(tempfile, new_name)
        tempfile = new_name

        _logger.debug("Saving file %s to datastore...", tempfile)
        mimetype = Gio.content_type_guess(tempfile, None)[0]
        self._jobject.metadata['mime_type'] = mimetype
        self._jobject.file_path = tempfile
        datastore.write(self._jobject)

        _logger.debug("Got document %s (%s) from tube %u",
                      tempfile, suggested_name, tube_id)
        if self._progress_alert is not None:
            self.remove_alert(self._progress_alert)
            self._progress_alert = None

        # download the metadata
        GObject.idle_add(self._download_metadata, tube_id, tube_ip, tube_port)

    def _download_metadata_result_cb(self, getter, tempfile, suggested_name,
                                     tube_id):
        # load the shared metadata
        with open(tempfile) as json_file:
            shared_metadata = json.load(json_file)
        os.remove(tempfile)

        # load the object from the datastore to update the file path
        GObject.idle_add(self._open_downloaded_file, shared_metadata)

    def _open_downloaded_file(self, shared_metadata):
        self._jobject = datastore.get(self._jobject.object_id)
        for key in shared_metadata.keys():
            self.metadata[key] = shared_metadata[key]

        self.read_file(self._jobject.file_path)

    def _download_progress_cb(self, getter, bytes_downloaded, tube_id):
        # FIXME: Draw a progress bar
        if self._download_content_length > 0:
            _logger.debug("Downloaded %u of %u bytes from tube %u...",
                          bytes_downloaded, self._download_content_length,
                          tube_id)
            fraction = float(bytes_downloaded) / \
                float(self._download_content_length)
            self._progress_alert.set_fraction(fraction)
        else:
            _logger.debug("Downloaded %u bytes from tube %u...",
                          bytes_downloaded, tube_id)

    def _download_error_cb(self, getter, err, tube_id):
        _logger.debug("Error getting document from tube %u: %s",
                      tube_id, err)
        self._want_document = True
        self._download_content_length = 0
        self._download_content_type = None
        if self._progress_alert is not None:
            self.remove_alert(self._progress_alert)
            self._progress_alert = None
        GObject.idle_add(self._get_document)

    def _get_connection_params(self, tube_id):
        # return ip and port to download a file
        chan = self.shared_activity.telepathy_tubes_chan
        iface = chan[telepathy.CHANNEL_TYPE_TUBES]
        addr = iface.AcceptStreamTube(
            tube_id,
            telepathy.SOCKET_ADDRESS_TYPE_IPV4,
            telepathy.SOCKET_ACCESS_CONTROL_LOCALHOST, 0,
            utf8_strings=True)
        _logger.debug('Accepted stream tube: listening address is %r', addr)
        # SOCKET_ADDRESS_TYPE_IPV4 is defined to have addresses of type '(sq)'
        assert isinstance(addr, dbus.Struct)
        assert len(addr) == 2
        assert isinstance(addr[0], str)
        assert isinstance(addr[1], (int, long))
        assert addr[1] > 0 and addr[1] < 65536
        ip = addr[0]
        port = int(addr[1])
        return ip, port

    def _download_document(self, tube_id):
        ip, port = self._get_connection_params(tube_id)

        getter = ReadURLDownloader("http://%s:%d/document" % (ip, port))
        getter.connect("finished", self._download_result_cb, tube_id, ip, port)
        getter.connect("progress", self._download_progress_cb, tube_id)
        getter.connect("error", self._download_error_cb, tube_id)
        getter.start()
        self._download_content_length = getter.get_content_length()
        self._download_content_type = getter.get_content_type()
        return False

    def _download_metadata(self, tube_id, ip, port):
        getter = ReadURLDownloader("http://%s:%d/metadata" % (ip, port))
        getter.connect("finished", self._download_metadata_result_cb, tube_id)
        # getter.connect("progress", self._download_progress_cb, tube_id)
        getter.connect("error", self._download_error_cb, tube_id)
        getter.start()
        self._download_content_length = getter.get_content_length()
        self._download_content_type = getter.get_content_type()
        return False

    def _get_document(self):
        if not self._want_document:
            return False

        # Pick an arbitrary tube we can try to download the document from
        try:
            tube_id = self.unused_download_tubes.pop()
        except (ValueError, KeyError), e:
            _logger.debug('No tubes to get the document from right now: %s',
                          e)
            return False

        # Avoid trying to download the document multiple times at once
        self._want_document = False
        GObject.idle_add(self._download_document, tube_id)
        return False

    def _joined_cb(self, also_self):
        """Callback for when a shared activity is joined.

        Get the shared document from another participant.
        """
        self.watch_for_tubes()
        if self._progress_alert is not None:
            self._progress_alert.props.msg = _('Receiving book...')

        GObject.idle_add(self._get_document)

    def _load_document(self, filepath):
        """Load the specified document and set up the UI.

        filepath -- string starting with file://

        """
        if self._tempfile is not None:
            # prevent reopen
            return

        self.set_canvas(self._vbox)

        filename = filepath.replace('file://', '')
        self._tempfile = filename
        if not os.path.exists(filename) or os.path.getsize(filename) == 0:
            return
        if 'mime_type' not in self.metadata or not self.metadata['mime_type']:
            mimetype = Gio.content_type_guess(filepath, None)[0]
            self.metadata['mime_type'] = mimetype
        else:
            mimetype = self.metadata['mime_type']

        if mimetype == 'application/epub+zip':
            import epubadapter
            self._view = epubadapter.EpubViewer()
        elif mimetype == 'text/plain' or mimetype == 'application/zip':
            import textadapter
            self._view = textadapter.TextViewer()
        elif mimetype == 'application/x-cbz':
            import comicadapter
            self._view = comicadapter.ComicViewer()
        else:
            import evinceadapter
            self._view = evinceadapter.EvinceViewer()

        self._view.setup(self)
        self._view.load_document(filepath)

        self._want_document = False

        self._view_toolbar.set_view(self._view)
        self._edit_toolbar.set_view(self._view)

        self.filehash = self.metadata.get('filehash', None)
        if self.filehash is None:
            self.filehash = get_md5(filepath)
            logging.error('Calculate hash %s', self.filehash)

        self._bookmarkmanager = BookmarkManager(self.filehash)

        # update bookmarks and highlights with the informaiton
        # from the metadata
        if 'bookmarks' in self.metadata:
            self._bookmarkmanager.update_bookmarks(
                json.loads(self.metadata['bookmarks']))

        if 'highlights' in self.metadata:
            self._bookmarkmanager.update_highlights(
                json.loads(self.metadata['highlights']))

        self._bookmarkmanager.connect('added_bookmark',
                                      self._added_bookmark_cb)
        self._bookmarkmanager.connect('removed_bookmark',
                                      self._removed_bookmark_cb)

        # Add the bookmarks to the tray
        for bookmark in self._bookmarkmanager.get_bookmarks():
            page = bookmark.page_no
            thumb = self._bookmarkmanager.get_bookmark_preview(page)
            if thumb is None:
                logging.error('Preview NOT FOUND')
                thumb = self._get_screenshot()
            # The database is zero based
            num_page = int(page) + 1
            title = _('%s (Page %d)') % \
                (bookmark.get_note_title(), num_page)
            self._add_link_totray(num_page, thumb, bookmark.color, title,
                                  bookmark.nick, bookmark.local)

        self._bookmark_view.set_bookmarkmanager(self._bookmarkmanager)
        self._update_toc()
        self._view.connect_page_changed_handler(self.__page_changed_cb)
        self._view.load_metadata(self)
        self._update_toolbars()

        self._edit_toolbar._search_entry.props.text = \
            self.metadata.get('Read_search', '')

        current_page = int(self.metadata.get('Read_current_page', '0'))
        _logger.debug('Setting page to: %d', current_page)
        self._view.set_current_page(current_page)
        self._update_nav_buttons(current_page)

        # README: bookmark sidebar is not showing the bookmark in the
        # first page because this is updated just if the page number changes
        if current_page == 0:
            self._bookmark_view.update_for_page(current_page)

        # We've got the document, so if we're a shared activity, offer it
        try:
            if self.get_shared():
                self.watch_for_tubes()
                self._share_document()
        except Exception, e:
            _logger.debug('Sharing failed: %s', e)

    def _update_toolbars(self):
        self._view_toolbar._update_zoom_buttons()
        if self._view.can_highlight():
            self._highlight.show()
        if self._view.can_do_text_to_speech():
            import speech
            from speechtoolbar import SpeechToolbar
            if speech.supported:
                self.speech_toolbar = SpeechToolbar(self)
                self.speech_toolbar_button.set_page(self.speech_toolbar)
                self.speech_toolbar_button.show()

    def _share_document(self):
        """Share the document."""
        # FIXME: should ideally have the fileserver listen on a Unix socket
        # instead of IPv4 (might be more compatible with Rainbow)

        _logger.debug('Starting HTTP server on port %d', self.port)

        self._fileserver = ReadHTTPServer(("", self.port),
                                          self._tempfile,
                                          self.create_metadata_file)

        # Make a tube for it
        chan = self.shared_activity.telepathy_tubes_chan
        iface = chan[telepathy.CHANNEL_TYPE_TUBES]
        self._fileserver_tube_id = iface.OfferStreamTube(
            READ_STREAM_SERVICE,
            {},
            telepathy.SOCKET_ADDRESS_TYPE_IPV4,
            ('127.0.0.1', dbus.UInt16(self.port)),
            telepathy.SOCKET_ACCESS_CONTROL_LOCALHOST, 0)

    def create_metadata_file(self):
        # store the metadata in a json file
        self._save_bookmars_in_metadata()
        metadata_file_path = self._tempfile + '.json'

        shared_metadata = {}
        for key in self.metadata.keys():
            if key not in ['preview', 'cover_image']:
                shared_metadata[str(key)] = self.metadata[key]
        logging.error('save metadata in %s', metadata_file_path)
        with open(metadata_file_path, 'w') as json_file:
            json.dump(shared_metadata, json_file)
        return metadata_file_path

    def watch_for_tubes(self):
        """Watch for new tubes."""
        tubes_chan = self.shared_activity.telepathy_tubes_chan

        tubes_chan[telepathy.CHANNEL_TYPE_TUBES].connect_to_signal(
            'NewTube', self._new_tube_cb)
        tubes_chan[telepathy.CHANNEL_TYPE_TUBES].ListTubes(
            reply_handler=self._list_tubes_reply_cb,
            error_handler=self._list_tubes_error_cb)

    def _new_tube_cb(self, tube_id, initiator, tube_type, service, params,
                     state):
        """Callback when a new tube becomes available."""
        _logger.debug('New tube: ID=%d initator=%d type=%d service=%s '
                      'params=%r state=%d', tube_id, initiator, tube_type,
                      service, params, state)
        if self._view is None and service == READ_STREAM_SERVICE:
            _logger.debug('I could download from that tube')
            self.unused_download_tubes.add(tube_id)
            # if no download is in progress, let's fetch the document
            if self._want_document:
                GObject.idle_add(self._get_document)

    def _list_tubes_reply_cb(self, tubes):
        """Callback when new tubes are available."""
        for tube_info in tubes:
            self._new_tube_cb(*tube_info)

    def _list_tubes_error_cb(self, e):
        """Handle ListTubes error by logging."""
        _logger.error('ListTubes() failed: %s', e)

    def _shared_cb(self, activityid):
        """Callback when activity shared.

        Set up to share the document.

        """
        # We initiated this activity and have now shared it, so by
        # definition we have the file.
        _logger.debug('Activity became shared')
        self.watch_for_tubes()
        self._share_document()

    def _view_selection_changed_cb(self, view):
        self._edit_toolbar.copy.props.sensitive = view.get_has_selection()
        if self._view.can_highlight():
            in_bounds, _highlight_found = self._view.in_highlight()
            self._highlight.props.sensitive = \
                view.get_has_selection() or in_bounds

            self._highlight.handler_block(self._highlight_id)
            self._highlight.set_active(in_bounds)
            self._highlight.handler_unblock(self._highlight_id)

    def _edit_toolbar_copy_cb(self, button):
        self._view.copy()

    def _key_press_event_cb(self, widget, event):
        if self.activity_button.page.title.has_focus() or \
                self._num_page_entry.has_focus():
            return False
        keyname = Gdk.keyval_name(event.keyval)
        if keyname == 'c' and event.state & Gdk.ModifierType.CONTROL_MASK:
            self._view.copy()
            return True
        elif keyname == 'KP_Home':
            # FIXME: refactor later to self.zoom_in()
            self._view_toolbar.zoom_in()
            return True
        elif keyname == 'KP_End':
            self._view_toolbar.zoom_out()
            return True
        elif keyname == 'Home':
            self._view.scroll(Gtk.ScrollType.START, False)
            return True
        elif keyname == 'End':
            self._view.scroll(Gtk.ScrollType.END, False)
            return True
        elif keyname == 'Page_Up' or keyname == 'KP_Page_Up':
            self._view.scroll(Gtk.ScrollType.PAGE_BACKWARD, False)
            return True
        elif keyname == 'Page_Down' or keyname == 'KP_Page_Down':
            self._view.scroll(Gtk.ScrollType.PAGE_FORWARD, False)
            return True
        elif keyname == 'Up' or keyname == 'KP_Up':
            self._view.scroll(Gtk.ScrollType.STEP_BACKWARD, False)
            return True
        elif keyname == 'Down' or keyname == 'KP_Down':
            self._view.scroll(Gtk.ScrollType.STEP_FORWARD, False)
            return True
        elif keyname == 'Left' or keyname == 'KP_Left':
            self._view.scroll(Gtk.ScrollType.STEP_BACKWARD, True)
            return True
        elif keyname == 'Right' or keyname == 'KP_Right':
            self._view.scroll(Gtk.ScrollType.STEP_FORWARD, True)
            return True
        else:
            return False

    def _key_release_event_cb(self, widget, event):
        # keyname = Gdk.keyval_name(event.keyval)
        # _logger.debug("Keyname Release: %s, time: %s", keyname, event.time)
        return False

    def __view_toolbar_needs_update_size_cb(self, view_toolbar):
        if hasattr(self._view, 'update_view_size'):
            self._view.update_view_size(self._scrolled)
        else:
            return False  # No need again to run this again and

    def __view_toolbar_go_fullscreen_cb(self, view_toolbar):
        self.fullscreen()

    def _added_bookmark_cb(self, bookmarkmanager, page, title):
        logging.error('Bookmark added page %d', page)
        title = _('%s (Page %d)') % (title, page)
        color = profile.get_color().to_string()
        owner = profile.get_nick_name()
        thumb = self._get_screenshot()
        self._add_link_totray(page, thumb, color, title, owner, 1)
        bookmarkmanager.add_bookmark_preview(page - 1, thumb)

    def _removed_bookmark_cb(self, bookmarkmanager, page):
        logging.error('Bookmark removed page %d', page)
        # remove button from tray
        for button in self.tray.get_children():
            if button.page == page:
                self.tray.remove_item(button)
        if len(self.tray.get_children()) == 0:
            self.tray.hide()
            self._view_toolbar.traybutton.props.active = False

    def _add_link_totray(self, page, buf, color, title, owner, local):
        ''' add a link to the tray '''
        item = LinkButton(buf, color, title, owner, page, local)
        item.connect('clicked', self._bookmark_button_clicked_cb, page)
        item.connect('go_to_bookmark', self._bookmark_button_clicked_cb)
        item.connect('remove_link', self._bookmark_button_removed_cb)
        self.tray.show()
        self.tray.add_item(item)
        item.show()
        self._view_toolbar.traybutton.props.active = True

    def _bookmark_button_clicked_cb(self, button, page):
        num_page = int(page) - 1
        self._view.set_current_page(num_page)
        if not button.have_preview():
            # HACK: we need take the screenshot after the page changed
            # but we don't have a event yet, Evince model have a event
            # we need check the differnt backends and implement
            # in all the backends.
            GObject.timeout_add_seconds(2, self._update_preview, button, page)

    def _update_preview(self, button, page):
        thumb = self._get_screenshot()
        self._bookmarkmanager.add_bookmark_preview(page - 1, thumb)
        button.set_image(thumb)
        return False

    def _bookmark_button_removed_cb(self, button, page):
        num_page = int(page) - 1
        self._bookmark_view.del_bookmark(num_page)

    def _get_screenshot(self):
        """Copied from activity.get_preview()
        """
        if self.canvas is None or not hasattr(self.canvas, 'get_window'):
            return None

        window = self.canvas.get_window()
        if window is None:
            return None

        alloc = self.canvas.get_allocation()

        dummy_cr = Gdk.cairo_create(window)
        target = dummy_cr.get_target()
        canvas_width, canvas_height = alloc.width, alloc.height
        screenshot_surface = target.create_similar(cairo.CONTENT_COLOR,
                                                   canvas_width, canvas_height)
        del dummy_cr, target

        cr = cairo.Context(screenshot_surface)
        r, g, b, a_ = style.COLOR_PANEL_GREY.get_rgba()
        cr.set_source_rgb(r, g, b)
        cr.paint()
        self.canvas.draw(cr)
        del cr

        preview_width, preview_height = style.zoom(100), style.zoom(80)
        preview_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                             preview_width, preview_height)
        cr = cairo.Context(preview_surface)

        scale_w = preview_width * 1.0 / canvas_width
        scale_h = preview_height * 1.0 / canvas_height
        scale = min(scale_w, scale_h)

        translate_x = int((preview_width - (canvas_width * scale)) / 2)
        translate_y = int((preview_height - (canvas_height * scale)) / 2)

        cr.translate(translate_x, translate_y)
        cr.scale(scale, scale)

        cr.set_source_rgba(1, 1, 1, 0)
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.paint()
        cr.set_source_surface(screenshot_surface)
        cr.paint()

        preview_str = StringIO.StringIO()
        preview_surface.write_to_png(preview_str)
        return preview_str.getvalue()
