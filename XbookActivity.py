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

from sugar.activity import activity
from sugar.p2p import network

from xbooktoolbar import XbookToolbar

_READ_PORT = 17982

class ReadHTTPRequestHandler(network.ChunkedGlibHTTPRequestHandler):
    def translate_path(self, path):
        return self.server._filepath

class ReadHTTPServer(network.GlibTCPServer):
    def __init__(self, server_address, filepath):
        self._filepath = filepath
        network.GlibTCPServer.__init__(self, server_address, ReadHTTPRequestHandler);

class XbookActivity(activity.Activity):
    def __init__(self, handle):
        activity.Activity.__init__(self, handle)
        self._document = None
        self._filepath = None
        self._fileserver = None

        logging.debug('Starting xbook...')
        self.set_title(_('Read Activity'))
        
        evince.job_queue_init()
        self._view = evince.View()

        toolbox = activity.ActivityToolbox(self)

        self._toolbar = XbookToolbar(self._view)
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

        handle.uri = "file:///home/dcbw/i1040nre.pdf"

        if handle.uri:
            self._load_document(handle.uri)
        elif self._shared_activity:
            self._tried_buddies = []
            if self.get_shared():
                # Already joined for some reason, just get the document
                self._get_document()
            else:
                # Wait for a successful join before trying to get the document
                self.connect("joined", self._joined_cb)

    def _download_result_cb(self, getter, tempfile, suggested_name, buddy):
        del self._tried_buddies
        logging.debug("Got document %s (%s) from %s (%s)" % (tempfile, suggested_name, buddy.props.nick, buddy.props.ip4_address))
        import shutil
        dest = os.path.join(os.path.expanduser("~"), suggested_name)
        shutil.copyfile(tempfile, dest)
        os.remove(tempfile)
        self._load_document("file://%s" % dest)

    def _download_error_cb(self, getter, err, buddy):
        logging.debug("Error getting document from %s (%s): %s" % (buddy.props.nick, buddy.props.ip4_address, err))
        self._tried_buddies.append(buddy)
        gobject.idle_add(self._get_document)

    def _download_document(self, buddy):
        getter = network.GlibURLDownloader("http://%s:%d/document" % (buddy.props.ip4_address, _READ_PORT))
        getter.connect("finished", self._download_result_cb, buddy)
        getter.connect("error", self._download_error_cb, buddy)
        logging.debug("Starting download...")
        getter.start()
        return False

    def _have_file_reply_handler(self, have_it, buddy):
        if not have_it:
            # Try again
            logging.debug("Error: %s (%s) didn't have it" % (buddy.props.nick, buddy.props.ip4_address))
            self._tried_buddies.append(buddy)
            gobject.idle_add(self._get_document)
            return
        logging.debug("Trying to download document from %s (%s)" % (buddy.props.nick, buddy.props.ip4_address))
        gobject.idle_add(self._download_document, buddy)

    def _have_file_error_handler(self, err, buddy):
        logging.debug("Failed to get document from %s (%s)" % (buddy.props.nick, buddy.props.ip4_address))
        # Try again
        self._tried_buddies.append(buddy)
        gobject.idle_add(self._get_document)

    def _get_document(self):
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

        logging.debug("Will try to get document from %s (%s)" % (buddy.props.nick, buddy.props.ip4_address))
        proxy = network.GlibServerProxy("http://%s:%d" % (buddy.props.ip4_address, _READ_XMLPC_PORT))
        proxy.have_file(reply_handler=self._have_file_reply_handler,
                        error_handler=self._have_file_error_handler,
                        user_data=buddy)

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
        self._fileserver = ReadHTTPServer(("", _READ_PORT), self._filepath)

    def _shared_cb(self, activity):
        self._start_shared_services()
