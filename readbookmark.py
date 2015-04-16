# Copyright 2009 One Laptop Per Child
# Author: Sayamindu Dasgupta <sayamindu@laptop.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import json


class Bookmark:

    def __init__(self, data):
        self.md5 = data[0]
        self.page_no = data[1]
        self.content = data[2]
        self.timestamp = data[3]
        self.nick = data[4]
        self.color = data[5]
        self.local = data[6]

    def belongstopage(self, page_no):
        return self.page_no == page_no

    def is_local(self):
        return bool(self.local)

    def get_note_title(self):
        if self.content == '' or self.content is None:
            return ''

        note = json.loads(self.content)
        return note['title']

    def get_note_body(self):
        if self.content == '' or self.content is None:
            return ''

        note = json.loads(self.content)
        return note['body']

    def get_as_dict(self):
        return {'md5': self.md5,
                'page_no': self.page_no,
                'content': self.content,
                'timestamp': self.timestamp,
                'nick': self.nick,
                'color': self.color,
                'local': self.local}

    def compare_equal_to_dict(self, _dict):
        return _dict['md5'] == self.md5 and \
            _dict['page_no'] == self.page_no and\
            _dict['content'] == self.content and \
            _dict['timestamp'] == self.timestamp and \
            _dict['nick'] == self.nick and \
            _dict['color'] == self.color and \
            _dict['local'] == self.local
