# Copyright (C) 2006-2007, Red Hat, Inc.
# Copyright (C) 2009 One Laptop Per Child
# Author: Sayamindu Dasgupta <sayamindu@laptop.org>
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

import gtk, gobject
import dbus

from sugar.graphics import style
from sugar.graphics.icon import Icon, get_icon_state

from gettext import gettext as _


_LEVEL_PROP = 'battery.charge_level.percentage'
_CHARGING_PROP = 'battery.rechargeable.is_charging'
_DISCHARGING_PROP = 'battery.rechargeable.is_discharging'
_PRESENT_PROP = 'battery.present'

_ICON_NAME = 'battery'


# Taken from sugar/extensions/deviceicon/battery.py
class BattMan(gobject.GObject):

    __gproperties__ = {
        'level': (int, None, None, 0, 100, 0, gobject.PARAM_READABLE),
        'charging': (bool, None, None, False, gobject.PARAM_READABLE),
        'discharging': (bool, None, None, False, gobject.PARAM_READABLE),
        'present': (bool, None, None, False, gobject.PARAM_READABLE),
    }

    def __init__(self, udi):
        gobject.GObject.__init__(self)

        bus = dbus.Bus(dbus.Bus.TYPE_SYSTEM)
        proxy = bus.get_object('org.freedesktop.Hal', udi,
                               follow_name_owner_changes=True)
        self._battery = dbus.Interface(proxy, 'org.freedesktop.Hal.Device')
        bus.add_signal_receiver(self._battery_changed,
                                'PropertyModified',
                                'org.freedesktop.Hal.Device',
                                'org.freedesktop.Hal',
                                udi)

        self._level = self._get_level()
        self._charging = self._get_charging()
        self._discharging = self._get_discharging()
        self._present = self._get_present()

    def _get_level(self):
        try:
            return self._battery.GetProperty(_LEVEL_PROP)
        except dbus.DBusException:
            logging.error('Cannot access %s' % _LEVEL_PROP)
            return 0

    def _get_charging(self):
        try:
            return self._battery.GetProperty(_CHARGING_PROP)
        except dbus.DBusException:
            logging.error('Cannot access %s' % _CHARGING_PROP)
            return False

    def _get_discharging(self):
        try:
            return self._battery.GetProperty(_DISCHARGING_PROP)
        except dbus.DBusException:
            logging.error('Cannot access %s' % _DISCHARGING_PROP)
            return False

    def _get_present(self):
        try:
            return self._battery.GetProperty(_PRESENT_PROP)
        except dbus.DBusException:
            logging.error('Cannot access %s' % _PRESENT_PROP)
            return False

    def do_get_property(self, pspec):
        if pspec.name == 'level':
            return self._level
        if pspec.name == 'charging':
            return self._charging
        if pspec.name == 'discharging':
            return self._discharging
        if pspec.name == 'present':
            return self._present

    def get_type(self):
        return 'battery'

    def _battery_changed(self, num_changes, changes_list):
        for change in changes_list:
            if change[0] == _LEVEL_PROP:
                self._level = self._get_level()
                self.notify('level')
            elif change[0] == _CHARGING_PROP:
                self._charging = self._get_charging()
                self.notify('charging')
            elif change[0] == _DISCHARGING_PROP:
                self._discharging = self._get_discharging()
                self.notify('discharging')
            elif change[0] == _PRESENT_PROP:
                self._present = self._get_present()
                self.notify('present')


class _TopBar(gtk.HBox):
    __gproperties__ = {
        'completion-level': (float, None, None, 0.0, 100.0, 0.0,
                             gobject.PARAM_READWRITE),
    }

    def __init__(self):
        gtk.HBox.__init__(self)

        self.set_border_width(int(style.DEFAULT_SPACING / 2.0))
        self.set_spacing(style.DEFAULT_SPACING * 4)

        self._completion_level = 0
        self._progressbar = None

        bus = dbus.Bus(dbus.Bus.TYPE_SYSTEM)
        proxy = bus.get_object('org.freedesktop.Hal',
                                '/org/freedesktop/Hal/Manager')
        hal_manager = dbus.Interface(proxy, 'org.freedesktop.Hal.Manager')
        udis = hal_manager.FindDeviceByCapability('battery')
        if len(udis) > 0:
            self._battery = BattMan(udis[0]) # TODO: Support more than one battery
            self._battery.connect('notify::level', \
                self._battery_level_changed_cb)
        else:
            self._battery = None

        self._icon = None

        self._setup()

    def do_get_property(self, property):
        if property.name == 'completion-level':
            return self._completion_level
        else:
            raise AttributeError, 'unknown property %s' % property.name

    def do_set_property(self, property, value):
        if property.name == 'completion-level':
            self.set_completion_level(value)
        else:
            raise AttributeError, 'unknown property %s' % property.name

    def set_completion_level(self, value):
        self._completion_level = value
        self._progressbar.set_fraction(self._completion_level / 100.0)

    def _setup(self):
        self._progressbar = gtk.ProgressBar()
        self._progressbar.props.discrete_blocks = 10
        self._progressbar.set_fraction(self._completion_level / 100.0)
        self.pack_start(self._progressbar, expand=True, fill=True)
        if self._battery is not None:
            icon_name = get_icon_state(_ICON_NAME, self._battery.props.level, step=-5)
            self._icon = Icon(icon_name=icon_name)
            self.pack_start(self._icon, expand=False, fill=False)

    def _battery_level_changed_cb(self, pspec, param):
        icon_name = get_icon_state(_ICON_NAME, self._battery.props.level, step=-5)
        self._icon.props.icon_name = icon_name


class TopBar(_TopBar):

    def __init__(self):
        _TopBar.__init__(self)
        self._document = None

    def set_document(self, document):
        self._document = document

        page_cache = self._document.get_page_cache()
        page_cache.connect('page-changed', self._page_changed_cb)

    def _page_changed_cb(self, page, proxy=None):
        current_page = self._document.get_page_cache().get_current_page()
        n_pages = self._document.get_n_pages()

        self.set_completion_level(current_page * 100 / n_pages)

        #TRANS: Translate this as Page i of m (eg: Page 4 of 334)
        self._progressbar.set_text(_("Page %i of %i") % (current_page, n_pages))
