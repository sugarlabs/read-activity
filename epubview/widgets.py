import gi
gi.require_version('WebKit2', '4.0')
gi.require_version('Gtk', '3.0')

from gi.repository import WebKit2
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject


class _WebView(WebKit2.WebView):

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
        cm = WebKit2.UserContentManager()

        cm.register_script_message_handler('scrolled')
        cm.connect(
            'script-message-received::scrolled',
            lambda cm, result: self.emit(
                'scrolled', result.get_js_value().to_double()))

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
                'selection-changed', result.get_js_value().to_boolean()))

        cm.add_script(
            WebKit2.UserScript(
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
                WebKit2.UserContentInjectedFrames.ALL_FRAMES,
                WebKit2.UserScriptInjectionTime.START, None, None))

        cm.add_style_sheet(
            WebKit2.UserStyleSheet(
                '''
html { margin: 50px; }
body { overflow: hidden; }
                ''',
                WebKit2.UserContentInjectedFrames.ALL_FRAMES,
                WebKit2.UserStyleLevel.USER, None, None))

        WebKit2.WebView.__init__(self, user_content_manager=cm, **kwargs)
        self.get_settings().set_enable_write_console_messages_to_stdout(True)

    def do_context_menu(self, context_menu, event, hit_test_result):
        # nope nope nope nopenopenopenenope
        return True

    def setup_touch(self):
        self.get_window().set_events(
            self.get_window().get_events() | Gdk.EventMask.TOUCH_MASK)
        self.connect('event', self.__event_cb)

    def __event_cb(self, widget, event):
        if event.type == Gdk.EventType.TOUCH_BEGIN:
            x = event.touch.x
            view_width = widget.get_allocation().width
            if x > view_width * 3 / 4:
                self.emit('touch-change-page', True)
            elif x < view_width * 1 / 4:
                self.emit('touch-change-page', False)

    def _execute_script_sync(self, js):
        '''
        This sad function aims to provide synchronous script execution like
        WebKit-1.0's WebView.execute_script() to ease porting.
        '''
        res = ["0"]

        def callback(self, task, user_data):
            Gtk.main_quit()
            result = self.run_javascript_finish(task)
            if result is not None:
                res[0] = result.get_js_value().to_string()

        self.run_javascript(js, None, callback, None)
        Gtk.main()
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
        self.run_javascript(
            'document.body.style.marginBottom = "%dpx";' % (incr + 50))

    def highlight_next_word(self):
        '''
        Highlight next word (for text to speech)
        '''
        self.run_javascript('highLightNextWord();')

    def go_to_link(self, id_link):
        self.run_javascript('window.location.href = "%s";' % id_link)

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
        self.run_javascript('window.scrollTo(-1, %d);' % to)

    def scroll_by(self, by):
        '''
        Modify the vertical position in a document by a value in pixels.
        '''
        self.run_javascript(
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
            ''' % by)
