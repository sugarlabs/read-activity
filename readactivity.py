# Copyright (C) 2007, Red Hat, Inc.
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
from gettext import gettext as _

import gtk, gobject
import evince
import hippo
import os
import tempfile
import time

from sugar.activity import activity
from sugar import network

from readtoolbar import ReadToolbar

class ReadHTTPRequestHandler(network.ChunkedGlibHTTPRequestHandler):
    def translate_path(self, path):
        return self.server._filepath

class ReadHTTPServer(network.GlibTCPServer):
    def __init__(self, server_address, filepath):
        self._filepath = filepath
        network.GlibTCPServer.__init__(self, server_address, ReadHTTPRequestHandler)

class ReadActivity(activity.Activity):
    def __init__(self, handle):
        activity.Activity.__init__(self, handle)
        self._document = None
        self._filepath = None
        self._fileserver = None

        logging.debug('Starting read...')
        self.set_title(_('Read Activity'))
        
        evince.job_queue_init()
        self._view = evince.View()

        toolbox = activity.ActivityToolbox(self)

        self._toolbar = ReadToolbar(self._view)
        toolbox.add_toolbar(_('View'), self._toolbar)
        self._toolbar.show()

        self.set_toolbox(toolbox)
        toolbox.show()

        scrolled = gtk.ScrolledWindow()
        scrolled.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled.props.shadow_type = gtk.SHADOW_NONE

        scrolled.add(self._view)
        self._view.show()
                
        self.set_canvas(scrolled)
        scrolled.show()

        self.connect("shared", self._shared_cb)

        h = hash(self._activity_id)
        self.port = 1024 + (h % 64511)

        if handle.uri:
            self._load_document(handle.uri)

        if self._shared_activity or not self._document:
            self._tried_buddies = []
            if self.get_shared():
                # Already joined for some reason, just get the document
                self._get_document()
            else:
                # Wait for a successful join before trying to get the document
                self.connect("joined", self._joined_cb)

    def read_file(self, file_path):
        """Load a file from the datastore on activity start"""
        logging.debug('ReadActivity.read_file: ' + file_path)
        self._load_document('file://' + file_path)

    def write_file(self, file_path):
        # Don't do anything here, file has already been saved
        pass

    def _download_result_cb(self, getter, tempfile, suggested_name, buddy):
        del self._tried_buddies
        logging.debug("Got document %s (%s) from %s (%s)" % (tempfile, suggested_name, buddy.props.nick, buddy.props.ip4_address))
        self._load_document("file://%s" % tempfile)
        logging.debug("Saving %s to datastore..." % tempfile)
        self.save()

    def _download_error_cb(self, getter, err, buddy):
        logging.debug("Error getting document from %s (%s): %s" % (buddy.props.nick, buddy.props.ip4_address, err))
        self._tried_buddies.append(buddy)
        gobject.idle_add(self._get_document)

    def _download_document(self, buddy):
        getter = network.GlibURLDownloader("http://%s:%d/document" % (buddy.props.ip4_address, self.port))
        getter.connect("finished", self._download_result_cb, buddy)
        getter.connect("error", self._download_error_cb, buddy)
        logging.debug("Starting download to %s..." % self._jobject.file_path)
        getter.start(self._jobject.file_path)
        return False

    def _get_document(self):
        # Assign a file path to download if one doesn't exist yet
        if not self._jobject.file_path:
            self._jobject.file_path = os.path.join(tempfile.gettempdir(), '%i' % time.time())
            self._owns_file = True

        next_buddy = None
        # Find the next untried buddy with an IP4 address we can try to
        # download the document from
        for buddy in self._shared_activity.get_joined_buddies():
            if buddy.props.owner:
                continue
            if not buddy in self._tried_buddies:
                if buddy.props.ip4_address:
                    next_buddy = buddy
                    break

        if not next_buddy:
            logging.debug("Couldn't find a buddy to get the document from.")
            return False

        gobject.idle_add(self._download_document, buddy)
        return False

    def _joined_cb(self, activity):
        gobject.idle_add(self._get_document)

    def _load_document(self, filepath):
        if self._document:
            del self._document
        self._document = evince.factory_get_document(filepath)
        self._view.set_document(self._document)
        self._toolbar.set_document(self._document)
        title = _("Read Activity")
        info = self._document.get_info()
        if info and info.title:
            title += ": " + info.title
        self.set_title(title)

        import urllib
        garbage, path = urllib.splittype(filepath)
        garbage, path = urllib.splithost(path or "")
        path, garbage = urllib.splitquery(path or "")
        path, garbage = urllib.splitattr(path or "")
        self._filepath = os.path.abspath(path)

        # When we get the document, start up our sharing services
        if self.get_shared():
            self._start_shared_services()

    def _start_shared_services(self):
        self._fileserver = ReadHTTPServer(("", self.port), self._filepath)

    def _shared_cb(self, activity):
        self._start_shared_services()
