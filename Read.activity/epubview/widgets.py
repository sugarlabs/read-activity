import logging

from gi.repository import WebKit
from gi.repository import Gdk
from gi.repository import GObject


class _WebView(WebKit.WebView):

    __gsignals__ = {
        'touch-change-page': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE,
                              ([bool])), }

    def __init__(self, only_to_measure=False):
        WebKit.WebView.__init__(self)
        self._only_to_measure = only_to_measure

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

    def get_page_height(self):
        '''
        Gets height (in pixels) of loaded (X)HTML page.
        This is done via javascript at the moment
        '''
        hide_scrollbar_js = ''
        if self._only_to_measure:
            hide_scrollbar_js = \
                'document.documentElement.style.overflow = "hidden";'

        oldtitle = self.get_main_frame().get_title()

        js = """
            document.documentElement.style.margin = "50px";
            if (document.body == null) {
                document.title = 0;
            } else {
                %s
                document.title=Math.max(document.body.scrollHeight,
                    document.body.offsetHeight,
                    document.documentElement.clientHeight,
                    document.documentElement.scrollHeight,
                    document.documentElement.offsetHeight);
            };
        """ % hide_scrollbar_js
        self.execute_script(js)
        ret = self.get_main_frame().get_title()
        logging.error('get_page_height %s', ret)
        self.execute_script('document.title=%s;' % oldtitle)
        try:
            return int(ret)
        except ValueError:
            return 0

    def add_bottom_padding(self, incr):
        '''
        Adds incr pixels of padding to the end of the loaded (X)HTML page.
        This is done via javascript at the moment
        '''
        js = """
            var newdiv = document.createElement("div");
            newdiv.style.height = "%dpx";
            document.body.appendChild(newdiv);
        """ % incr
        self.execute_script(js)

    def highlight_next_word(self):
        '''
        Highlight next word (for text to speech)
        '''
        self.execute_script('highLightNextWord();')

    def go_to_link(self, id_link):
        self.execute_script('window.location.href = "%s";' % id_link)

    def get_vertical_position_element(self, id_link):
        '''
        Get the vertical position of a element, in pixels
        '''
        # remove the first '#' char
        id_link = id_link[1:]
        oldtitle = self.get_main_frame().get_title()
        js = """
            obj = document.getElementById('%s');
            var top = 0;
            if(obj.offsetParent) {
                while(1) {
                    top += obj.offsetTop;
                    if(!obj.offsetParent) {
                        break;
                    };
                    obj = obj.offsetParent;
                    };
            } else if(obj.y) {
                top += obj.y;
            };
            document.title=top;""" % id_link
        self.execute_script(js)
        ret = self.get_main_frame().get_title()
        self.execute_script('document.title=%s;' % oldtitle)
        try:
            return int(ret)
        except ValueError:
            return 0
