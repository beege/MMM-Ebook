This is a fork of [beege/MMM-Ebook](https://github.com/beege/MMM-Ebook]) updated to use Python3.

This utility scrapes Mr. Money Mustache's blog (http://www.mrmoneymustache.com/) and outputs HTML pages to import through a tool such as Calibre to create into an EBook of the desired format.

The bundled ebooks are current as of February 2022.

### Use

In the repo root, run ```pip install -r requirements.txt" to install dependencies```. After deps are installed, run **dump.py** in the repo root, and then import the file ```import_index.html_in_this_folder_in_calibre_to_create_ebook/index.html``` into Calibre where you can convert it to an ePub, mobi, or other format of your choice. Note: You will want to set Calibre to import HTML files in depth-first order by going to Preferences → Advanced → Plugins → File type → HTML to ZIP and checking **Add linked files in breadth first order**.

### MMM Approved!

You can see Mr Money Mustache's endorsement of this project [here](https://forum.mrmoneymustache.com/welcome-to-the-forum/making-a-mr-money-mustache-ebook/).

"Awesome work!! You hereby have my full approval to share this book (and work together to improve it if you like). As long as you give it away for free!"

### Future Updates

When I get a chance I plan to add automatic ebook generation through the calibre command-line tools.