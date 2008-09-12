# Copyright (C) 2007, Red Hat, Inc.
# Copyright (C) 2007 Collabora Ltd. <http://www.collabora.co.uk/>
# Copyright 2008 One Laptop Per Child
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

import dbus
import evince
import gobject
import gtk
import telepathy

from sugar.activity import activity
from sugar import network

from sugar.datastore import datastore

from readtoolbar import EditToolbar, ReadToolbar, ViewToolbar

_HARDWARE_MANAGER_INTERFACE = 'org.laptop.HardwareManager'
_HARDWARE_MANAGER_SERVICE = 'org.laptop.HardwareManager'
_HARDWARE_MANAGER_OBJECT_PATH = '/org/laptop/HardwareManager'

_TOOLBAR_READ = 2

_logger = logging.getLogger('read-activity')

def _get_screen_dpi():
    xft_dpi = gtk.settings_get_default().get_property('gtk-xft-dpi')
    print 'Setting dpi to %f' % (float(xft_dpi / 1024))
    return float(xft_dpi / 1024)


class ReadHTTPRequestHandler(network.ChunkedGlibHTTPRequestHandler):
    """HTTP Request Handler for transferring document while collaborating.

    RequestHandler class that integrates with Glib mainloop. It writes
    the specified file to the client in chunks, returning control to the
    mainloop between chunks.

    """
    def translate_path(self, path):
        """Return the filepath to the shared document."""
        return self.server.filepath


class ReadHTTPServer(network.GlibTCPServer):
    """HTTP Server for transferring document while collaborating."""
    def __init__(self, server_address, filepath):
        """Set up the GlibTCPServer with the ReadHTTPRequestHandler.

        filepath -- path to shared document to be served.
        """
        self.filepath = filepath
        network.GlibTCPServer.__init__(self, server_address,
                                       ReadHTTPRequestHandler)


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

