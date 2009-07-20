from lxml import etree
import gtk

class NavPoint(object):
    def __init__(self, label, contentsrc, children = []):
        self._label = label
        self._contentsrc = contentsrc
        self._children = children 
        
    def get_label(self):
        return self._label
    
    def get_contentsrc(self):
        return self._contentsrc
    
    def get_children(self):
        return self._children


class NavMap(object):
    def __init__(self, file, basepath):
        self._basepath = basepath
        self._tree = etree.parse(file)
        self._root = self._tree.getroot()
        self._gtktreestore = gtk.TreeStore(str, str)
        self._flattoc = []
        
        self._populate_toc()
 
    def _populate_toc(self):
        navmap = self._root.find('{http://www.daisy.org/z3986/2005/ncx/}navMap')       
        for navpoint in navmap.iterfind('./{http://www.daisy.org/z3986/2005/ncx/}navPoint'):
            self._process_navpoint(navpoint)
            
    def _gettitle(self, navpoint):
        text = navpoint.find('./{http://www.daisy.org/z3986/2005/ncx/}navLabel/{http://www.daisy.org/z3986/2005/ncx/}text')
        return text.text

    def _getcontent(self, navpoint):
        text = navpoint.find('./{http://www.daisy.org/z3986/2005/ncx/}content/')
        return self._basepath + text.get('src')

    def _process_navpoint(self, navpoint, parent = None):
        title = self._gettitle(navpoint)
        content = self._getcontent(navpoint)
        
        iter = self._gtktreestore.append(parent, [title, content])
        self._flattoc.append((title, content))
        
        childnavpointlist = list(navpoint.iterfind('./{http://www.daisy.org/z3986/2005/ncx/}navPoint'))
        
        if len(childnavpointlist):
            for childnavpoint in childnavpointlist:
                self._process_navpoint(childnavpoint, parent = iter)   
        else: 
            return
             
    def get_gtktreestore(self):
        return self._gtktreestore
    
    def get_flattoc(self):
        return self._flattoc
    
#t = TocParser('/home/sayamindu/Desktop/Test/OPS/fb.ncx')