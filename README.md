
What Arguments does
===================

Arguments is a Python script for scraping and storing oral argument metadata from federal courts of appeal. The script currently gathers data on arguments in the First, Third, Fourth, Fifth, Sixth, Seventh, Eighth, Ninth, D.C. and Federal circuits. It extracts links to the argument recordings and information about the case, including the caption, docket number, date argued, media format and other relevant details. (Some circuits provide more detail than others.) It stores the data in a MySQL table. 

I use this as the data collection routine for http://bradheath.org/arguments. 

What Arguments does NOT do
==========================

Arguments does NOT download or store the actual recordings, because doing that would produce hundreds of gigabytes of audio data. 

Use
===
Pay attention to the #SETTINGS block at the top of the script, which is where you configure your database settings, determine whether the script should multiprocess, and decide where the results are stored. 

Arguments will automatically create MySQL tables to store the data if they do not already exist. 
