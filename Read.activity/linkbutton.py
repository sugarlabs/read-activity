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
from gi.repository import GObject

import StringIO
import cairo
from gettext import gettext as _

from sugar3.graphics.palette import Palette
from sugar3.graphics.tray import TrayButton
from sugar3.graphics import style


class LinkButton(TrayButton, GObject.GObject):
    __gtype_name__ = 'LinkButton'
    __gsignals__ = {
        'remove_link': (GObject.SignalFlags.RUN_FIRST,
                        None, ([int])),
        'go_to_bookmark': (GObject.SignalFlags.RUN_FIRST,
                           None, ([int])), }

    def __init__(self, buf, color, title, owner, page, local):
        TrayButton.__init__(self)

        # Color read from the Journal may be Unicode, but Rsvg needs
        # it as single byte string:
        self._color = color
        if isinstance(color, unicode):
            self._color = str(color)
        self._have_preview = False
        if buf is not None:
            self.set_image(buf)
        else:
            self.set_empty_image(page)

        self.page = int(page)
        self.setup_rollover_options(title, owner, local)

    def have_preview(self):
        return self._have_preview

    def set_image(self, buf):
        fill = self._color.split(',')[1]
        stroke = self._color.split(',')[0]
        self._have_preview = True
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

    def set_empty_image(self, page):
        fill = self._color.split(',')[1]
        stroke = self._color.split(',')[0]
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

    def setup_rollover_options(self, title, info, local):
        palette = Palette(title, text_maxlen=50)
        palette.set_secondary_text(info)
        self.set_palette(palette)

        menu_item = Gtk.MenuItem(_('Go to Bookmark'))
        menu_item.connect('activate', self.go_to_bookmark_cb)
        palette.menu.append(menu_item)
        menu_item.show()

        if local == 1:
            menu_item = Gtk.MenuItem(_('Remove'))
            menu_item.connect('activate', self.item_remove_cb)
            palette.menu.append(menu_item)
            menu_item.show()

    def item_remove_cb(self, widget):
        self.emit('remove_link', self.page)

    def go_to_bookmark_cb(self, widget):
        self.emit('go_to_bookmark', self.page)
