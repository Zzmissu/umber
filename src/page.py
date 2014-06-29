# -- coding: utf-8 --
"""
 page.py

 a Page corresponds to both
    (a) a URL, and
    (b) a file or folder in the filesystem.

 Pages are not in the sql database (and not part of the 'model' per se),
 though there are some file and folder meta-data that may be in the
 database such as course assignments and student submitted work.
  
  TODO  find some way to cache (path,course,user,privilege) connections,
        either in the filesystem or the database.)

  TODO  the conversion of markdown or wiki files to html could be
        cached in sql database Page objects. If so, a hash would be
        needed to keep track of whether the file had changed since the
        sql data had been cached. That could speed things up assuming
        the hash computation is faster than the markdown conversion)
        at the cost of database size and code complexity.
 
 --- paths, folders, urls, and all that ---

 The vocabulary terms that I'm using to describe file and url addresses
 for courses, directories, and files are 'path', 'basename', and 'name.
 I'll use an example to illustrate.

 If the settings on my laptop development machine are

    os_base    /Users/mahoney/academics/umber/courses
    url_base   umber

 then for the 'notes/week1' file within a course at 'fall/math'
 we would have

    url     http://localhost:8090/  umber    /  fall/math   /  notes/week1
                   host             url_base    course_path    file_path
                       
    file    /Users/mahoney/academics/umber/courses / fall/math  / notes/week1
            os_base                                  course_path  file_path
                 
 My definitions are then
 
    path         address after base
                 e.g. fall/math               for this course
                      fall/math/notes/week1   for this file

    basename     last word in address (same as os.path.basename)
                 e.g. math                    for this course
                      week1                   for this file
                      
    file name    address after course's path (without leading slash)
                 e.g. notes/week1
    
    course name  anything (actual name of course, not part of address)
                 e.g. "Math 101" (or any)

 This url would have in its flask request object the attributes

    request.url_root        'http://localhost:8090/'
    request.path            '/umber/fall/math/notes/week1'
                  
 Leading slashes are left off my paths.
                  
 This implies that
    * course and file paths do not start with or end with slashes.
    * course and file paths are unique
    * course_path + file_name = file_path
    * file paths always have a course path as a prefix
    * files with the same name may be in many courses (i.e. notes/week1)

 Folders have nearly the same notion of path, basename, and name as files, i.e.
    * their path has the course path as a prefix, and
    * their name is the address within the course
      (which may be the empty string if it the top folder in a course).
 The difference is that folder paths always end in a trailing slash,
 as do their URLs. If the trailing slash for a folder is missing,
 the URL redirects.
    * url     http://localhost:8090/umber/fall/math/notes/
              http://localhost:8090/umber/fall/math/notes  redirects to notes/
    * path    fall/math/notes/
            
 A Page corresponds to a URL for a file or a folder, not a course.
 (And in fact the path for a course e.g. fall/math is not that 
 same as the path for that course's top folder e.g. fall/math/ .)

 Some file suffixes which are understood by the umber framework
 and displayed within the course layout (.wiki = media-wiki-ish markup,
 .md = markdown-ish markup, .umber = special page) are optional
 (and generally discouraged) in URLs . 

 
"""

import os, arrow, yaml
from settings import os_base, http_port, https_port, timezone
from model import anonymous_person, db_session, Course
from glob import glob

expand_extensions = ('.umber', '.md', '.wiki', '.html')
access_filename = '.access.yaml'

class ArrowTime(object):
    """ Convert between time representations.
        In the sqlite database, times are stored as ISO strings
        including a timezone-aware offset, like these.
        >>> ArrowTime('2013-01-01T12:24:52.3327-05:00').str()
        '2013-01-01T12:24:52-05:00'
        >>> ArrowTime(1402606871).str() # an epoch-sec timestamp (time.time())
        '2014-06-12T17:01:11-04:00'
    """
    # See http://crsmithdev.com/arrow/ for this arrow.py python module.
    # For time differences, subtract two of these (givin a datetime.timedelta)
    # and then use .seconds, .total_seconds(), .resoultion etc.
    def __init__(self, *args, **kwargs):
        """ With no arguments, returns the 'now' time. """
        self.arrow = arrow.get(*args, **kwargs).to(timezone)
    def __str__(self):
        """ ISO representation rounded down to the nearest second """
        return self.arrow.floor('second').isoformat()
    def human(self):
        """ Return in human friendly form, e.g. 'seconds ago'"""
        return self.arrow.humanize()
    def str(self):
        return str(self)

def getext(filename):
    """ Return file extension, i.e. '.html' from '/foo/bar/baz.html' """
    return os.path.splitext(filename)[1]

def get_course(pagepath):
    """ Return course that pagepath is in
        >>> get_course('demo/a/b/c').name
        u'Demo Course'
        >>> get_course('foo/bar/baz').name
        u'Umber'
    """
    # i.e. the course whose coursepath is the longest prefix of pagepath 
    # example: page.path = 'demo/home', course.path = 'demo'
    courses = Course.filter('LIKE(path || "%" , :pagepath)'
                            ).params(pagepath=pagepath).all()
    if not courses:
        raise Exception('OOPS - no Course for pagepath "{}"'.format(pagepath))
    return max(courses, key = lambda c: len(c.path))

