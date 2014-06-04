
What Arguments does
===================

Arguments is a Python script for scraping and storing oral argument metadata from federal courts of appeal. The script currently gathers data on arguments in the First, Third, Fourth, Fifth, Sixth, Seventh, Eighth, Ninth, D.C. and Federal circuits. It extracts links to the argument recordings and information about the case, including the caption, docket number, date argued, media format and other relevant details. (Some circuits provide more detail than others.) It stores the data in a MySQL table. 

I use this as the data collection routine for http://bradheath.org/arguments. 

What Arguments does NOT do
==========================

Arguments does NOT download or store the actual recordings (though it does give you the option if you choose), because doing that would produce hundreds of gigabytes of audio data. 

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
