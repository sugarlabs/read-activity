# Copyright (C) 2006, Red Hat, Inc.
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

import os
import json
from gettext import gettext as _

from gi.repository import Gtk

from sugar3.graphics.toolbutton import ToolButton
from sugar3.graphics.toggletoolbutton import ToggleToolButton
from sugar3.graphics.combobox import ComboBox
from sugar3.graphics.toolcombobox import ToolComboBox
from sugar3.speech import SpeechManager


class SpeechToolbar(Gtk.Toolbar):

    def __init__(self, activity):
        Gtk.Toolbar.__init__(self)
        self._activity = activity
        self._speech = SpeechManager()
        self._is_paused = False

        # Play button
        self._play_button = ToggleToolButton('media-playback-start')
        self._play_button.show()
        self._play_button.connect('toggled', self._play_toggled_cb)
        self.insert(self._play_button, -1)
        self._play_button.set_tooltip(_('Play / Pause'))

        # Stop button
        self._stop_button = ToolButton('media-playback-stop')
        self._stop_button.show()
        self._stop_button.connect('clicked', self._stop_clicked_cb)
        self._stop_button.set_sensitive(False)
        self.insert(self._stop_button, -1)
        self._stop_button.set_tooltip(_('Stop'))

        self._speech.connect('stop', self._reset_buttons_cb)

    def _reset_buttons_cb(self, widget=None):
        self._play_button.set_icon_name('media-playback-start')
        self._stop_button.set_sensitive(False)
        self._is_paused = False

    def _play_toggled_cb(self, widget):
        self._stop_button.set_sensitive(True)
        if widget.get_active():
            self._play_button.set_icon_name('media-playback-pause')
            if not self._is_paused:
                self._speech.say_text(
                    self._activity._view.get_marked_words())
            else:
                self._speech.restart()
        else:
            self._play_button.set_icon_name('media-playback-start')
            self._is_paused = True
            self._speech.pause()

    def _stop_clicked_cb(self, widget):
        self._stop_button.set_sensitive(False)
        self._play_button.set_icon_name('media-playback-start')
        self._play_button.set_active(False)
        self._is_paused = False
        self._speech.stop()