class ReadActivity(activity.Activity):
    """The Read sugar activity."""
    def __init__(self, handle):
        activity.Activity.__init__(self, handle)

        evince.evince_embed_init()

        self._document = None
        self._fileserver = None
        self._object_id = handle.object_id

        self.connect('key-press-event', self._key_press_event_cb)
        self.connect('key-release-event', self._key_release_event_cb)

        _logger.debug('Starting Read...')
        
        evince.job_queue_init()
        self._view = evince.View()
        self._view.set_screen_dpi(_get_screen_dpi())
        self._view.connect('notify::has-selection',
                           self._view_notify_has_selection_cb)

        toolbox = activity.ActivityToolbox(self)

        self._edit_toolbar = EditToolbar(self._view)
        self._edit_toolbar.undo.props.visible = False
        self._edit_toolbar.redo.props.visible = False
        self._edit_toolbar.separator.props.visible = False
        self._edit_toolbar.copy.set_sensitive(False)
        self._edit_toolbar.copy.connect('clicked', self._edit_toolbar_copy_cb)
        self._edit_toolbar.paste.props.visible = False
        toolbox.add_toolbar(_('Edit'), self._edit_toolbar)
        self._edit_toolbar.show()

        self._read_toolbar = ReadToolbar(self._view)
        toolbox.add_toolbar(_('Read'), self._read_toolbar)
        self._read_toolbar.show()

        self._view_toolbar = ViewToolbar(self._view)
        self._view_toolbar.connect('needs-update-size',
                self.__view_toolbar_needs_update_size_cb)
        self._view_toolbar.connect('go-fullscreen',
                self.__view_toolbar_go_fullscreen_cb)
        toolbox.add_toolbar(_('View'), self._view_toolbar)
        self._view_toolbar.show()

        self.set_toolbox(toolbox)
        toolbox.show()

        scrolled = gtk.ScrolledWindow()
        scrolled.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled.props.shadow_type = gtk.SHADOW_NONE

        scrolled.add(self._view)
        self._view.show()
                
        self.set_canvas(scrolled)
        scrolled.show()

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
                scrolled.props.vadjustment.connect("value-changed",
                                                   self._user_action_cb)
                scrolled.props.hadjustment.connect("value-changed",
                                                   self._user_action_cb)
                self.connect("focus-in-event", self._focus_in_event_cb)
                self.connect("focus-out-event", self._focus_out_event_cb)
                self.connect("notify::active", self._now_active_cb)

                logging.debug('Suspend on idle enabled')
            except dbus.DBusException, e:
                _logger.info(
                    'Hardware manager service not found, no idle suspend.')
        else:
            logging.debug('Suspend on idle disabled')

        self.connect("shared", self._shared_cb)

        h = hash(self._activity_id)
        self.port = 1024 + (h % 64511)

        if handle.uri:
            self._load_document(handle.uri)

        # start on the read toolbar
        self.toolbox.set_current_toolbar(_TOOLBAR_READ)

        if self._shared_activity:
            # We're joining
            if self.get_shared():
                # Already joined for some reason, just get the document
                self._joined_cb(self)
            else:
                # Wait for a successful join before trying to get the document
                self.connect("joined", self._joined_cb)
        # uncomment this and adjust the path for easier testing
        #else:
        #    self._load_document('file:///home/smcv/tmp/test.pdf')

    def _now_active_cb(self, widget, pspec):
        if self.props.active:
            # Now active, start initial suspend timeout
            if self._idle_timer > 0:
                gobject.source_remove(self._idle_timer)
            self._idle_timer = gobject.timeout_add(15000, self._suspend_cb)
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
            gobject.source_remove(self._idle_timer)
        self._idle_timer = gobject.timeout_add(5000, self._suspend_cb)

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
        tempfile = os.path.join(self.get_activity_root(), 'instance',
                                'tmp%i' % time.time())
        os.link(file_path, tempfile)
        self._tempfile = tempfile
        self._load_document('file://' + self._tempfile)

        # FIXME: This should obviously be fixed properly
        gobject.timeout_add(1000, self.__view_toolbar_needs_update_size_cb,
            None)

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
                        str(self._document.get_page_cache().get_current_page())

            self.metadata['Read_zoom'] = str(self._view.props.zoom)

            if self._view.props.sizing_mode == evince.SIZING_BEST_FIT:
                self.metadata['Read_sizing_mode'] = "best-fit"
            elif self._view.props.sizing_mode == evince.SIZING_FREE:
                self.metadata['Read_sizing_mode'] = "free"
            elif self._view.props.sizing_mode == evince.SIZING_FIT_WIDTH:
                self.metadata['Read_sizing_mode'] = "fit-width"
            else:
                logging.error("Don't know how to save sizing_mode state '%s'" %
                              self._view.props.sizing_mode)
                self.metadata['Read_sizing_mode'] = "fit-width"

            self.metadata['Read_search'] = \
                    self._edit_toolbar._search_entry.props.text

        except Exception, e:
            logging.error('write_file(): %s', e)

        self.metadata['Read_search'] = \
                self._edit_toolbar._search_entry.props.text

        os.link(self._tempfile, file_path)

        if self._close_requested:
            _logger.debug("Removing temp file %s because we will close",
                          self._tempfile)
            os.unlink(self._tempfile)
            self._tempfile = None

    def can_close(self):
        """Prepare to cleanup on closing.
        
        Called from self.close()
        """
        self._close_requested = True
        return True

    def _download_result_cb(self, getter, tempfile, suggested_name, tube_id):
        if self._download_content_type == 'text/html':
            # got an error page instead
            self._download_error_cb(getter, 'HTTP Error', tube_id)
            return

        del self.unused_download_tubes

        self._tempfile = tempfile
        file_path = os.path.join(self.get_activity_root(), 'instance',
                                    '%i' % time.time())
        _logger.debug("Saving file %s to datastore...", file_path)
        os.link(tempfile, file_path)
        self._jobject.file_path = file_path
        datastore.write(self._jobject, transfer_ownership=True)

        _logger.debug("Got document %s (%s) from tube %u",
                      tempfile, suggested_name, tube_id)
        self._load_document("file://%s" % tempfile)
        self.save()

    def _download_progress_cb(self, getter, bytes_downloaded, tube_id):
        # FIXME: Draw a progress bar
        if self._download_content_length > 0:
            _logger.debug("Downloaded %u of %u bytes from tube %u...",
                          bytes_downloaded, self._download_content_length, 
                          tube_id)
        else:
            _logger.debug("Downloaded %u bytes from tube %u...",
                          bytes_downloaded, tube_id)

    def _download_error_cb(self, getter, err, tube_id):
        _logger.debug("Error getting document from tube %u: %s",
                      tube_id, err)
        self._want_document = True
        self._download_content_length = 0
        self._download_content_type = None
        gobject.idle_add(self._get_document)

    def _download_document(self, tube_id, path):
        # FIXME: should ideally have the CM listen on a Unix socket
        # instead of IPv4 (might be more compatible with Rainbow)
        chan = self._shared_activity.telepathy_tubes_chan
        iface = chan[telepathy.CHANNEL_TYPE_TUBES]
        addr = iface.AcceptStreamTube(tube_id,
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
        port = int(addr[1])

        getter = ReadURLDownloader("http://%s:%d/document"
                                           % (addr[0], port))
        getter.connect("finished", self._download_result_cb, tube_id)
        getter.connect("progress", self._download_progress_cb, tube_id)
        getter.connect("error", self._download_error_cb, tube_id)
        _logger.debug("Starting download to %s...", path)
        getter.start(path)
        self._download_content_length = getter.get_content_length()
        self._download_content_type = getter.get_content_type()
        return False

    def _get_document(self):
        if not self._want_document:
            return False

        # Assign a file path to download if one doesn't exist yet
        if not self._jobject.file_path:
            path = os.path.join(self.get_activity_root(), 'instance',
                                'tmp%i' % time.time())
        else:
            path = self._jobject.file_path

        # Pick an arbitrary tube we can try to download the document from
        try:
            tube_id = self.unused_download_tubes.pop()
        except (ValueError, KeyError), e:
            _logger.debug('No tubes to get the document from right now: %s',
                          e)
            return False

        # Avoid trying to download the document multiple times at once
        self._want_document = False
        gobject.idle_add(self._download_document, tube_id, path)
        return False

    def _joined_cb(self, also_self):
        """Callback for when a shared activity is joined.

        Get the shared document from another participant.
        """
        self.watch_for_tubes()
        gobject.idle_add(self._get_document)

    def _load_document(self, filepath):
        """Load the specified document and set up the UI.

        filepath -- string starting with file://
        
        """
        self._document = evince.factory_get_document(filepath)
        self._want_document = False
        self._view.set_document(self._document)
        self._edit_toolbar.set_document(self._document)
        self._read_toolbar.set_document(self._document)

        if not self.metadata['title_set_by_user'] == '1':
            info = self._document.get_info()
            if info and info.title:
                self.metadata['title'] = info.title

        current_page = int(self.metadata.get('Read_current_page', '0'))
        self._document.get_page_cache().set_current_page(current_page)

        sizing_mode = self.metadata.get('Read_sizing_mode', 'fit-width')
        logging.debug('Found sizing mode: %s', sizing_mode)
        if sizing_mode == "best-fit":
            self._view.props.sizing_mode = evince.SIZING_BEST_FIT
            self._view.update_view_size(self.canvas)
        elif sizing_mode == "free":
            self._view.props.sizing_mode = evince.SIZING_FREE
            self._view.props.zoom = float(self.metadata.get('Read_zoom', '1.0'))
            logging.debug('Set zoom to %f', self._view.props.zoom)
        elif sizing_mode == "fit-width":
            self._view.props.sizing_mode = evince.SIZING_FIT_WIDTH
            self._view.update_view_size(self.canvas)
        else:
            # this may happen when we get a document from a buddy with a later
            # version of Read, for example.
            _logger.warning("Unknown sizing_mode state '%s'", sizing_mode)
            if self.metadata.get('Read_zoom', None) is not None:
                self._view.props.zoom = float(self.metadata['Read_zoom'])

        self._view_toolbar._update_zoom_buttons()

        self._edit_toolbar._search_entry.props.text = \
                                self.metadata.get('Read_search', '')

        # We've got the document, so if we're a shared activity, offer it
        try:
            if self.get_shared():
                self.watch_for_tubes()
                self._share_document()
        except Exception, e:
            logging.debug('Sharing failed: %s', e)

    def _share_document(self):
        """Share the document."""
        # FIXME: should ideally have the fileserver listen on a Unix socket
        # instead of IPv4 (might be more compatible with Rainbow)

        logging.debug('Starting HTTP server on port %d', self.port)
        self._fileserver = ReadHTTPServer(("", self.port),
            self._tempfile)

        # Make a tube for it
        chan = self._shared_activity.telepathy_tubes_chan
        iface = chan[telepathy.CHANNEL_TYPE_TUBES]
        self._fileserver_tube_id = iface.OfferStreamTube(READ_STREAM_SERVICE,
                {},
                telepathy.SOCKET_ADDRESS_TYPE_IPV4,
                ('127.0.0.1', dbus.UInt16(self.port)),
                telepathy.SOCKET_ACCESS_CONTROL_LOCALHOST, 0)

    def watch_for_tubes(self):
        """Watch for new tubes."""
        tubes_chan = self._shared_activity.telepathy_tubes_chan

        tubes_chan[telepathy.CHANNEL_TYPE_TUBES].connect_to_signal('NewTube',
            self._new_tube_cb)
        tubes_chan[telepathy.CHANNEL_TYPE_TUBES].ListTubes(
            reply_handler=self._list_tubes_reply_cb,
            error_handler=self._list_tubes_error_cb)

    def _new_tube_cb(self, tube_id, initiator, tube_type, service, params,
                     state):
        """Callback when a new tube becomes available."""
        _logger.debug('New tube: ID=%d initator=%d type=%d service=%s '
                      'params=%r state=%d', tube_id, initiator, tube_type,
                      service, params, state)
        if self._document is None and service == READ_STREAM_SERVICE:
            _logger.debug('I could download from that tube')
            self.unused_download_tubes.add(tube_id)
            # if no download is in progress, let's fetch the document
            if self._want_document:
                gobject.idle_add(self._get_document)

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

    def _view_notify_has_selection_cb(self, view, pspec):
        self._edit_toolbar.copy.set_sensitive(self._view.props.has_selection)

    def _edit_toolbar_copy_cb(self, button):
        self._view.copy()

    def _key_press_event_cb(self, widget, event):
        keyname = gtk.gdk.keyval_name(event.keyval)
        logging.debug("Keyname Press: %s, time: %s", keyname, event.time)
        if keyname == 'c' and event.state & gtk.gdk.CONTROL_MASK:
            self._view.copy()
            return True
        elif keyname == 'KP_Home':
            # FIXME: refactor later to self.zoom_in()
            self._view_toolbar.zoom_in()
            return True
        elif keyname == 'KP_End':
            self._view_toolbar.zoom_out()
            return True
        else:
            return False

    def _key_release_event_cb(self, widget, event):
        keyname = gtk.gdk.keyval_name(event.keyval)
        logging.debug("Keyname Release: %s, time: %s", keyname, event.time)

    def __view_toolbar_needs_update_size_cb(self, view_toolbar):
        self._view.update_view_size(self.canvas)

    def __view_toolbar_go_fullscreen_cb(self, view_toolbar):
        self.fullscreen()
