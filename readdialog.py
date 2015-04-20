#!/usr/bin/env python

# Stolen from the PyGTK demo module by Maik Hertha <maik.hertha@berlin.de>

from gi.repository import Gtk
from gi.repository import Gdk

from sugar3.graphics import style
from sugar3.graphics.toolbutton import ToolButton

from gettext import gettext as _
import json


class BaseReadDialog(Gtk.Window):

    def __init__(self, parent_xid, dialog_title):
        Gtk.Window.__init__(self)

        self.connect('realize', self.__realize_cb)

        self.set_decorated(False)
        self.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
        self.set_border_width(style.LINE_WIDTH)
        self.set_resizable(False)

        width = Gdk.Screen.width() - style.GRID_CELL_SIZE * 4
        height = Gdk.Screen.height() - style.GRID_CELL_SIZE * 4
        self.set_size_request(width, height)

        self._parent_window_xid = parent_xid

        _vbox = Gtk.VBox(spacing=2)
        self.add(_vbox)

        self.toolbar = Gtk.Toolbar()
        label = Gtk.Label()
        label.set_markup('<b>  %s</b>' % dialog_title)
        label.set_alignment(0, 0.5)
        tool_item = Gtk.ToolItem()
        tool_item.add(label)
        label.show()
        self.toolbar.insert(tool_item, -1)
        tool_item.show()

        separator = Gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)
        self.toolbar.insert(separator, -1)
        separator.show()
        stop = ToolButton(icon_name='dialog-cancel')
        stop.set_tooltip(_('Cancel'))
        stop.connect('clicked', self.cancel_clicked_cb)
        self.toolbar.insert(stop, -1)
        stop.show()

        accept = ToolButton(icon_name='dialog-ok')
        accept.set_tooltip(_('Ok'))
        accept.connect('clicked', self.accept_clicked_cb)
        accept.show()
        self.toolbar.insert(accept, -1)

        _vbox.pack_start(self.toolbar, False, True, 0)
        self.toolbar.show()

        self._event_box = Gtk.EventBox()
        _vbox.pack_start(self._event_box, True, True, 0)
        self._canvas = None

    def set_canvas(self, canvas):
        if self._canvas is not None:
            self._event_box.remove(self._canvas)
        self._event_box.add(canvas)
        self._canvas = canvas

    def __realize_cb(self, widget):
        self.get_window().set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.get_window().set_accept_focus(True)
        self.get_window().set_decorations(Gdk.WMDecoration.BORDER)
        self.get_window().set_transient_for(self._parent_window_xid)

        self.modify_bg(Gtk.StateType.NORMAL,
                       style.COLOR_WHITE.get_gdk_color())

        if self._canvas is not None:
            self._canvas.modify_bg(Gtk.StateType.NORMAL,
                                   style.COLOR_WHITE.get_gdk_color())
            self._canvas.grab_focus()

        self._event_box.modify_bg(Gtk.StateType.NORMAL,
                                  style.COLOR_WHITE.get_gdk_color())

    def accept_clicked_cb(self, widget):
        raise NotImplementedError

    def cancel_clicked_cb(self, widget):
        self.destroy()


