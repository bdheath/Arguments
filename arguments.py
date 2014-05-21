# ORAL ARGUMENT SCRAPER
# brad.heath@gmail.com, @bradheath
# Script to scrape and store metadata on U.S. Court of Appeals oral arguments
# Scrapes 1st, 3rd, 4th, 5th, 7th, 8th, 9th, D.C. and Fed. Circuits
#
# TODO
# - Add readme
# - Extract 3rd Cir. case metadata
# - Update argument class so new/updated cases can be shared, noticed

import sys
from dateutil.parser import parse
import time
import datetime
import urllib2
from bs4 import BeautifulSoup
import MySQLdb
import re
import feedparser
import multiprocessing
from arguments_log import argumentLog

# IMPORT dbaccess, which has default MySQL connection settings
sys.path.append('/')
from dbaccess import dbinfo

# SETTINGS 
# IMPORTANT CONFIGURATION SETTINGS HERE
dbhost = dbinfo.dbhost
dbuser = dbinfo.dbuser
dbpass = dbinfo.dbpass
dbname = 'court'
dbtable = 'arguments'
dbtable_courts = dbtable + '_courts'
dbtable_urls = dbtable + '_urls'
multiprocess = True
maxprocesses = 2

db = MySQLdb.connect(dbhost, dbuser, dbpass, dbname).cursor(MySQLdb.cursors.DictCursor)
log = argumentLog()

class argument:

	_uid = ''
	_caption = ''
	_docket_no = ''
	_case_url = ''
	_media_url = ''
	_media_type = ''
	_media_size = 0
	_counsel = ''
	_issues = ''
	_argued = ''
	_duration = 0
	_judges = ''
	_court_id = 0

	def __init__(self, docket_no = '', caption = '', case_url = '', \
		media_url = '', media_type = '', media_size = 0, counsel = '', \
		issues='', judges = '', argued='', duration = 0, court_id = 0):
		self._docket_no = docket_no
		self._caption = caption
		self._case_url = case_url
		self._media_url = media_url
		self._media_type = media_type
		self._media_size = media_size
		self._counsel = counsel
		self._issues = issues
		self._judges = judges
		self._argued = argued
		self._duration = duration
		self._court_id = court_id
		self.checkDB()
		self._uid = str(self._court_id) + '__' + self._docket_no.replace(' ','') \
			+ '__' + str(self._argued).replace(' ','_')
		return
		
	def exists(self):
		db.execute(""" SELECT COUNT(*) AS c FROM """ + dbname + """.""" \
			+ dbtable + """ WHERE uid = %s """, (self._uid, ))
		if db.fetchone()['c'] == 0:
			return False
		else:
			return True
		
	def write(self):
		if self._court_id == 0:
			print '  # EXCEPTION: You cannot write to an unspecified court '
		else:
			u = argumentUtils()
			if self._media_size == 0:
				self._media_size = u.getRemoteSize(self._media_url)
			db.execute(""" REPLACE INTO """ + dbname + """.""" + dbtable + """
					(uid, docket_no, caption, case_url, media_url, media_type, media_size, counsel, issues, judges, argued, duration, court_id, added) 
					VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()) """,
					(self._uid, self._docket_no, self._caption, self._case_url,
					self._media_url, self._media_type, self._media_size, 
					self._counsel, self._issues, self._judges, self._argued,
					self._duration, self._court_id, ))
	
	def checkDB(self):
		if str(type(db)) == "<class 'MySQLdb.cursors.DictCursor'>":
			db.execute(""" SHOW TABLES FROM """ + dbname + """ LIKE %s """, 
				(dbtable, ))
			h = db.fetchall()
			if len(h) == 0:
				sql = """ CREATE TABLE IF NOT EXISTS """ + dbname + "." + dbtable \
					+ """ (
							uid VARCHAR(255) PRIMARY KEY,
							court_id INT,
							docket_no VARCHAR(255),
							caption VARCHAR(255),				
							case_url VARCHAR(255),
							media_url VARCHAR(255),
							media_type VARCHAR(255),
							media_size DOUBLE,
							counsel VARCHAR(255),
							issues VARCHAR(255),
							judges VARCHAR(255),
							argued DATE,
							duration INT,
							modified TIMESTAMP,
							added DATETIME,
							KEY docket_no_idx(docket_no),
							KEY added_idx(added),
							KEY modified_idx(modified),
							KEY court_id_idx(court_id),
							KEY court_id_added_idx(court_id,added),
							KEY duration_idx(duration),
							KEY caption_idx(caption),
							FULLTEXT KEY caption_ftidx(caption),
							FULLTEXT KEY issues_ftidx(issues),
							FULLTEXT KEY counsel_ftidx(counsel),
							FULLTEXT KEY judges_ftidx(judges),
							FULLTEXT KEY all_ftidx(caption,issues,counsel,judges)
						) ENGINE=MyISAM """
				db.execute(sql)
			db.execute(""" SHOW TABLES FROM """ + dbname + """ LIKE %s """, 
				(dbtable_courts, ))
			h = db.fetchall()
			if len(h) == 0:
				sql = """ CREATE TABLE IF NOT EXISTS """ + dbname + """.""" + dbtable_courts \
					+ """ (
							court_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
							short_name VARCHAR(255),
							bluebook_name VARCHAR(255),
							proper_name VARCHAR(255),
							KEY short_name_idx(short_name),
							KEY bluebook_name_idx(bluebook_name)
						) ENGINE=MyISAM """
				db.execute(sql)
				sql = """ INSERT INTO """ + dbname + """.""" + dbtable_courts \
					+ """ (short_name, bluebook_name, proper_name) 
							VALUES(%s, %s, %s) """
				from arguments_courts import courts_list
				
				db.executemany(sql, (courts_list))
			db.execute(""" SHOW TABLES FROM """ + dbname + """ LIKE %s """, (dbtable_urls, ))
			h = db.fetchall()
			if len(h) == 0:
				sql = """ CREATE TABLE IF NOT EXISTS """ + dbname + """.""" + dbtable_urls \
					+ """(
							url VARCHAR(255) PRIMARY KEY,
							modified TIMESTAMP,
							r INT DEFAULT 0
						) ENGINE=MyISAM """
				db.execute(sql)
		return

