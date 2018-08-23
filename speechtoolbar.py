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

        self.load_speech_parameters()

        self._voices = self._speech.get_all_voices()  # a dictionary

        locale = os.environ.get('LANG', '')
        language_location = locale.split('.', 1)[0].lower()
        language = language_location.split('_')[0]
        # if the language is es but not es_es default to es_la (latin voice)
        if language == 'es' and language_location != 'es_es':
            language_location = 'es_la'

        self._voice = 'en_us'
        if language_location in self._voices:
            self._voice = language_location
        elif language in self._voices:
            self._voice = language

        voice_names = []
        for language, name in self._voices.iteritems():
            voice_names.append((language, name))
        voice_names.sort(self._compare_voice)

        # Play button
        self.play_button = ToggleToolButton('media-playback-start')
        self.play_button.show()
        self.play_button.connect('toggled', self._play_toggled_cb)
        self.insert(self.play_button, -1)
        self.play_btn.set_tooltip(_('Play / Pause'))

        # Stop button
        self.stop_button = ToolButton('media-playback-stop')
        self.stop_button.show()
        self.stop_button.connect('clicked', self.stop_cb)
        self.stop_button.set_sensitive(False)
        self.insert(self.stop_button, -1)
        self.stop_btn.set_tooltip(_('Stop'))

        # Language list
        combo = ComboBox()
        which = 0
        for pair in voice_names:
            language, name = pair
            combo.append_item(language, name)
            if language == self._voice:
                combo.set_active(which)
            which += 1

        combo.connect('changed', self._voice_changed_cb)
        combotool = ToolComboBox(combo)
        self.insert(combotool, -1)
        combotool.show()

        self._speech.connect('stop', self._reset_buttons_cb)

    def _compare_voice(self,  a,  b):
        if a[1].lower() == b[1].lower():
            return 0
        if a[1] .lower() < b[1].lower():
            return -1
        if a[1] .lower() > b[1].lower():
            return 1

    def _voice_changed_cb(self, combo):
        self._voice = combo.props.value
        self._speech.say_text(self._voices[self._voice])
        self.save_speech_parameters()

    def load_speech_parameters(self):
        speech_parameters = {}
        data_path = os.path.join(self._activity.get_activity_root(), 'data')
        data_file_name = os.path.join(data_path, 'speech_params.json')
        if os.path.exists(data_file_name):
            f = open(data_file_name, 'r')
            try:
                speech_parameters = json.load(f)
                self._voice = speech_parameters['voice']
            finally:
                f.close()

    def save_speech_parameters(self):
        speech_parameters = {}
        speech_parameters['voice'] = self._voice
        data_path = os.path.join(self._activity.get_activity_root(), 'data')
        data_file_name = os.path.join(data_path, 'speech_params.json')
        f = open(data_file_name, 'w')
        try:
            json.dump(speech_parameters, f)
        finally:
            f.close()

    def _reset_buttons_cb(self):
        self.play_button.set_icon_name('media-playback-start')
        self.stop_button.set_sensitive(False)
        self._is_paused = False

    def _play_toggled_cb(self, widget):
        self.stop_button.set_sensitive(True)
        if widget.get_active():
            self.play_button.set_icon_name('media-playback-pause')
            if not self._is_paused:
                self._speech.say_text(
                    self._activity._view.get_marked_words(),
                    lang_code=self._voice)
            else:
                self._speech.restart()
        else:
            self.play_button.set_icon_name('media-playback-start')
            self._is_paused = True
            self._speech.pause()

    def stop_cb(self, widget):
        self.stop_button.set_sensitive(False)
        self.play_button.set_icon_name('media-playback-start')
        self.play_button.set_active(False)
        self._is_paused = False
        self._speech.stop()
