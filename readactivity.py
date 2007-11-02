# Copyright (C) 2007, Red Hat, Inc.
# Copyright (C) 2007 Collabora Ltd. <http://www.collabora.co.uk/>
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
import tempfile
import time
from gettext import gettext as _

import dbus
import evince
import gobject
import gtk
import hippo
import telepathy

from sugar.activity import activity
from sugar import network

from readtoolbar import EditToolbar, ReadToolbar, ViewToolbar

_HARDWARE_MANAGER_INTERFACE = 'org.laptop.HardwareManager'
_HARDWARE_MANAGER_SERVICE = 'org.laptop.HardwareManager'
_HARDWARE_MANAGER_OBJECT_PATH = '/org/laptop/HardwareManager'

_TOOLBAR_READ = 2

_logger = logging.getLogger('read-activity')

class ReadHTTPRequestHandler(network.ChunkedGlibHTTPRequestHandler):
    def translate_path(self, path):
        return self.server._filepath

class ReadHTTPServer(network.GlibTCPServer):
    def __init__(self, server_address, filepath):
        self._filepath = filepath
        network.GlibTCPServer.__init__(self, server_address, ReadHTTPRequestHandler)

READ_STREAM_SERVICE = 'read-activity-http'

class ReadActivity(activity.Activity):
    def __init__(self, handle):
        activity.Activity.__init__(self, handle)
        self._document = None
        self._filepath = None
        self._fileserver = None

        self.connect('key-press-event', self._key_press_event_cb)
        self.connect('key-release-event', self._key_release_event_cb)

        _logger.debug('Starting Read...')
        
        evince.job_queue_init()
        self._view = evince.View()
        self._view.connect('notify::has-selection', self._view_notify_has_selection_cb)

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

        if os.path.exists(os.path.expanduser("~/ebook-enable-sleep")):
            try:
                bus = dbus.SystemBus()
                proxy = bus.get_object(_HARDWARE_MANAGER_SERVICE,
                                       _HARDWARE_MANAGER_OBJECT_PATH)
                self._service = dbus.Interface(proxy, _HARDWARE_MANAGER_INTERFACE)
                scrolled.props.vadjustment.connect("value-changed", self._user_action_cb)
                scrolled.props.hadjustment.connect("value-changed", self._user_action_cb)
                self.connect("focus-in-event", self._focus_in_event_cb)
                self.connect("focus-out-event", self._focus_out_event_cb)
                self.connect("notify::active", self._now_active_cb)
            except dbus.DBusException, e:
                _logger.info('Hardware manager service not found, no idle suspend.')

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
        self._sleep_inhibit = False
        self._user_action_cb(self)

    def _focus_out_event_cb(self, widget, event):
        self._sleep_inhibit = True

    def _user_action_cb(self, widget):
        if self._idle_timer > 0:
            gobject.source_remove(self._idle_timer)
        self._idle_timer = gobject.timeout_add(5000, self._suspend_cb)

    def _suspend_cb(self):
        # If the machine has been idle for 5 seconds, suspend
        self._idle_timer = 0
        if not self._sleep_inhibit:
            self._service.set_kernel_suspend()
        return False

    def read_file(self, file_path):
        """Load a file from the datastore on activity start"""
        _logger.debug('ReadActivity.read_file: %s', file_path)
        self._load_document('file://' + file_path)

    def write_file(self, file_path):
        """We only save meta data, not the document itself.
        current page, view settings, search text."""
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

            self.metadata['Read_search'] = self._edit_toolbar._search_entry.props.text
        except Exception, e:
            logging.error('write_file(): %s', e)

        self.metadata['Read_search'] = self._edit_toolbar._search_entry.props.text

    def _download_result_cb(self, getter, tempfile, suggested_name, tube_id):
        del self.unused_download_tubes

        _logger.debug("Got document %s (%s) from tube %u",
                      tempfile, suggested_name, tube_id)
        self._load_document("file://%s" % tempfile)
        _logger.debug("Saving %s to datastore...", tempfile)
        self.save()

    def _download_progress_cb(self, getter, bytes_downloaded, tube_id):
        # FIXME: signal the expected size somehow, so we can draw a progress
        # bar
        _logger.debug("Downloaded %u bytes from tube %u...",
                      bytes_downloaded, tube_id)

    def _download_error_cb(self, getter, err, tube_id):
        _logger.debug("Error getting document from tube %u: %s",
                      tube_id, err)
        self._want_document = True
        gobject.idle_add(self._get_document)

    def _download_document(self, tube_id):
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

        getter = network.GlibURLDownloader("http://%s:%d/document"
                                           % (addr[0], port))
        getter.connect("finished", self._download_result_cb, tube_id)
        getter.connect("progress", self._download_progress_cb, tube_id)
        getter.connect("error", self._download_error_cb, tube_id)
        _logger.debug("Starting download to %s...", self._jobject.file_path)
        # Avoid trying to download the document multiple times at once
        self._want_document = False
        getter.start(self._jobject.file_path)
        return False

    def _get_document(self):
        if not self._want_document:
            return False

        # Assign a file path to download if one doesn't exist yet
        if not self._jobject.file_path:
            self._jobject.file_path = os.path.join(tempfile.gettempdir(), '%i' % time.time())
            self._owns_file = True

        next_buddy = None
        # Pick an arbitrary tube we can try to download the document from
        try:
            tube_id = self.unused_download_tubes.pop()
        except (ValueError, KeyError), e:
            _logger.debug('No tubes to get the document from right now: %s',
                          e)
            return False

        gobject.idle_add(self._download_document, tube_id)
        return False

    def _joined_cb(self, also_self):
        self.watch_for_tubes()
        gobject.idle_add(self._get_document)

    def _load_document(self, filepath):
        self._document = evince.factory_get_document(filepath)
        self._want_document = False
        self._view.set_document(self._document)
        self._edit_toolbar.set_document(self._document)
        self._read_toolbar.set_document(self._document)

        if not self.metadata['title_set_by_user'] == '1':
            info = self._document.get_info()
            if info and info.title:
                self.metadata['title'] = info.title

        import urllib
        garbage, path = urllib.splittype(filepath)
        garbage, path = urllib.splithost(path or "")
        path, garbage = urllib.splitquery(path or "")
        path, garbage = urllib.splitattr(path or "")
        self._filepath = os.path.abspath(path)

        current_page = int(self.metadata.get('Read_current_page', '0'))
        self._document.get_page_cache().set_current_page(current_page)

        sizing_mode = self.metadata.get('Read_sizing_mode', 'fit-width')
        if sizing_mode == "best-fit":
            self._view.props.sizing_mode = evince.SIZING_BEST_FIT
        elif sizing_mode == "free":
            self._view.props.sizing_mode = evince.SIZING_FREE
            self._view.props.zoom = float(self.metadata.get('Read_zoom', '1.0'))
        elif sizing_mode == "fit-width":
            self._view.props.sizing_mode = evince.SIZING_FIT_WIDTH
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
        if self.get_shared():
            self.watch_for_tubes()
            self._share_document()

    def _share_document(self):
        # FIXME: should ideally have the fileserver listen on a Unix socket
        # instead of IPv4 (might be more compatible with Rainbow)
        self._fileserver = ReadHTTPServer(("", self.port), self._filepath)
        # Make a tube for it
        chan = self._shared_activity.telepathy_tubes_chan
        iface = chan[telepathy.CHANNEL_TYPE_TUBES]
        self._fileserver_tube_id = iface.OfferStreamTube(READ_STREAM_SERVICE,
                {},
                telepathy.SOCKET_ADDRESS_TYPE_IPV4,
                ('127.0.0.1', dbus.UInt16(self.port)),
                telepathy.SOCKET_ACCESS_CONTROL_LOCALHOST, 0)

    def watch_for_tubes(self):
        tubes_chan = self._shared_activity.telepathy_tubes_chan

        tubes_chan[telepathy.CHANNEL_TYPE_TUBES].connect_to_signal('NewTube',
            self._new_tube_cb)
        tubes_chan[telepathy.CHANNEL_TYPE_TUBES].ListTubes(
            reply_handler=self._list_tubes_reply_cb,
            error_handler=self._list_tubes_error_cb)

    def _new_tube_cb(self, tube_id, initiator, tube_type, service, params,
                     state):
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
        for tube_info in tubes:
            self._new_tube_cb(*tube_info)

    def _list_tubes_error_cb(self, e):
        _logger.error('ListTubes() failed: %s', e)

    def _shared_cb(self, activity):
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

    def _key_release_event_cb(self, widget, event):
        keyname = gtk.gdk.keyval_name(event.keyval)
        logging.debug("Keyname Release: %s, time: %s", keyname, event.time)