class argumentUtils:
	
	def convertDate(self, date, format):
		if format == 'rss':
			d = parse(date)
			return d
		if format == 'mdy':
			d = parse(date)
			return d
		return

	def checkValidMediaUrl(self, url):
		MP3 = re.compile('mp3$', re.IGNORECASE)
		WMA = re.compile('wma$', re.IGNORECASE)
		valid = False
		
		# First see if we've already checked this
		db.execute(""" SELECT r FROM """ + dbname + """.""" + dbtable_urls + """ WHERE
			url = %s """, (url, ))
		h = db.fetchall()
		if len(h) == 0:
			# Haven't checked this yet; let's screen it
			if re.search(MP3, url) \
				or re.search(WMA, url):
				try:
					u = urllib2.urlopen(url)
					valid = True
				except:
					valid = False
			if valid:
				r = 1
			else:
				r = 0
			db.execute(""" REPLACE INTO """ + dbname + """.""" + dbtable_urls + """
				(url, r) VALUES(%s, %s)""", (url, r, ))
		else:
			if h[0]['r'] == 1:
				valid = True
		return valid
		
	def downloadFile(self, url, local):
		request = urllib2.Request(url)
		urlfile = urllib2.urlopen(request)
		chunk = 4096 * 2
		f = open(local, "wb")
		while 1:
			data = urlfile.read(chunk)
			if not data:
				break
			f.write(data)
		return

	def getFileDetails(self, url):
		MP3 = re.compile('mp3$', re.IGNORECASE)
		file = {}
		file['success'] = False
		file['time'] = 0
		if re.search(MP3, url):
			# Parse MP3 data
			tmpFile = '/scrape-temp.mp3'
			downloadFile(url, tmpFile)
			audio = MP3(tmpFile)
			#file['time'] = audio.info.length
			file['success'] = True		
		return file
		
	def getRemoteSize(self, url):
		usock = urllib2.urlopen(url)
		try:
			remoteSize = float(usock.info().get('Content-Length'))
		except:
			remoteSize = None
		return remoteSize
		
	def getCourt(self, bluebook):
		db.execute(""" SELECT court_id FROM """ + dbname + """.""" + dbtable_courts + """
					WHERE bluebook_name = %s """, (bluebook, ))
		return db.fetchone()['court_id']
	

