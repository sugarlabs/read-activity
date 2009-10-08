import webkit
import gtk


class _WebView(webkit.WebView):
    def __init__(self):
        webkit.WebView.__init__(self)
        
    def get_page_height(self):
        '''
        Gets height (in pixels) of loaded (X)HTML page.
        This is done via javascript at the moment
        '''        
        #TODO: Need to check status of page load
        js = 'oldtitle=document.title;document.title=Math.max(document.body.scrollHeight, document.body.offsetHeight,document.documentElement.clientHeight, document.documentElement.scrollHeight, document.documentElement.offsetHeight);'
        self.execute_script(js)
        ret = self.get_main_frame().get_title()
        js = 'document.title=oldtitle;'
        self.execute_script(js)
        if ret is None:
            return 0
        return int(ret)
        
    def add_bottom_padding(self, incr):
        '''
        Adds incr pixels of padding to the end of the loaded (X)HTML page.
        This is done via javascript at the moment
        '''        
        js = ('var newdiv = document.createElement("div");newdiv.style.height = "%dpx";document.body.appendChild(newdiv);' % incr)
        self.execute_script(js)
        
