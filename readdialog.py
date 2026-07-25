#!/usr/bin/env python

# Stolen from the PyGTK demo module by Maik Hertha <maik.hertha@berlin.de>

from gi.repository import Gtk


from sugar4.graphics import style
from sugar4.graphics.toolbutton import ToolButton

from gettext import gettext as _
import json


class BaseReadDialog(Gtk.Window):

    def __init__(self, parent_window, dialog_title):
        super().__init__()

        from readactivity import get_screen_width, get_screen_height
        width = int(get_screen_width() - style.GRID_CELL_SIZE * 4)
        height = int(get_screen_height() - style.GRID_CELL_SIZE * 4)
        self.set_default_size(width, height)
        self.add_css_class('background')

        self.set_transient_for(parent_window)
        self.set_modal(True)

        _vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.set_child(_vbox)

        self.toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        label = Gtk.Label()
        label.set_markup('<b>  %s</b>' % dialog_title)
        label.set_xalign(0.0)
        label.set_yalign(0.5)
        tool_item = Gtk.Box()
        tool_item.append(label)
        label.set_visible(True)
        self.toolbar.append(tool_item)
        tool_item.set_visible(True)

        separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        separator.set_opacity(0)
        separator.set_hexpand(True)
        self.toolbar.append(separator)
        separator.set_visible(True)
        stop = ToolButton(icon_name='dialog-cancel')
        stop.set_tooltip(_('Cancel'))
        stop.connect('clicked', self.cancel_clicked_cb)
        self.toolbar.append(stop)
        stop.set_visible(True)

        accept = ToolButton(icon_name='dialog-ok')
        accept.set_tooltip(_('Ok'))
        accept.connect('clicked', self.accept_clicked_cb)
        accept.set_visible(True)
        self.toolbar.append(accept)

        self.toolbar.set_hexpand(True)
        _vbox.append(self.toolbar)
        self.toolbar.set_visible(True)

        self._event_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._event_box.set_vexpand(True)
        self._event_box.set_valign(Gtk.Align.FILL)
        _vbox.append(self._event_box)
        self._canvas = None

    def set_canvas(self, canvas):
        if self._canvas is not None:
            self._event_box.remove(self._canvas)
        self._event_box.append(canvas)
        self._canvas = canvas

    def accept_clicked_cb(self, widget):
        raise NotImplementedError

    def cancel_clicked_cb(self, widget):
        self.destroy()