def scrape_1st():
	print '-> Updating 1st Cir. data'
	court_id = utils.getCourt('1st Cir.')
	URL = 'http://media.ca1.uscourts.gov/files/audio/audiorss.php'
	TITLEPARSE = re.compile('Case:(.*?), (.*?)$', re.IGNORECASE)
	try:
		feed = feedparser.parse(URL)
		for item in feed.entries:
			media_url = item.link
			docket_no = re.search(TITLEPARSE, item.title).group(1)
			caption = re.search(TITLEPARSE, item.title).group(2)
			argued = utils.convertDate(item.published, 'rss')
			media_type = media_url[-3:].lower()
			if utils.checkValidMediaUrl(media_url):
				arg = argument( court_id = court_id, docket_no = docket_no,
					caption = caption, argued = argued, media_type = media_type,
					media_url = media_url )
				if not arg.exists():
					arg.write()
	except:
		err = str(sys.exc_info()[0]) + ' -> ' + str(sys.exc_info()[1])
		log.log('ERROR', err)
		
def scrape_3rd():
	print '-> Updating 3rd Cir. data'
	court_id = utils.getCourt("3d Cir.")
	URL = 'http://www2.ca3.uscourts.gov/oralargument/OralArguments.xml'
	TITLEPARSE = re.compile('^([\d-]{4,})', re.IGNORECASE)
	try:
		feed = feedparser.parse(URL)
		for item in feed.entries:
			media_url = item.link.replace(' ', '%20')
			if utils.checkValidMediaUrl(media_url):
				if re.search(TITLEPARSE, item.title.replace('_','-')):
					docket_no = re.search(TITLEPARSE, item.title.replace('_','-')).group(1)
					argued = utils.convertDate(item.description, 'mdy')
					arg = argument(docket_no = docket_no, court_id = court_id, media_url = media_url,
						argued = argued)
					if not arg.exists():
						arg.write()
	except:
		err = str(sys.exc_info()[0]) + ' -> ' + str(sys.exc_info()[1])
		log.log('ERROR', err)	
	return

def scrape_4th():
	URL = 'http://www.ca4.uscourts.gov/OAarchive/OAList.asp'
	print '-> Updating 4th Cir. data'
	court_id = utils.getCourt('4th Cir.')
	
	try:
		html = urllib2.urlopen(URL).read()
		s = BeautifulSoup(html)
		for tr in s.find_all('tr'):
			td = tr.find_all('td')
			if(len(td)) == 5:
				media_url = td[1].find('a')['href']
				if utils.checkValidMediaUrl(media_url):
					media_type = 'mp3'
					docket_no = td[1].text.strip()
					caption = td[2].string.strip()
					judges = td[3].string.strip()
					counsel = td[4].string.strip()
					argued = utils.convertDate(td[0].string.strip(), 'mdy')
					arg = argument(media_type = media_type, docket_no = docket_no,
						caption = caption, judges = judges, counsel = counsel,
						argued = argued, court_id = court_id, media_url = media_url)
					if not arg.exists():
						arg.write()
	except:
		err = str(sys.exc_info()[0]) + ' -> ' + str(sys.exc_info()[1])
		log.log('ERROR', err)	
	return

def scrape_5th():
	print '-> Updating 5th Cir. data'
	court_id = utils.getCourt('5th Cir.')
	URL = 'http://www.ca5.uscourts.gov/Rss.aspx?Feed=OralArgRecs'
	TITLEPARSE = re.compile('^([\d-]{4,})\s+(.*?)$', re.IGNORECASE)
	
	try:
		feed = feedparser.parse(URL)
		for item in feed.entries:
			media_url = item.link
			media_type = media_url[-3:].lower()
			docket_no = re.search(TITLEPARSE, item.title).group(1)
			caption = re.search(TITLEPARSE, item.title).group(2)
			argued = utils.convertDate(item.published.strip(), 'rss')
			if utils.checkValidMediaUrl(media_url):
				arg = argument(court_id = court_id, docket_no = docket_no, caption = caption,
					argued = argued, media_url = media_url, media_type = media_type)
				if not arg.exists():
					arg.write()		
	except:
		err = str(sys.exc_info()[0]) + ' -> ' + str(sys.exc_info()[1])
		log.log('ERROR', err)
	return
					
