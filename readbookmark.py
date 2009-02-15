class Bookmark:
    def __init__(self, data):
        self.md5 = data[0]
        self.page_no = data[1]
        self.title = data[2]
        self.timestamp = data[3]
        self.nick = data[4]
        self.color = data[5]
        self.local = data[6]
        
    def belongstopage(self, page_no):
        return self.page_no == page_no 
    
    def is_local(self):
        return bool(self.local)