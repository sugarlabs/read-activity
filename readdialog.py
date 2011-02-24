#!/usr/bin/env python

# Stolen from the PyGTK demo module by Maik Hertha <maik.hertha@berlin.de>

import gtk
import gobject

from sugar.graphics import style
from sugar.graphics.toolbutton import ToolButton

from gettext import gettext as _
import cjson


class BaseReadDialog(gtk.Window):

    def __init__(self, parent_xid, dialog_title):
        gtk.Window.__init__(self)

        self.connect('realize', self.__realize_cb)

        self.set_decorated(False)
        self.set_position(gtk.WIN_POS_CENTER_ALWAYS)
        self.set_border_width(style.LINE_WIDTH)

        width = gtk.gdk.screen_width() - style.GRID_CELL_SIZE * 4
        height = gtk.gdk.screen_height() - style.GRID_CELL_SIZE * 4
        self.set_size_request(width, height)

        self._parent_window_xid = parent_xid

        _vbox = gtk.VBox(spacing=2)
        self.add(_vbox)

        self.toolbar = gtk.Toolbar()
        label = gtk.Label()
        label.set_markup('<b>  %s</b>' % dialog_title)
        label.set_alignment(0, 0.5)
        tool_item = gtk.ToolItem()
        tool_item.add(label)
        label.show()
        self.toolbar.insert(tool_item, -1)
        tool_item.show()

        separator = gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)
        self.toolbar.insert(separator, -1)
        separator.show()
        stop = ToolButton(icon_name='dialog-cancel')
        stop.set_tooltip(_('Cancel'))
        stop.connect('clicked', lambda *w: self.destroy())
        self.toolbar.insert(stop, -1)
        stop.show()

        accept = ToolButton(icon_name='dialog-ok')
        accept.set_tooltip(_('Ok'))
        accept.connect('clicked', self.accept_clicked_cb)
        accept.show()
        self.toolbar.insert(accept, -1)

        _vbox.pack_start(self.toolbar, expand=False)
        self.toolbar.show()

        self._event_box = gtk.EventBox()
        _vbox.pack_start(self._event_box, expand=True, fill=True)
        self._canvas = None

    def set_canvas(self, canvas):
        if self._canvas is not None:
            self._event_box.remove(self._canvas)
        self._event_box.add(canvas)
        self._canvas = canvas

    def __realize_cb(self, widget):
        self.window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
        self.window.set_accept_focus(True)

        parent = gtk.gdk.window_foreign_new(self._parent_window_xid)
        self.window.set_transient_for(parent)

        self.modify_bg(gtk.STATE_NORMAL,
                            style.COLOR_WHITE.get_gdk_color())

        if self._canvas is not None:
            self._canvas.modify_bg(gtk.STATE_NORMAL,
                style.COLOR_WHITE.get_gdk_color())
            self._canvas.grab_focus()

        self._event_box.modify_bg(gtk.STATE_NORMAL,
                style.COLOR_WHITE.get_gdk_color())

    def accept_clicked_cb(self, widget):
        raise NotImplementedError


class BookmarkDialog(BaseReadDialog):
    def __init__(self, parent_xid, dialog_title, bookmark_title,
            bookmark_content, page, sidebarinstance):
        BaseReadDialog.__init__(self, parent_xid, dialog_title)

        self._sidebarinstance = sidebarinstance
        self._page = page

        vbox = gtk.VBox()
        thbox = gtk.HBox()
        vbox.pack_start(thbox, expand=False, fill=False)
        thbox.set_border_width(style.DEFAULT_SPACING * 2)
        thbox.set_spacing(style.DEFAULT_SPACING)
        thbox.show()

        label_title = gtk.Label(_('<b>Title</b>:'))
        label_title.set_use_markup(True)
        label_title.set_alignment(1, 0.5)
        label_title.modify_fg(gtk.STATE_NORMAL,
                            style.COLOR_SELECTION_GREY.get_gdk_color())
        thbox.pack_start(label_title, expand=False, fill=False)
        label_title.show()

        self._title_entry = gtk.Entry()
        self._title_entry.modify_bg(gtk.STATE_INSENSITIVE,
                            style.COLOR_WHITE.get_gdk_color())
        self._title_entry.modify_base(gtk.STATE_INSENSITIVE,
                            style.COLOR_WHITE.get_gdk_color())
        self._title_entry.set_size_request(int(gtk.gdk.screen_width() / 3), -1)

        thbox.pack_start(self._title_entry, expand=False, fill=False)
        self._title_entry.show()
        if bookmark_title is not None:
            self._title_entry.set_text(bookmark_title)

        cvbox = gtk.VBox()
        vbox.pack_start(cvbox, expand=True, fill=True)
        cvbox.set_border_width(style.DEFAULT_SPACING * 2)
        cvbox.set_spacing(style.DEFAULT_SPACING / 2)
        cvbox.show()

        label_content = gtk.Label(_('<b>Details</b>:'))
        label_content.set_use_markup(True)
        label_content.set_alignment(0, 0)
        label_content.modify_fg(gtk.STATE_NORMAL,
                            style.COLOR_SELECTION_GREY.get_gdk_color())
        cvbox.pack_start(label_content, expand=False, fill=False)
        label_content.show()

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        self._content_entry = gtk.TextView()
        self._content_entry.set_wrap_mode(gtk.WRAP_WORD)

        sw.add(self._content_entry)
        sw.set_shadow_type(gtk.SHADOW_ETCHED_IN)

        cvbox.pack_start(sw, expand=True, fill=True)
        self._content_entry.show()
        if bookmark_content is not None:
            buffer = self._content_entry.get_buffer()
            buffer.set_text(bookmark_content)

        self.set_canvas(vbox)


class BookmarkAddDialog(BookmarkDialog):

    def __init__(self, parent_xid, dialog_title, bookmark_title,
            bookmark_content, page, sidebarinstance):
        BookmarkDialog.__init__(self, parent_xid, dialog_title, bookmark_title,
            bookmark_content, page, sidebarinstance)

    def accept_clicked_cb(self, widget):
        title = self._title_entry.get_text()
        details = self._content_entry.get_buffer().props.text
        content = {'title': unicode(title), 'body': unicode(details)}
        self._sidebarinstance._real_add_bookmark(self._page,
                cjson.encode(content))
        self.destroy()


class BookmarkEditDialog(BookmarkDialog):

    def __init__(self, parent_xid, dialog_title, bookmark_title,
            bookmark_content, page, sidebarinstance):
        BookmarkDialog.__init__(self, parent_xid, dialog_title, bookmark_title,
            bookmark_content, page, sidebarinstance)

    def accept_clicked_cb(self, widget):
        title = self._title_entry.get_text()
        details = self._content_entry.get_buffer().props.text
        content = {'title': unicode(title), 'body': unicode(details)}
        self._sidebarinstance.del_bookmark(self._page)
        self._sidebarinstance._real_add_bookmark(self._page,
                cjson.encode(content))
        self.destroy()
