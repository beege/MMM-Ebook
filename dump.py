#!/usr/bin/env python3
import os
import re
import sys
from urllib.parse import urlparse
from lxml import etree as ET
import urllib
from urllib.request import urlopen
import glob
import shutil
from pathlib import Path
import subprocess
from PIL import Image, ImageFile

# Cached data (RSS feed XML)
CACHED_DATA = os.path.join(os.path.dirname(__file__), ".cached")
CACHED_MEDIA = os.path.join(CACHED_DATA, "media")

CACHED_RSS_PREFIX = "rssPage"
CACHED_RSS_PAGENO = "%04u"
CACHED_RSS_SUFFIX = ".xml"

CACHED_URL_MAP_PATH = os.path.join(CACHED_DATA, 'url_maps')

MMM_RSS_URL = "http://www.mrmoneymustache.com/feed/?order=ASC&paged=%d"

IMG_MAX_WIDTH_PX = 800
ImageFile.LOAD_TRUNCATED_IMAGES = True

# Book data (use data here to construct ebook
BOOK_DATA = os.path.join(os.path.dirname(__file__), 
    "import_index.html_in_this_folder_in_calibre_to_create_ebook")
MEDIA = os.path.join(BOOK_DATA, "media")

class RSSParser(object):
    """Downloads (or reads from local file cache) RSS data of MMM feed"""
    
    def __init__(self, url, pageNo=None): 
        self.url = url # Confusing design - URL doubles as an actual URL or a cached local file
        self.pageNo = pageNo
              
        url = "file://" + self.url if Path(self.url).exists() else self.url
        print("Trying to open and parse RSS feed @ <" + url + ">...")
        doc = ET.parse(urlopen(url))
        self.root = doc.getroot()

        # Cache the page        
        if self.pageNo is not None:
           self.url = os.path.join(CACHED_DATA, CACHED_RSS_PREFIX + 
                CACHED_RSS_PAGENO % (self.pageNo, ) + CACHED_RSS_SUFFIX)
           ET.ElementTree(self.root).write(open(self.url, "wb"))
        
    def parse(self):   
        """Extract useful data from the RSS posting"""     
        for item in self.root.find('channel').findall('item'):
            title = item.find('title').text
            url = item.find('link').text            
            text = item.find('.//content:encoded', namespaces=self.root.nsmap).text
            date = item.find('pubDate').text
            author = item.find('.//dc:creator', namespaces=self.root.nsmap).text
            
            yield (
                title.encode('utf-8'), 
                text.encode('utf-8'), 
                url.encode('utf-8'),
                date.encode('utf-8'),
                author.encode('utf-8'))

def getCachedPostings():
    """Get a list of all the cached RSS data on disk"""
    filePaths = glob.glob(os.path.join(CACHED_DATA, 
        CACHED_RSS_PREFIX + '*' + CACHED_RSS_SUFFIX))
    filePaths.sort()
    return filePaths
            
def getLastPostPageNo():
    """Get the last RSS page number downloaded"""
    downloadedPages = getCachedPostings()
    if not downloadedPages or not len(downloadedPages):
        return 1 # Pages start at 1
    downloadedPages.sort()
    lastPage = downloadedPages[-1]
    
    return int(re.findall(os.path.join(CACHED_DATA, CACHED_RSS_PREFIX 
        + r'(\d+)' + CACHED_RSS_SUFFIX), lastPage)[0])
    

def getLatestRssDataFromMMM():
    """Download newest RSS pages - always redownloads last page as it may
        be updated"""
    if not os.path.isdir(CACHED_DATA):
        os.mkdir(CACHED_DATA)

    parsers = []
    pageNo = getLastPostPageNo()
    
    print("Downloading pages %d and newer" % (pageNo, ))
    
    while True:
        try:
            print(MMM_RSS_URL)
            parser = RSSParser(MMM_RSS_URL % (pageNo), pageNo)            
            parsers.append(parser)
            pageNo += 1
        except IOError as e:
            print(f'Failed to open last (end of detected RSS pages), error: {e}')
            break
            
    return parsers


def getRssData():
    """Gets a list of all RSS data from cache and downloads"""    
    parsers = []
    
    print("Parsing cached pages from disk")
    
    # First parse our cached pages
    for cachedPageFilePath in getCachedPostings():
         parsers.append(RSSParser(cachedPageFilePath)) # No page number necessary since cached
         
    parsers.extend(getLatestRssDataFromMMM())
    
    return parsers
    
class Post(object):
    """Once we have the RSS data and have started parsing it, we can break
        it down into posts"""
    next = 0

    def __init__(self, title, text, date, author, num=None):
        self.title = title
        self.text = text
        self.date = date
        self.author = author
        
        if num is None:
            num = Post.next
            Post.next = Post.next + 1
            self.localUrl = 'p%04d.html' % (num, )

def createPostingsFromParsedRss(parsers):
    """Create a list of all the posts from the RSS data"""
    postsInOrder = []
    posts = {}
    
    for parser in parsers:
        for (title, text, url, date, author) in parser.parse():
            postsInOrder.append(url)
            posts[url] = Post(title, text, date, author)      

    return (posts, postsInOrder)
    
                            
def getCachedUrlMaps():
    if not os.path.isdir(CACHED_DATA):
        os.mkdir(CACHED_DATA)
        
    if not os.path.isfile(CACHED_URL_MAP):
        return ({}, {})
    
    remoteToLocal, localToRemote = pickle.load(open(CACHED_URL_MAP, 'rb'))
     
    return (remoteToLocal, localToRemote)
    
def saveUrlMaps(remoteToLocal, localToRemote):
    if not os.path.isdir(CACHED_DATA):
        os.mkdir(CACHED_DATA)
        
    pickle.dump((remoteToLocal, localToRemote), open(CACHED_URL_MAP, 'wb'))
    
