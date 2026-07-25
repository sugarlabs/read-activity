from gi.repository import Gtk

from sugar4.graphics import style
from sugar4.graphics.icon import Icon


def show(activity, icon_name, message, btn_label, btn_callback):
    empty_widgets = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    empty_widgets.add_css_class("background-white")

    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    mvbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    mvbox.set_vexpand(True)
    mvbox.set_hexpand(True)
    mvbox.set_valign(Gtk.Align.CENTER)
    mvbox.set_halign(Gtk.Align.CENTER)
    vbox.append(mvbox)

    image_icon = Icon(pixel_size=style.LARGE_ICON_SIZE,
                      icon_name=icon_name,
                      stroke_color=style.COLOR_BUTTON_GREY.get_svg(),
                      fill_color=style.COLOR_TRANSPARENT.get_svg())
    image_icon.set_margin_top(style.DEFAULT_PADDING)
    image_icon.set_margin_bottom(style.DEFAULT_PADDING)
    mvbox.append(image_icon)

    label = Gtk.Label(label='<span foreground="%s"><b>%s</b></span>' %
                      (style.COLOR_BUTTON_GREY.get_html(),
                       message))
    label.set_use_markup(True)
    label.set_margin_top(style.DEFAULT_PADDING)
    label.set_margin_bottom(style.DEFAULT_PADDING)
    mvbox.append(label)

    hbox = Gtk.Box()
    open_image_btn = Gtk.Button()
    open_image_btn.connect('clicked', btn_callback)
    add_image = Gtk.Image.new_from_icon_name("list-add")
    buttonbox = Gtk.Box()
    buttonbox.append(add_image)
    lbl = Gtk.Label(label=btn_label)
    lbl.set_hexpand(True)
    lbl.set_halign(Gtk.Align.FILL)
    lbl.set_margin_start(5)
    lbl.set_margin_end(5)
    buttonbox.append(lbl)
    open_image_btn.set_child(buttonbox)
    open_image_btn.set_hexpand(True)
    open_image_btn.set_halign(Gtk.Align.CENTER)
    hbox.append(open_image_btn)
    hbox.set_margin_top(style.DEFAULT_PADDING)
    hbox.set_margin_bottom(style.DEFAULT_PADDING)
    mvbox.append(hbox)

    empty_widgets.append(vbox)
    empty_widgets.set_visible(True)
    activity.set_canvas(empty_widgets)