def csv_to_list(csv_string):
    """ Return list of strings given string of comma-seperated-values
        >>> csv_to_list('a, b, c')
        ['a', 'b', 'c']
    """
    return map(lambda string: string.strip(), csv_string.split(','))

def get_permissions(absdir):
    """ Given an absolute folder path (without trailing slash),
        recursively search for its access file.
        Return permission dict {'read': set(...), 'write': set(...)}
        where the elements of the sets are username or role strings.
        >>> p = Page('demo/students/johnsmith/foo/bar/baz')
        >>> get_permissions(p.dirabspath)['read']
        set(['johnsmith'])
    """
    # Looking for an access file (i.e. .access.yaml) in
    # this folder, or its parent, or its parent's parent - first found.
    # The highest legit folder is os_base, which should have an access file.
    relative = os.path.relpath(absdir, os_base)
    if len(relative) > 1 and relative[0:2] == '..':
        # a parent of os_base - shouldn't get here, but if so : "no access"
        return {'read': set(), 'write': set()}  
    try:
        access_abspath = os.path.join(absdir, access_filename)
        with open(access_abspath) as accessfile:
            perms = yaml.load(accessfile.read())
        return {key: set(csv_to_list(value)) for (key,value) in perms.items()}
    except IOError:
        return get_permissions(os.path.dirname(absdir))


class Page(object):
    """ a url-accessable file or folder in a Course """
        # __init__ args        example
        # -----------------    --------------
        #    path              'demo/home'
        #    request.url       'http://localhost:8080/umber/demo/home'
        #    request.url_root  'http://localhost:8080/'
        #    request.path      '/umber/demo/home' 
        #    user              Person(username='bob', id=...) # None is valid
        #
        # attributes            example
        # --------------        ---------------
        #    page.user          Person(username='bob', id=...)
        #    page.path          'demo/home'
        #    page.basename      'home'  # os.path.basename (but no extension)
        #    page.abspath       '/Users/.../umber/courses/demo/home.wiki'
        #    page.isdir         False   # os.path.isdir
        #    page.isfile        True    # os.path.isfile 
        #    page.exists        True    # os.path.exists
        #    page.extension     '.wiki' 
        #    page.dirabspath    '/Users/.../umber/courses/demo' # file's folder
        #    page.lastmodified  '2014-06-12T17:01:11-04:00'
        #    page.request       flask Request(...)
        #    page.url           'http://localhost:8080/umber/demo/home'
        #    page.secure_url    'https://localhost:8433/umber/demo/home'
        #    page.course        Course(name='Demo Course')
        #    page.permissions   {'read': set(['all']), 'write':set(['bob']}
        #    page.can_read      True
        #    page.can_write     True
    
    def __init__(self, 
                 path = None,    # URL=host/url_base+path eg /demo/home
                 request = None, # flask Request object
                 user = None     # Person
                 ):
        
        self.user = user or anonymous_person()
        self.path = path
        self.course = get_course(self.path)
        self.abspath = os.path.join(os_base, path)
        if len(path) > 0 and path[-1]=='/':
            # when path ends in a slash, e.g. '/foo/bar/'
            # the basename (i.e. name of this folder) here will be 'bar',
            # which isn't os.path.basename's behavior.
            self.basename = os.path.basename(path[:-1])
        else:
            self.basename = os.path.splitext(os.path.basename(path))[0]
        if os.path.isdir(self.abspath):
            (self.isdir, self.isfile) = (True, False)
        elif os.path.isfile(self.abspath):
            (self.isdir, self.isfile) = (False, True)
        else:
            (self.isdir, self.isfile) = (False, False)
            # TODO : search for file extensions, adjust abspath
            if self.abspath[-1] != '/':
                existing_exts = set(map(getext, glob(self.abspath + '.*')))
                if existing_exts:
                    for ext in expand_extensions:
                        if ext in existing_exts:
                            # found file with valid expansion of file path
                            # e.g. from 'demo/home' to 'demo/home.md'
                            self.abspath = self.abspath + ext
                            self.isfile = True
                            break
        self.exists = self.isdir or self.isfile
        self.extension = getext(self.abspath)
        if self.isdir:
            self.dirabspath = self.abspath
        else:
            self.dirabspath = os.path.dirname(self.abspath)
        self.permissions = get_permissions(self.dirabspath)
        # .get_read, .get_write
        if self.exists:
            self.lastmodified = str(ArrowTime(os.path.getmtime(self.abspath)))
        else:
            self.lastmodified = ''
        if request:
            self.request = request
            if request.is_secure:
                secure_host = request.host
                host = secure_host.replace(str(https_port), str(http_port))
            else:
                host = request.host
                secure_host = host.replace(str(http_port), str(https_port))
            self.secure_url = 'https://' + secure_host + request.path
            self.url = 'http://' + host + request.path            
        else: # may be useful without web request, at least for debugging
            self.request = None
            self.secure_url = ''
            self.url = ''
        
        self.uri_links = '- uri_links -'
        
    def __str__(self):
        return "<Page path='{}' id={}>".format(self.path, id(self))


if __name__ == "__main__":
    import doctest
    doctest.testmod()