class BookmarkDialog(BaseReadDialog):

    def __init__(self, parent_xid, dialog_title, page, sidebarinstance):
        BaseReadDialog.__init__(self, parent_xid, dialog_title)

        self._sidebarinstance = sidebarinstance
        self._page = page

        self._vbox = Gtk.VBox()

        self.set_canvas(self._vbox)

    def add_bookmark_widgets(self, bookmark_title, bookmark_content, local,
                             nick=''):
        thbox = Gtk.HBox()
        self._vbox.pack_start(thbox, False, False, 0)
        thbox.set_border_width(style.DEFAULT_SPACING * 2)
        thbox.set_spacing(style.DEFAULT_SPACING)
        thbox.show()

        label_title = Gtk.Label(_('<b>Title</b>:'))
        label_title.set_use_markup(True)
        label_title.set_alignment(1, 0.5)
        label_title.modify_fg(Gtk.StateType.NORMAL,
                              style.COLOR_SELECTION_GREY.get_gdk_color())
        thbox.pack_start(label_title, False, False, 0)
        label_title.show()

        if local == 1:
            self._title_entry = Gtk.Entry()
            self._title_entry.modify_bg(Gtk.StateType.INSENSITIVE,
                                        style.COLOR_WHITE.get_gdk_color())
            self._title_entry.modify_base(Gtk.StateType.INSENSITIVE,
                                          style.COLOR_WHITE.get_gdk_color())
            self._title_entry.set_size_request(int(Gdk.Screen.width() / 3), -1)
            thbox.pack_start(self._title_entry, False, False, 0)
            self._title_entry.show()
            if bookmark_title is not None:
                self._title_entry.set_text(bookmark_title)
        else:
            title = Gtk.Label(bookmark_title)
            thbox.pack_start(title, False, False, 0)

            # show the nickname
            hbox = Gtk.HBox()
            hbox.set_margin_left(style.DEFAULT_SPACING * 2)
            hbox.set_spacing(style.DEFAULT_SPACING)
            signed_by = Gtk.Label(_('<b>Author</b>:'))
            signed_by.set_use_markup(True)
            signed_by.set_alignment(1, 0.5)
            signed_by.modify_fg(Gtk.StateType.NORMAL,
                                style.COLOR_SELECTION_GREY.get_gdk_color())
            hbox.pack_start(signed_by, False, False, 0)
            nick_label = Gtk.Label(nick)
            hbox.pack_start(nick_label, False, False, 0)
            self._vbox.pack_start(hbox, False, False, 0)
            hbox.show_all()

        cvbox = Gtk.VBox()
        cvbox.set_border_width(style.DEFAULT_SPACING * 2)
        cvbox.set_spacing(style.DEFAULT_SPACING / 2)
        cvbox.show()

        label_content = Gtk.Label(_('<b>Details</b>:'))
        label_content.set_use_markup(True)
        label_content.set_alignment(0, 0)
        label_content.modify_fg(Gtk.StateType.NORMAL,
                                style.COLOR_SELECTION_GREY.get_gdk_color())
        cvbox.pack_start(label_content, False, False, 0)
        label_content.show()

        if local == 1:
            sw = Gtk.ScrolledWindow()
            sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

            self._content_entry = Gtk.TextView()
            self._content_entry.set_wrap_mode(Gtk.WrapMode.WORD)
            self._content_entry.set_sensitive(local == 1)

            sw.add(self._content_entry)
            sw.set_shadow_type(Gtk.ShadowType.ETCHED_IN)

            cvbox.pack_start(sw, True, True, 0)
            self._content_entry.show()
            if bookmark_content is not None:
                buffer = self._content_entry.get_buffer()
                buffer.set_text(bookmark_content)
            self._vbox.pack_start(cvbox, True, True, 0)
        else:
            content = Gtk.Label(bookmark_content)
            content.set_alignment(0, 0)
            cvbox.pack_start(content, False, False, 0)
            self._vbox.pack_start(cvbox, False, False, 0)

    def cancel_clicked_cb(self, widget):
        self._sidebarinstance.notify_bookmark_change()
        BaseReadDialog.cancel_clicked_cb(self, widget)


class BookmarkAddDialog(BookmarkDialog):

    def __init__(self, parent_xid, dialog_title, bookmark_title,
                 bookmark_content, page, sidebarinstance):
        BookmarkDialog.__init__(self, parent_xid, dialog_title, page,
                                sidebarinstance)
        self.add_bookmark_widgets(bookmark_title, bookmark_content, 1)

    def accept_clicked_cb(self, widget):
        title = self._title_entry.get_text()
        details = self._content_entry.get_buffer().props.text
        content = {'title': title.decode('utf-8'),
                   'body': details.decode('utf-8')}
        self._sidebarinstance._real_add_bookmark(self._page,
                                                 json.dumps(content))
        self.destroy()

    def cancel_clicked_cb(self, widget):
        self._sidebarinstance.notify_bookmark_change()
        BaseReadDialog.cancel_clicked_cb(self, widget)


class BookmarkEditDialog(BookmarkDialog):

    def __init__(self, parent_xid, dialog_title, bookmarks, page,
                 sidebarinstance):
        BookmarkDialog.__init__(self, parent_xid, dialog_title, page,
                                sidebarinstance)
        for bookmark in bookmarks:
            self.add_bookmark_widgets(bookmark.get_note_title(),
                                      bookmark.get_note_body(),
                                      bookmark.local,
                                      bookmark.nick)

    def accept_clicked_cb(self, widget):
        title = self._title_entry.get_text()
        details = self._content_entry.get_buffer().props.text
        content = {'title': title.decode('utf-8'),
                   'body': details.decode('utf-8')}
        self._sidebarinstance.del_bookmark(self._page)
        self._sidebarinstance._real_add_bookmark(self._page,
                                                 json.dumps(content))
        self.destroy()
