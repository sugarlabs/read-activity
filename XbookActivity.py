import gtk

from sugar.activity.Activity import Activity

class XbookActivity(Activity):
        def __init__(self, service):
                Activity.__init__(self, service)

                button = gtk.Button('drawing')
                self.add(button)
                button.show()

