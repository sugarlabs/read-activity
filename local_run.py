#!/usr/bin/env python3

import sys
import os
import traceback
import faulthandler

faulthandler.enable()
import gi
import cairo

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk

gi.require_foreign("cairo")

import dbus.mainloop.glib
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

# Force the Sugar GTK theme so icons and CSS render correctly in standalone mode
os.environ.setdefault("GTK_THEME", "Sugar")
# Set up standalone environment
os.environ.setdefault("SUGAR_BUNDLE_ID", "org.laptop.sugar.ReadActivity")
os.environ.setdefault("SUGAR_BUNDLE_NAME", "Read")
os.environ.setdefault("SUGAR_BUNDLE_PATH", os.getcwd())
os.environ.setdefault("SUGAR_ACTIVITY_ROOT", os.path.expanduser("~/.sugar/default/org.laptop.sugar.ReadActivity"))

activity_root = os.environ["SUGAR_ACTIVITY_ROOT"]
for subdir in ["tmp", "instance", "data"]:
    os.makedirs(os.path.join(activity_root, subdir), exist_ok=True)

from sugar4.activity.activityhandle import ActivityHandle
from readactivity import ReadActivity

def main():
    def on_activate(app):
        icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        icon_theme.add_search_path(os.path.join(os.getcwd(), "icons"))

        # Load the CSS Provider
        css_provider = Gtk.CssProvider()
        css_path = os.path.join(os.getcwd(), "activity.css")
        if os.path.exists(css_path):
            css_provider.load_from_path(css_path)
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
            
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-icon-theme-name", "Sugar")
        settings.set_property("gtk-theme-name", "Sugar")

        handle = ActivityHandle(
            activity_id="read-local",
            object_id="read-local"
        )
        try:
            win = ReadActivity(handle)
            app.add_window(win)
            win.present()
        except Exception as e:
            print("Failed to launch activity: %s" % e, file=sys.stderr)
            traceback.print_exc()
            app.quit()

    app = Gtk.Application(application_id="org.laptop.sugar.ReadActivity.local")
    app.connect("activate", on_activate)
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