def scrape_6th():
	print '-> Updating 6th Cir. data'
	court_id = utils.getCourt('6th Cir.')
	URL = 'http://www.ca6.uscourts.gov/internet/court_audio/aud1.php'
	SUBTABLES = re.compile('<p class="copytxt01" style="margin-bottom: 0;">(<table.*?<\/table>)', re.IGNORECASE)
	DATE = re.compile('(\d\d-\d\d-\d\d\d\d)', re.IGNORECASE)
	TITLEPARSE = re.compile('^([\d-]{4,})\s+(.*?)$', re.IGNORECASE)
	LINK = re.compile('link=(.*?)&name', re.IGNORECASE)
	
	try:
		html = urllib2.urlopen(URL).read()
		html = re.sub(r'[\n\r]', '', html)
		html = re.sub(r'</tr></tr>','</tr>',html)
		html = re.sub(r'\s+', ' ', html)
		
		# Find date-specific tables within the HTML and iterate
		for m in re.finditer(SUBTABLES, html):
			
			# Parse the table
			s = BeautifulSoup(m.group(1))
			
			# Identify the first row, where the date is stored
			trs = s.find('table').find_all('tr')
			
			if re.search(DATE, trs[0].text):
				argued = utils.convertDate(re.search(DATE, trs[0].text).group(1), 'mdy')
				i = 0
				
				# Iterate through sub records (excluding first row)
				for tr in trs:
					if i > 0:
						td = tr.find_all('td')
						if re.search(TITLEPARSE, td[0].text.strip()):
							docket_no = re.search(TITLEPARSE, td[0].text).group(1)
							caption = re.search(TITLEPARSE, td[0].text).group(2)
							if re.search(LINK, td[1].find('a')['href']):
								media_url = re.search(LINK, td[1].find('a')['href']).group(1)
								media_url = re.sub(' ', '%20', media_url)
								media_type = media_url[-3:].lower()
								
								if utils.checkValidMediaUrl(media_url):
									arg = argument(court_id = court_id, argued = argued,
										media_url = media_url, media_type = media_type,
										caption = caption, docket_no = docket_no)
									if not arg.exists():
										arg.write()
					i += 1
	except:
		err = str(sys.exc_info()[0]) + ' -> ' + str(sys.exc_info()[1])
		log.log('ERROR', err)
	return
				
def scrape_7th():
	print '-> Updating 7th Cir. data'
	court_id = utils.getCourt('7th Cir.')
	MEDIABASE = 'http://media.ca7.uscourts.gov/'
	URL = 'http://media.ca7.uscourts.gov/oralArguments/oar.jsp?caseyear=&casenumber=&period=Past+month'
	URLEXTRACT = re.compile('href="(.*?)"', re.IGNORECASE)
	
	try:
		s = BeautifulSoup(urllib2.urlopen(URL).read())
		tables = s.find_all('table')
		i = 0
		for tr in tables[4].find_all('tr'):
			if i > 1:
				td = tr.find_all('td')
				if len(td) == 5:
					docket_no = td[0].text.strip()
					caption = td[1].text.strip()
					issues = td[2].text.strip()
					media_type = 'mp3'
					argued = utils.convertDate(td[3].text.strip(),'mdy')
					media_url = MEDIABASE + td[4].find('a')['href'].strip()
					if utils.checkValidMediaUrl(media_url):
						arg = argument( court_id = court_id, docket_no = docket_no,
							caption = caption, issues = issues, argued = argued,
							media_url = media_url, media_type = media_type)
						if not arg.exists():
							arg.write()
			i += 1
	except:
		err = str(sys.exc_info()[0]) + ' -> ' + str(sys.exc_info()[1])
		log.log('ERROR', err)	
	return

def scrape_8th():
	print "-> Updating 8th Cir. data"
	court_id = utils.getCourt("8th Cir.")
	URL = 'http://8cc-www.ca8.uscourts.gov/circ8rss.xml'
	TITLEPARSE = re.compile('^([\d-]{4,}:(.*?))$', re.IGNORECASE)
	
	try:
		feed = feedparser.parse(URL)
		for item in feed.entries:
			if utils.checkValidMediaUrl(item.guid):
				docket_no = re.search(TITLEPARSE, item.title).group(1)
				caption = re.search(TITLEPARSE, item.title).group(2).strip()
				media_url = item.guid
				media_type = 'mp3'
				argued = utils.convertDate(item.published, 'rss')
				arg = argument(docket_no = docket_no, caption = caption, media_url = media_url,
					media_type = media_type, argued = argued,
					court_id = court_id)
				if not arg.exists():
					arg.write()
	except:
		err = str(sys.exc_info()[0]) + ' -> ' + str(sys.exc_info()[1])
		log.log('ERROR', err)					
	return
	
