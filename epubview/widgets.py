import logging

import gi
gi.require_version('WebKit', '6.0')
gi.require_version('Gtk', '4.0')

from gi.repository import WebKit
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import GLib


class _WebView(WebKit.WebView):

    __gsignals__ = {
        'touch-change-page': (
            GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, ([bool])),
        'scrolled': (
            GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, ([float])),
        'scrolled-top': (
            GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, ([])),
        'scrolled-bottom': (
            GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, ([])),
        'selection-changed': (
            GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, ([bool])),
    }

    def __init__(self, **kwargs):
        cm = WebKit.UserContentManager()

        cm.register_script_message_handler('scrolled')
        cm.connect(
            'script-message-received::scrolled',
            lambda cm, result: self.emit(
                'scrolled', result.to_double()))

        cm.register_script_message_handler('scrolled_top')
        cm.connect(
            'script-message-received::scrolled_top',
            lambda cm, result: self.emit('scrolled-top'))

        cm.register_script_message_handler('scrolled_bottom')
        cm.connect(
            'script-message-received::scrolled_bottom',
            lambda cm, result: self.emit('scrolled-bottom'))

        cm.register_script_message_handler('selection_changed')
        cm.connect(
            'script-message-received::selection_changed',
            lambda cm, result: self.emit(
                'selection-changed', result.to_boolean()))

        cm.add_script(
            WebKit.UserScript(
                '''
window.addEventListener("scroll", function(){
    var handler = window.webkit.messageHandlers.scrolled;
    handler.postMessage(window.scrollY);
});
document.addEventListener("selectionchange", function() {
    var handler = window.webkit.messageHandlers.selection_changed;
    handler.postMessage(window.getSelection() != '');
});
                ''',
                WebKit.UserContentInjectedFrames.ALL_FRAMES,
                WebKit.UserScriptInjectionTime.START, None, None))

        cm.add_style_sheet(
            WebKit.UserStyleSheet(
                '''
html { margin: 50px; }
body { overflow: hidden; }
                ''',
                WebKit.UserContentInjectedFrames.ALL_FRAMES,
                WebKit.UserStyleLevel.USER, None, None))

        super().__init__(user_content_manager=cm, **kwargs)
        self.set_hexpand(True)
        self.set_vexpand(True)

    def do_context_menu(self, context_menu, hit_test_result):
        # Disable default WebKit context menu
        return True

    def setup_touch(self):
        self._click_gesture = Gtk.GestureClick.new()
        self._click_gesture.set_button(0)
        self._click_gesture.connect('pressed', self.__event_cb)
        self.add_controller(self._click_gesture)

    def __event_cb(self, gesture, n_press, x, y):
        view_width = self.get_width()
        if x > view_width * 3 / 4:
            self.emit('touch-change-page', True)
        elif x < view_width * 1 / 4:
            self.emit('touch-change-page', False)

    def _execute_script_sync(self, js):
        '''
        Executes JavaScript synchronously and returns the string result.
        '''
        res = ["0"]
        loop = GLib.MainLoop()

        def callback(self, task, user_data):
            try:
                result = self.evaluate_javascript_finish(task)
                if result is not None:
                    res[0] = result.to_string()
            except Exception as e:
                logging.error('Error executing script: %s', e)
            finally:
                loop.quit()

        self.evaluate_javascript(js, -1, None, None, None, callback, None)
        loop.run()
        return res[0]

    def get_page_height(self):
        '''
        Gets height (in pixels) of loaded (X)HTML page.
        This is done via javascript at the moment
        '''
        return int(self._execute_script_sync('''
            (function(){
                if (document.body == null) {
                    return 0;
                } else {
                    return Math.max(document.body.scrollHeight,
                        document.body.offsetHeight,
                        document.documentElement.clientHeight,
                        document.documentElement.scrollHeight,
                        document.documentElement.offsetHeight);
                };
            })()
        '''))

    def add_bottom_padding(self, incr):
        '''
        Adds incr pixels of margin to the end of the loaded (X)HTML page.
        '''
        self.evaluate_javascript(
            'document.body.style.marginBottom = "%dpx";' % (incr + 50), -1, None, None, None, None, None)

    def highlight_next_word(self):
        '''
        Highlight next word (for text to speech)
        '''
        self.evaluate_javascript('highLightNextWord();', -1, None, None, None, None, None)

    def go_to_link(self, id_link):
        self.evaluate_javascript('window.location.href = "%s";' % id_link, -1, None, None, None, None, None)

    def get_vertical_position_element(self, id_link):
        '''
        Get the vertical position of a element, in pixels
        '''
        # remove the first '#' char
        id_link = id_link[1:]
        return int(self._execute_script_sync('''
            (function(id_link){
                var obj = document.getElementById(id_link);
                var top = 0;
                if (obj.offsetParent) {
                    while(1) {
                        top += obj.offsetTop;
                        if (!obj.offsetParent) {
                            break;
                        };
                        obj = obj.offsetParent;
                        };
                } else if (obj.y) {
                    top += obj.y;
                }
                return top;
            })("%s")
        ''' % id_link))

    def scroll_to(self, to):
        '''
        Set the vertical position in a document to a value in pixels.
        '''
        self.evaluate_javascript('window.scrollTo(-1, %d);' % to, -1, None, None, None, None, None)

    def scroll_by(self, by):
        '''
        Modify the vertical position in a document by a value in pixels.
        '''
        self.evaluate_javascript(
            '''
(function(by){
    var before = window.scrollY;
    window.scrollBy(0, by);
    if (window.scrollY == before) {
        if (by < 0) {
            var handler = window.webkit.messageHandlers.scrolled_top;
            handler.postMessage(window.scrollY);
        } else if (by > 0) {
            var handler = window.webkit.messageHandlers.scrolled_bottom;
            handler.postMessage(window.scrollY);
        }
    }
}(%d))
            ''' % by, -1, None, None, None, None, None)
