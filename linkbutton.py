# Copyright (C) 2007, One Laptop Per Child
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GObject
from gi.repository import Rsvg

import os
import StringIO
import cairo
from gettext import gettext as _
import re
import gc
import logging

from sugar3.graphics.palette import Palette
from sugar3.graphics.tray import TrayButton
from sugar3.graphics import style


class LinkButton(TrayButton, GObject.GObject):
    __gtype_name__ = 'LinkButton'
    __gsignals__ = {
        'remove_link': (GObject.SignalFlags.RUN_FIRST,
                        None, ([int])),
        'go_to_bookmark': (GObject.SignalFlags.RUN_FIRST,
                        None, ([int])),
        }

    def __init__(self, buf, color, title, owner, page):
        TrayButton.__init__(self)

        # Color read from the Journal may be Unicode, but Rsvg needs
        # it as single byte string:
        if isinstance(color, unicode):
            color = str(color)
        if buf is not None:
            self.set_image(buf, color.split(',')[1], color.split(',')[0])
        else:
            self.set_empty_image(page, color.split(',')[1],
                                 color.split(',')[0])

        self.page = int(page)
        info = title + '\n' + owner
        self.setup_rollover_options(info)

    def set_image(self, buf, fill='#0000ff', stroke='#4d4c4f'):
        img = Gtk.Image()
        str_buf = StringIO.StringIO(buf)
        thumb_surface = cairo.ImageSurface.create_from_png(str_buf)

        bg_width, bg_height = style.zoom(120), style.zoom(110)
        bg_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, bg_width,
                bg_height)
        context = cairo.Context(bg_surface)
        # draw a rectangle in the background with the selected colors
        context.set_line_width(style.zoom(10))
        context.set_source_rgba(*style.Color(fill).get_rgba())
        context.rectangle(0, 0, bg_width, bg_height)
        context.fill_preserve()
        context.set_source_rgba(*style.Color(stroke).get_rgba())
        context.stroke()
        # add the screenshot
        dest_x = style.zoom(10)
        dest_y = style.zoom(20)
        context.set_source_surface(thumb_surface, dest_x, dest_y)
        thumb_width, thumb_height = style.zoom(100), style.zoom(80)
        context.rectangle(dest_x, dest_y, thumb_width, thumb_height)
        context.fill()

        pixbuf_bg = Gdk.pixbuf_get_from_surface(bg_surface, 0, 0,
                                                bg_width, bg_height)

        img.set_from_pixbuf(pixbuf_bg)
        self.set_icon_widget(img)
        img.show()

    def set_empty_image(self, page, fill='#0000ff', stroke='#4d4c4f'):
        img = Gtk.Image()

        bg_width, bg_height = style.zoom(120), style.zoom(110)
        bg_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, bg_width,
                                        bg_height)
        context = cairo.Context(bg_surface)
        # draw a rectangle in the background with the selected colors
        context.set_line_width(style.zoom(10))
        context.set_source_rgba(*style.Color(fill).get_rgba())
        context.rectangle(0, 0, bg_width, bg_height)
        context.fill_preserve()
        context.set_source_rgba(*style.Color(stroke).get_rgba())
        context.stroke()

        # add the page number
        context.set_font_size(style.zoom(60))
        text = str(page)
        x, y = bg_width / 2, bg_height / 2

        xbearing, ybearing, width, height, xadvance, yadvance = \
            context.text_extents(text)
        context.move_to(x - width / 2, y + height / 2)
        context.show_text(text)
        context.stroke()

        pixbuf_bg = Gdk.pixbuf_get_from_surface(bg_surface, 0, 0,
                                                bg_width, bg_height)

        img.set_from_pixbuf(pixbuf_bg)
        self.set_icon_widget(img)
        img.show()

    def setup_rollover_options(self, info):
        palette = Palette(info, text_maxlen=50)
        self.set_palette(palette)

        menu_item = Gtk.MenuItem(_('Go to Bookmark'))
        menu_item.connect('activate', self.go_to_bookmark_cb)
        palette.menu.append(menu_item)
        menu_item.show()

        menu_item = Gtk.MenuItem(_('Remove'))
        menu_item.connect('activate', self.item_remove_cb)
        palette.menu.append(menu_item)
        menu_item.show()

    def item_remove_cb(self, widget):
        self.emit('remove_link', self.page)

    def go_to_bookmark_cb(self, widget):
        self.emit('go_to_bookmark', self.page)