def scrape_9th():
	print '-> Updating 9th Cir. data'
	court_id = utils.getCourt('9th Cir.')
	URL = 'http://www.ca9.uscourts.gov/media/?z=2'
	DT = re.compile('(\d\d)/(\d\d)/(\d\d\d\d)')
	
	try:
		html = urllib2.urlopen(URL).read()
		s = BeautifulSoup(html)
		tables = s.find_all('table')
		i = 0
		for tr in tables[5].find_all('tr'):
			if i > 0:
				td = tr.find_all('td')
				if len(td) == 7:
					docket_no = td[1].text.strip()
					caption = td[0].text.strip()
					judges = td[2].text.strip()
					argued = utils.convertDate(td[4].text.strip(), 'mdy')
					dt = re.search(DT, td[4].text.strip())
					media_url = 'http://cdn.ca9.uscourts.gov/datastore/media/' \
						+ dt.group(3) + '/' \
						+ dt.group(1) + '/' \
						+ dt.group(2) + '/' \
						+ docket_no + '.wma'
					media_type = 'wma'
					if utils.checkValidMediaUrl(media_url):
						arg = argument(docket_no = docket_no, court_id = court_id, 
							media_type = media_type, media_url = media_url, 
							argued = argued, judges = judges, caption = caption)
						if not arg.exists():
							arg.write()
			i += 1
	except:
		err = str(sys.exc_info()[0]) + ' -> ' + str(sys.exc_info()[1])
		log.log('ERROR', err)	
	return

def scrape_dc():
	print "-> Updating D.C. Cir. data"
	court_id = utils.getCourt("D.C. Cir.")
	URL = 'http://www.cadc.uscourts.gov/recordings/recordings.nsf/uscadcoralarguments.xml'
	TITLEPARSE = re.compile('^(.*?) \| (.*?)$', re.IGNORECASE)
	
	try:
		feed = feedparser.parse(URL)
		for item in feed.entries:
			if utils.checkValidMediaUrl(item.link):
				docket_no = re.search(TITLEPARSE, item.title).group(1)
				caption = re.search(TITLEPARSE, item.title).group(2)
				media_url = item.link
				#file = getFileDetails(item.link)
				argued = utils.convertDate(item.published, 'rss')
				arg = argument(docket_no = docket_no, caption = caption, media_url = media_url,
					argued = argued, court_id = court_id)
				if not arg.exists():
					arg.write()
	except:
		err = str(sys.exc_info()[0]) + ' -> ' + str(sys.exc_info()[1])
		log.log('ERROR', err)
	
	return
	
def scrape_scotus():
	return
	
def scrape_fed():
	print '-> Updating Fed. Cir. data'
	court_id = utils.getCourt('Fed. Cir.')
	URL = 'http://www.cafc.uscourts.gov/rss-audio-recordings.php'
	DESC = re.compile('Case Number: (.*?)$', re.IGNORECASE)

	try:
		feed = feedparser.parse(URL)
		for item in feed.entries:
			media_url = item.link
			media_type = media_url[-3:].lower()
			docket_no = re.search(DESC, item.description).group(1)
			caption = item.title
			argued = item.published
			if utils.checkValidMediaUrl(media_url):
				arg = argument( media_url = media_url, court_id = court_id, 
					media_type = media_type, docket_no = docket_no, caption = caption,
					argued = argued )
				if not arg.exists():
					arg.write()
	except:
		err = str(sys.exc_info()[0]) + ' -> ' + str(sys.exc_info()[1])
		log.log('ERROR', err)
	
	return
	
utils = argumentUtils()
	
if __name__ == '__main__':
	log.log('status','Job started')

	# Error checking
	c = argument()
	c.checkDB()

	# Now execute the scrapes
	scrapes = [scrape_1st, scrape_3rd, scrape_4th, scrape_5th, scrape_6th,
		scrape_7th, scrape_8th, scrape_9th, scrape_dc, scrape_fed, ]
	
	if multiprocess:
		pool = multiprocessing.Pool(processes=maxprocesses)
	
	for scrape in scrapes:
		if multiprocess:
			pool.apply_async(scrape, args=())
		else:
			scrape()
			
	if multiprocess:
		pool.close()
		pool.join()
	
	log.log('status','Job finished')
