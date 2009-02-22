import logging

import sqlite3
import time

import gconf

from readbookmark import Bookmark

_logger = logging.getLogger('read-activity')

class BookmarkManager:
    def __init__(self, filehash, dbpath='read.db'):
        self._filehash = filehash
        self._conn = sqlite3.connect(dbpath)
        self._cur = self._conn.cursor()
        
        self._bookmarks = []
        self._populate_bookmarks()
        
    def add_bookmark(self, page, title, local=1):
        # locale = 0 means that this is a bookmark originally 
        # created by the person who originally shared the file
        timestamp = time.time()
        client = gconf.client_get_default()
        user = client.get_string("/desktop/sugar/user/nick")
        color = client.get_string("/desktop/sugar/user/color")

        t = (self._filehash, page, title, timestamp, user, color, local)
        self._cur.execute('insert into bookmarks values (?, ?, ?, ?, ?, ?, ?)', t)
        self._conn.commit()
        
        self._resync_bookmark_cache()
        
    def del_bookmark(self, page):
        client = gconf.client_get_default()
        user = client.get_string("/desktop/sugar/user/nick")

        # We delete only the locally made bookmark
        
        t = (self._filehash, page, user)
        self._cur.execute('delete from bookmarks where md5=? and page=? and user=?', t)
        self._conn.commit()
        
        self._resync_bookmark_cache()

    def _populate_bookmarks(self):
        # TODO: Figure out if caching the entire set of bookmarks is a good idea or not
        self._cur.execute('select * from bookmarks where md5=? order by page', (self._filehash,))

        for row in self._cur:
            self._bookmarks.append(Bookmark(row))
            
    def get_bookmarks_for_page(self, page):
        bookmarks = []
        for bookmark in self._bookmarks:
            if bookmark.belongstopage(page):
                bookmarks.append(bookmark)
        
        return bookmarks
    
    def _resync_bookmark_cache(self):
        # To be called when a new bookmark has been added/removed
        self._bookmarks = []
        self._populate_bookmarks()


    def get_prev_bookmark_for_page(self, page, wrap = True):
        if not len(self._bookmarks):
            return None
        
        if page <= self._bookmarks[0].page_no and wrap:
            return self._bookmarks[-1]
        else:
            for i in range(page-1, -1, -1):
                for bookmark in self._bookmarks:
                    if bookmark.belongstopage(i):
                        return bookmark
                
        return None 


    def get_next_bookmark_for_page(self, page, wrap = True):
        if not len(self._bookmarks):
            return None
        
        if page >= self._bookmarks[-1].page_no and wrap:
            return self._bookmarks[0]
        else:
            for i in range(page+1, self._bookmarks[-1].page_no + 1):
                for bookmark in self._bookmarks:
                    if bookmark.belongstopage(i):
                        return bookmark
        
        return None            
