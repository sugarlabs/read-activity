import gtk

try:
    import webkit
except ImportError:
    import os, sys
    sys.path.append(os.path.join(os.environ['SUGAR_BUNDLE_PATH'], 'epubview', 'modules'))
    import webkit


class _WebView(webkit.WebView):
    def __init__(self):
        webkit.WebView.__init__(self)
        
    def get_page_height(self):
        #TODO: Need to check status of page load
        js = 'oldtitle=document.title;document.title=document.body.clientHeight;'
        self.execute_script(js)
        ret = self.get_main_frame().get_title()
        js = 'document.title=oldtitle;'
        self.execute_script(js)
        return int(ret)
        
    def add_bottom_padding(self, incr):
        js = ('var newdiv = document.createElement("div");newdiv.style.height = "%dpx";document.body.appendChild(newdiv);' % incr)
        self.execute_script(js)
        