def rewritePostLinks(posts, postsInOrder):
    """We do this once we have all the posts since sometimes MMM goes back
        and edits earlier posts to include a link to a later posting"""
        
    print("Rewriting post links...")
            
    for url in postsInOrder:
        post = posts[url]
        text = post.text if isinstance(post.text, str) else post.text.decode('utf-8')

        for url2 in postsInOrder:
            regex = re.compile('<a\\s(.*href=")%s(".*)>(.*)</a>' % url2)
            post.text = regex.sub('<a \\1' + posts[url2].localUrl + '\\2>\\3</a>', text)
            
def rewriteImageLinks(posts):
    print("Rewriting image links...")

    if not os.path.isdir(CACHED_MEDIA):
        os.mkdir(CACHED_MEDIA)

    for post in posts.values():
        text = post.text if isinstance(post.text, str) else post.text.decode('utf-8')
        tree = ET.HTML(text)

        for image in tree.findall('.//img'):
            imageurl = image.attrib["src"]
            urlParseResult = urlparse(imageurl)
            path = urlParseResult.path
            imageFilename = urlParseResult.path.replace("/", "", 1) .replace("/", "_") # Create name from full path to help avoid accidentally overriding images, wordpress image paths have date component

            # Only include images actually hosted on mrmoneymustache.com
            if urlParseResult.hostname != "www.mrmoneymustache.com":
                print(f"Not including image in article {post.title} hosted at {imageurl}")
                continue

            # Cache images
            cachedImagePath = os.path.join(CACHED_MEDIA, imageFilename)
            if not Path(cachedImagePath).exists():
                try:
                    urllib.request.urlretrieve(imageurl, cachedImagePath)

                    # Resize images to a max width of 800px to save space
                    try:
                        image = Image.open(cachedImagePath)
                        image.LOAD_TRUNCATED_IMAGES = True
                        if not image.width <= 600:
                            aspectRatioChange = IMG_MAX_WIDTH_PX / image.width
                            height = int(image.height * aspectRatioChange)
                            newSize = (IMG_MAX_WIDTH_PX, height)
                            image = image.resize(newSize)

                        image.save(cachedImagePath, optimize=True, quality=85)
                    except IOError as e:
                        print(f'Failed to open image at path {cachedImagePath} for resize, caching at original resolution, error: {e}')
                except Exception as e:
                    print(f"Caching image {imageurl} to {localpath} failed with exception {e}")

            outputImageAbsolutePath = os.path.join(MEDIA, imageFilename)
            outputImageRelativePath = os.path.relpath(outputImageAbsolutePath, BOOK_DATA)
            shutil.copyfile(cachedImagePath, outputImageAbsolutePath)
            text = text.replace(imageurl, outputImageRelativePath)
        post.text = text
    
def createBookData(posts, postsInOrder):
    print("Creating book data...")
    
    index = open(os.path.join(BOOK_DATA, 'index.html'), 'w')
    
    index.write('''<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
    </head>
    <body>
      <h1>Table of Contents</h1>
      <p style="text-indent:0pt">''')
    for url in postsInOrder:
        post = posts[url]
        text = post.text if isinstance(post.text, str) else post.text.decode('utf-8')
        
        open(os.path.join(BOOK_DATA, post.localUrl), 'w').write(
            '<!DOCTYPE html>\n' + \
            '<html lang="en">\n' + \
                '<head>\n' + \
                    '<meta charset="UTF-8">\n' + \
                    '<title>' + post.title.decode('utf-8') + "</title>\n" + \
                '</head>\n' + \
                '<body>\n' + \
                    '<h1 class="chapter">' + post.title.decode('utf-8') + "</h1>\n" + \
                    '<h2>By ' + post.author.decode('utf-8') + "</h2>\n" + \
                    '<h2> ' + post.date.decode('utf-8') + "</h2>\n" + \
                    text + \
                '</body>' + \
            '</html>')
        index.write('<a href=%s>%s</a><br/>\n' % (post.localUrl, post.title.decode('utf-8')))
        
    index.write('''     </p>
   </body>
</html>''')

def generateEbooks():
    print("Generating eBooks...")

    subprocess.run(["ebook-convert", "import_index.html_in_this_folder_in_calibre_to_create_ebook/index.html", "Ebooks/mmm.azw3", "--title", "Financial Freedom Through Badassity", "--authors", "Mr. Money Mustache", "--no-inline-toc"])
    subprocess.run(["ebook-convert", "import_index.html_in_this_folder_in_calibre_to_create_ebook/index.html", "Ebooks/mmm.epub", "--title", "Financial Freedom Through Badassity", "--authors", "Mr. Money Mustache"])
    subprocess.run(["ebook-convert", "import_index.html_in_this_folder_in_calibre_to_create_ebook/index.html", "Ebooks/mmm.mobi", "--title", "Financial Freedom Through Badassity", "--authors", "Mr. Money Mustache", "--no-inline-toc"])
    subprocess.run(["ebook-convert", "import_index.html_in_this_folder_in_calibre_to_create_ebook/index.html", "Ebooks/mmm.pdf", "--title", "Financial Freedom Through Badassity", "--authors", "Mr. Money Mustache"])

    print("Finished generating Ebooks")

def main():
    if os.path.isdir(BOOK_DATA):
        shutil.rmtree(BOOK_DATA)

    os.mkdir(BOOK_DATA)
    os.mkdir(MEDIA)

    parsers = getRssData()
    (posts, postsInOrder) = createPostingsFromParsedRss(parsers)
    rewritePostLinks(posts, postsInOrder)
    rewriteImageLinks(posts)
    createBookData(posts, postsInOrder)
    generateEbooks()
            
if __name__=="__main__":
    main()