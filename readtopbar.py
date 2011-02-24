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

import gtk
import gobject
import dbus
import logging

from sugar.graphics import style
from sugar.graphics.icon import Icon, get_icon_state

from gettext import gettext as _


_ICON_NAME = 'battery'

_UP_DEVICE_IFACE = 'org.freedesktop.UPower.Device'
_UP_TYPE_BATTERY = 2


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
        self._icon = None
        self._battery_props = None

        try:
            bus = dbus.Bus(dbus.Bus.TYPE_SYSTEM)
            up_proxy = bus.get_object('org.freedesktop.UPower',
                                      '/org/freedesktop/UPower')
            upower = dbus.Interface(up_proxy, 'org.freedesktop.UPower')

            for device_path in upower.EnumerateDevices():
                device = bus.get_object('org.freedesktop.UPower', device_path)
                device_prop_iface = dbus.Interface(device,
                        dbus.PROPERTIES_IFACE)
                device_type = device_prop_iface.Get(_UP_DEVICE_IFACE, 'Type')
                if device_type != _UP_TYPE_BATTERY:
                    continue

                device.connect_to_signal('Changed',
                                         self.__battery_properties_changed_cb,
                                         dbus_interface=_UP_DEVICE_IFACE)
                self._battery_props = dbus.Interface(device,
                                                     dbus.PROPERTIES_IFACE)
                break

        except dbus.DBusException:
            logging.warning("Could not connect to UPower, won't show battery"
                            "level.")

        self._setup()

    def do_get_property(self, property):
        if property.name == 'completion-level':
            return self._completion_level
        else:
            raise AttributeError('unknown property %s' % property.name)

    def do_set_property(self, property, value):
        if property.name == 'completion-level':
            self.set_completion_level(value)
        else:
            raise AttributeError('unknown property %s' % property.name)

    def set_completion_level(self, value):
        self._completion_level = value
        self._progressbar.set_fraction(self._completion_level / 100.0)

    def _get_battery_level(self):
        try:
            return self._battery_props.Get(_UP_DEVICE_IFACE,
                                           'Percentage')
        except dbus.DBusException:
            logging.exception('Error determining battery level:')
            return 0

    def _setup(self):
        self._progressbar = gtk.ProgressBar()
        self._progressbar.props.discrete_blocks = 10
        self._progressbar.set_fraction(self._completion_level / 100.0)
        self.pack_start(self._progressbar, expand=True, fill=True)
        if self._battery_props is None:
            return

        level = self._get_battery_level()
        icon_name = get_icon_state(_ICON_NAME, level, step=-5)
        self._icon = Icon(icon_name=icon_name)
        self.pack_start(self._icon, expand=False, fill=False)

    def __battery_properties_changed_cb(self):
        level = self._get_battery_level()
        icon_name = get_icon_state(_ICON_NAME, level, step=-5)
        self._icon.props.icon_name = icon_name


class TopBar(_TopBar):

    def __init__(self):
        _TopBar.__init__(self)
        self._view = None

    def set_view(self, view):
        self._view = view
        self._view.connect_page_changed_handler(self._page_changed_cb)

    def _page_changed_cb(self, model, page_from, page_to):
        current_page = self._view.get_current_page()
        n_pages = self._view.get_pagecount()
        completion_level = int(float(current_page) * 100 / float(n_pages))
        self.set_completion_level(completion_level)

        #TRANS: Translate this as Page i of m (eg: Page 4 of 334)
        self._progressbar.set_text(
                _("Page %i of %i") % (current_page, n_pages))
