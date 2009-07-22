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

import zipfile
import tempfile
import os, os.path
from lxml import etree
import shutil

import navmap, epubinfo


class _Epub(object):
    def __init__(self, filepath):
        self._filepath = filepath
        self._zobject = None
        self._obffile = None
        self._titlepage = None
        self._obfpath = None
        self._ncxpath = None
        self._ncxfile = None
        self._basepath = None
        self._tempdir = tempfile.mkdtemp()
        
        if not self._verify():
            print 'Warning: This does not seem to be a valid epub file'
        
        self._get_obf()
        self._get_ncx()
        self._get_titlepage()
        
        self._ncxfile = self._zobject.open(self._ncxpath)
        self._navmap = navmap.NavMap(self._ncxfile, self._basepath, self._titlepage)
        
        self._obffile = self._zobject.open(self._obfpath)
        self._info = epubinfo.EpubInfo(self._obffile) 
        
        self._unzip()
        
    def _unzip(self):
        #self._zobject.extractall(path = self._tempdir) # This is broken upto python 2.7
        orig_cwd = os.getcwd()
        os.chdir(self._tempdir)
        for name in self._zobject.namelist():
            if name.startswith(os.path.sep): # Some weird zip file entries start with a slash, and we don't want to write to the root directory
                name = name[1:]
            if name.endswith(os.path.sep) or name.endswith('\\'):
                os.makedirs(name)
            else:
                self._zobject.extract(name)
        os.chdir(orig_cwd)

                
    def _get_obf(self):
        containerfile = self._zobject.open('META-INF/container.xml')
        
        tree = etree.parse(containerfile)
        root = tree.getroot()
        
        for element in root.iterfind('.//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile'):
            if element.get('media-type') == 'application/oebps-package+xml':
                self._obfpath = element.get('full-path')
        
        if self._obfpath.rpartition('/')[0]:        
            self._basepath = self._obfpath.rpartition('/')[0] + '/'
        else:
            self._basepath = ''
            
        containerfile.close()


    def _get_ncx(self):
        obffile = self._zobject.open(self._obfpath)
        
        tree = etree.parse(obffile)
        root = tree.getroot()

        for element in root.iterfind('.//{http://www.idpf.org/2007/opf}item'):
            if element.get('media-type') == 'application/x-dtbncx+xml' or \
                element.get('id') == 'ncx':
                self._ncxpath = self._basepath + element.get('href')
        
        obffile.close()
        
    def _get_titlepage(self):
        obffile = self._zobject.open(self._obfpath)
        tree = etree.parse(obffile)
        root = tree.getroot()

        for element in root.iterfind('.//{http://www.idpf.org/2007/opf}item'):
            if element.get('id') == 'titlepage':
                    self._titlepage = self._basepath + element.get('href')
        
        obffile.close()                    
        
                    
    def _verify(self):
        '''
        Method to crudely check to verify that what we 
        are dealing with is a epub file or not
        '''
        if not os.path.exists(self._filepath):
            return False
        
        self._zobject = zipfile.ZipFile(self._filepath)
        
        if not 'mimetype' in self._zobject.namelist():
            return False
        
        mtypefile = self._zobject.open('mimetype')
        mimetype = mtypefile.readline()
        
        if mimetype != 'application/epub+zip':
            return False
        
        return True
    
    def get_toc_model(self):
        return self._navmap.get_gtktreestore()
    
    def get_flattoc(self):
        return self._navmap.get_flattoc()
    
    def get_basedir(self):
        return self._tempdir
    
    def get_info(self):
        return self._info
    
    def close(self):
        self._zobject.close()
        shutil.rmtree(self._tempdir)
