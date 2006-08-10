import gtk

from sugar.activity.Activity import Activity

class XbookActivity(Activity):
        def __init__(self):
                Activity.__init__(self)

                button = gtk.Button('drawing')
                self.add(button)
                button.show()
