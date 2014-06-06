
What Arguments does
===================

Arguments is a Python script for scraping and storing oral argument metadata from federal courts of appeal. The script currently gathers data on arguments in the First, Third, Fourth, Fifth, Sixth, Seventh, Eighth, Ninth, D.C. and Federal circuits. It extracts links to the argument recordings and information about the case, including the caption, docket number, date argued, media format and other relevant details. (Some circuits provide more detail than others.) It stores the data in a MySQL table. 

I use this as the data collection routine for http://bradheath.org/arguments. 

Arguments can also share new entries to social media. My implementation posts every new recording to http://twitter.com/oralarguments.

The scrape follows three basic steps:

* First, it scrapes the court's website or RSS feed and extracts basic metadata from the argument (the docket number, case caption, date argued, etc), then standardizes the data. 
* Second, it verifies that each scraped argument links to a valid media file -- we don't want 404 errors.
* Third, it posts the argument. A summary optionally goes to social media; another gets stored in a MySQL table.

What Arguments CAN do (but doesn't on my site)
==============================================

A few courts (the Third and Ninth Circuits; sometimes the Fifth Circuit, too) post their argument recordings in a WMA format that doesn't play well with most browsers, or with most Javascript-based media players. That's not much help if your use case is to play the files in a browser. So Arguments includes a mode that will automatically download those recordings and conver them to MP3s using pydub and FFMpeg. Be warned, though, the file sizes can add up quickly. And the conversions are killer for anybody on a shared hosting platform.

What Arguments will do next
===========================
* Add more social media integration. This could include Facebook posts, etc. 
* Attempt to determine on the fly which arguments are teh most interesting, probably by checking the arguments against recent news coverage. Highlight the best. 

Requirements
============

Arguments uses:
* MySQLdb
* BeautifulSoup4
* feedparser
* pydub to handle optional media conversion (which also requires an installation of FFMpeg)

Use
===
Before you use these scripts, you'll need to configure **arguments_settings.py**. This file is where Arguments learns how to access your MySQL server, where it should keep the results, where it can create temporary files, where it can push public media files, whether the script should run using multiple threads, etc.

Arguments will automatically create MySQL tables to store the data if they do not already exist. 