class BookmarkDialog(BaseReadDialog):

    def __init__(self, parent_window, dialog_title, page, sidebarinstance):
        super().__init__(parent_window, dialog_title)

        self._sidebarinstance = sidebarinstance
        self._page = page

        self._vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.set_canvas(self._vbox)

    def add_bookmark_widgets(self, bookmark_title, bookmark_content, local,
                             nick=''):
        thbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self._vbox.append(thbox)
        margin = style.DEFAULT_SPACING * 2
        thbox.set_margin_top(margin)
        thbox.set_margin_bottom(margin)
        thbox.set_margin_start(margin)
        thbox.set_margin_end(margin)
        thbox.set_spacing(style.DEFAULT_SPACING)
        thbox.set_visible(True)

        label_title = Gtk.Label(label=_('<b>Title</b>:'))
        label_title.set_use_markup(True)
        label_title.add_css_class('dim-label')
        label_title.set_xalign(1.0)
        label_title.set_yalign(0.5)
        thbox.append(label_title)
        label_title.set_visible(True)

        if local == 1:
            self._title_entry = Gtk.Entry()
            from readactivity import get_screen_width
            self._title_entry.set_size_request(int(get_screen_width() / 3), -1)
            thbox.append(self._title_entry)
            self._title_entry.set_visible(True)
            if bookmark_title is not None:
                self._title_entry.set_text(bookmark_title)
        else:
            title = Gtk.Label(label=bookmark_title)
            thbox.append(title)

            # show the nickname
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            hbox.set_margin_start(style.DEFAULT_SPACING * 2)
            hbox.set_spacing(style.DEFAULT_SPACING)
            signed_by = Gtk.Label(label=_('<b>Author</b>:'))
            signed_by.set_use_markup(True)
            signed_by.add_css_class('dim-label')
            signed_by.set_xalign(1.0)
            signed_by.set_yalign(0.5)
            hbox.append(signed_by)
            nick_label = Gtk.Label(label=nick)
            hbox.append(nick_label)
            self._vbox.append(hbox)
            hbox.set_visible(True)

        cvbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        margin = style.DEFAULT_SPACING * 2
        cvbox.set_margin_top(margin)
        cvbox.set_margin_bottom(margin)
        cvbox.set_margin_start(margin)
        cvbox.set_margin_end(margin)
        cvbox.set_spacing(style.DEFAULT_SPACING / 2)
        cvbox.set_visible(True)

        label_content = Gtk.Label(label=_('<b>Details</b>:'))
        label_content.set_use_markup(True)
        label_content.add_css_class('dim-label')
        label_content.set_xalign(0.0)
        label_content.set_yalign(0.0)
        cvbox.append(label_content)
        label_content.set_visible(True)

        if local == 1:
            sw = Gtk.ScrolledWindow()
            sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

            self._content_entry = Gtk.TextView()
            self._content_entry.set_wrap_mode(Gtk.WrapMode.WORD)
            self._content_entry.set_sensitive(local == 1)

            sw.set_child(self._content_entry)
            sw.set_has_frame(True)

            sw.set_vexpand(True)
            sw.set_valign(Gtk.Align.FILL)
            cvbox.append(sw)
            self._content_entry.set_visible(True)
            if bookmark_content is not None:
                buffer = self._content_entry.get_buffer()
                buffer.set_text(bookmark_content)
            cvbox.set_vexpand(True)
            cvbox.set_valign(Gtk.Align.FILL)
            self._vbox.append(cvbox)
        else:
            content = Gtk.Label(label=bookmark_content)
            content.set_xalign(0.0)
            content.set_yalign(0.0)
            cvbox.append(content)
            self._vbox.append(cvbox)

    def cancel_clicked_cb(self, widget):
        self._sidebarinstance.notify_bookmark_change()
        BaseReadDialog.cancel_clicked_cb(self, widget)


class BookmarkAddDialog(BookmarkDialog):

    def __init__(self, parent_window, dialog_title, bookmark_title,
                 bookmark_content, page, sidebarinstance):
        super().__init__(parent_window, dialog_title, page, sidebarinstance)
        self.add_bookmark_widgets(bookmark_title, bookmark_content, 1)

    def accept_clicked_cb(self, widget):
        title = self._title_entry.get_text()
        details = self._content_entry.get_buffer().props.text
        content = {'title': title,
                   'body': details}
        self._sidebarinstance._real_add_bookmark(self._page,
                                                 json.dumps(content))
        self.destroy()

    def cancel_clicked_cb(self, widget):
        self._sidebarinstance.notify_bookmark_change()
        BaseReadDialog.cancel_clicked_cb(self, widget)


class BookmarkEditDialog(BookmarkDialog):

    def __init__(self, parent_window, dialog_title, bookmarks, page,
                 sidebarinstance):
        super().__init__(parent_window, dialog_title, page, sidebarinstance)
        for bookmark in bookmarks:
            self.add_bookmark_widgets(bookmark.get_note_title(),
                                      bookmark.get_note_body(),
                                      bookmark.local,
                                      bookmark.nick)

    def accept_clicked_cb(self, widget):
        title = self._title_entry.get_text()
        details = self._content_entry.get_buffer().props.text
        content = {'title': title,
                   'body': details}
        self._sidebarinstance.del_bookmark(self._page)
        self._sidebarinstance._real_add_bookmark(self._page,
                                                 json.dumps(content))
        self.destroy()
