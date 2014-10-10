# ORAL ARGUMENT SCRAPER
# brad.heath@gmail.com, @bradheath
# Script to scrape and store metadata on U.S. Court of Appeals oral arguments
# Scrapes 1st, 3rd, 4th, 5th, 6th, 7th, 8th, 9th, D.C. and Fed. Circuits and SCOTUS
# Capable of multithreading scrapes, 
#
# TODO
# - Update social shares for arguments that will be happening TODAY
# - Update 9th Cir. scrapes so the model knows what to do if it finds a case
#   that moves from the schedule to being actually argued
# 		- Determine whether we already have the case (query method)
# 		- Load the case
#		- Change its status and assign media
#		- Re-save the case (requires new save)
# - Figure out which arguments are prominent, give them special status
# - Enhance logging
# - Attempt to standardize/modularize more of the scrape code


import sys
import time
import datetime
import urllib2
from datetime import date
from bs4 import BeautifulSoup
from dateutil.parser import parse
import os
import MySQLdb
import re
import feedparser
import multiprocessing
import mechanize

# Import my libraries
from arguments_log import argumentLog
from arguments_settings import argumentSettings

# Set up required connections and classes
settings = argumentSettings()
log = argumentLog()
db = MySQLdb.connect(settings.dbhost, settings.dbuser, settings.dbpass, settings.dbname, charset = 'UTF8').cursor(MySQLdb.cursors.DictCursor)

# Import optional dependencies
if settings.downloadandconvert:
	from pydub import AudioSegment


if settings.FFMpegLocation != '':
	AudioSegment.ffmpeg = settings.FFMpegLocation

# A simple class that describes a court from the database
# Retrieved by the court's unique id
class court:

	court_id = ''
	short_name = ''
	bluebook_name = ''
	proper_name = ''
	settings = ''
	
	def __init__(self, id):
		settings = argumentSettings()
		db.execute(""" SELECT * FROM """ + settings.dbname + """.""" + settings.dbtable_courts + """ 
						WHERE court_id = %s """, (id,))
		h = db.fetchone()
		self.court_id = id
		self.short_name = h['short_name']
		self.bluebook_name = h['bluebook_name']
		self.proper_name = h['proper_name']
		return
		

# A class that describes each oral argument in the index
# Methods for reading and writing arguments from the database
class argument:

	# Attributes and default values
	_uid = ''
	_caption = ''
	_docket_no = ''
	_case_url = ''
	_media_url = ''
	_media_type = ''
	_media_size = 0
	_original_media_type = ''
	_original_media_size = 0
	_original_media_url = ''
	_counsel = ''
	_issues = ''
	_argued = ''
	_duration = 0
	_judges = ''
	_court_id = 0
	_status = 'argued'
	_added = ''
	_date_scheduled = ''

	def __init__(self, docket_no = '', caption = '', case_url = '', \
		media_url = '', media_type = '', media_size = 0, counsel = '', \
		issues='', judges = '', argued='', duration = 0, court_id = 0, uid=None,
		status = 'argued', date_scheduled = '' ):
		self._docket_no = docket_no
		self._caption = caption
		self._case_url = case_url
		self._media_url = media_url
		self._media_type = media_type
		self._media_size = media_size
		self._original_media_type = media_type
		self._original_media_url = media_url
		self._original_media_size = media_size
		self._counsel = counsel
		self._issues = issues
		self._judges = judges
		self._argued = argued
		self._duration = duration
		self._court_id = court_id
		self._status = status
		self._date_scheduled = date_scheduled
		self.checkDB()
		if uid == None:
			if self._argued == '':
				self._uid = str(self._court_id) + '__' + self._docket_no.replace(' ','') \
					+ '__' + str(self._date_scheduled).replace(' ','_')
			else:
				self._uid = str(self._court_id) + '__' + self._docket_no.replace(' ','') \
					+ '__' + str(self._argued).replace(' ','_')
		return
		
	def exists(self):
		db.execute(""" SELECT COUNT(*) AS c FROM """ + settings.dbname + """.""" \
			+ settings.dbtable + """ WHERE uid = %s """, (self._uid, ))
		if db.fetchone()['c'] == 0:
			return False
		else:
			return True

	def convertAttempt(self):
		db.execute(""" UPDATE """ + settings.dbname + """.""" + settings.dbtable + """
			SET convert_attempts = convert_attempts + 1 WHERE uid = %s """,
			(self._uid, ))
		return
			
	def updateMediaUrl(self, newUrl):
		self._media_url = newUrl
		self._media_type = newUrl[-3:].lower()
		db.execute(""" UPDATE """ + settings.dbname + """.""" + settings.dbtable + """
			SET media_type = %s, media_url = %s WHERE uid = %s """,
			(self._media_type, self._media_url, self._uid))
		return
		
	def load(self, uid):
		db.execute(""" SELECT * FROM """ + settings.dbname + """.""" + settings.dbtable + """
			WHERE uid = %s """, (uid, ))
		h = db.fetchone()
		self._uid = h['uid']
		self._court_id = h['court_id']
		self._media_url = h['media_url']
		self._media_type = h['media_type']
		self._original_media_url = h['original_media_url']
		self._original_media_type = h['original_media_type']
		self._status = h['status']
		self._issues = h['issues']
		self._date_scheduled = h['date_scheduled']
		self._added = h['added']
		self._case_url = h['case_url']
		self._argued = h['argued'],
		self._issues = h['issues'],
		self._judges = h['judges'],
		self._original_media_size = h['original_media_size']
		self._caption = h['caption']
		self._docket_no = h['docket_no']

	def update(self, media_type = None, media_url = None, argued = None, added = None,
		original_media_url = None, original_media_type = None, status = None):

		if media_type != None and media_type <> self._media_type:
			self._media_type = media_type
		if media_url != None and media_url <> self._media_url:
			self._media_url = media_url
		if argued != None and argued <> self._argued:
			self._argued = argued
		if original_media_url != None and original_media_url <> self._original_media_url:
			self._original_media_url = original_media_url
		if original_media_type != None and original_media_type <> self._original_media_type:
			self._original_media_type = original_media_type
		if argued != None and argued <> self._argued:
			self._argued = argued
		if status != None and status <> self._status:
			# Also handle social shares here when the status changes
			if self._status == 'scheduled' and status == 'argued':
				if settings.tweetnew:
					share.tweet(self)
			self._status = status
		return
	
	def save(self):
		# Save an already existing record
		if self._uid == 0:
			print "  # EXCEPTION: You cannot update a case without a valid UID"
		else:
			try:
				db.execute(""" UPDATE """ + settings.dbname + """.""" + settings.dbtable + """
					SET docket_no = %s,
						caption = %s,
						case_url = %s,
						media_url = %s,
						media_type = %s, 
						media_size = %s,
						counsel = %s,
						issues = %s,
						judges = %s,
						argued = %s, 
						duration = %s,
						court_id = %s,
						added = %s,
						original_media_type = %s,
						original_media_size = %s,
						original_media_url = %s,
						status = %s,
						date_scheduled = %s
					WHERE uid = %s """,
					(self._docket_no, self._caption, self._case_url, self._media_url,
					self._media_type, self._media_size, self._counsel, self._issues,
					self._judges, self._argued, self._duration, self._court_id,
					self._added, self._original_media_type, self._original_media_size,
					self._original_media_url, self._status, self._date_scheduled,
					self._uid, ))
			except:
				sql = db._last_executed
				err = str(sys.exc_info()[0]) + ' -> ' + str(sys.exc_info()[1])
				log.log('ERROR (DB)', err + ' in ' + sql)
		return
	
	def write(self):
		if self._court_id == 0:
			print '  # EXCEPTION: You cannot write to an unspecified court '
		else:
			# Handle the optional stuff - media conversion, social shares, etc. 
			if settings.downloadandconvert == True:
				filename = utils.localFileName(prefix=self._court_id, url=self._media_url)
				f = utils.convertFile(self._media_url, filename)
			if settings.tweetnew:
				share.tweet(self)
				
			# Clean up anything that might have been missed in passing data to the argument
			if self._status == 'argued':
				if self._media_type == '':
					self._media_type = self._media_url[-3:].lower()
				u = argumentUtils()
				if self._media_size == 0:
					self._media_size = u.getRemoteSize(self._media_url)
				
			print '   - NEW: ' + self._caption
			try:
				db.execute(""" REPLACE INTO """ + settings.dbname + """.""" + settings.dbtable + """
					(uid, docket_no, caption, case_url, media_url, media_type, media_size, counsel, issues, judges, argued, duration, court_id, added,
					original_media_type, original_media_size, original_media_url,
					status, date_scheduled) 
					VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(),
					%s, %s, %s, %s, %s) """,
					(self._uid, self._docket_no, self._caption, self._case_url,
					self._media_url, self._media_type, self._media_size, 
					self._counsel, self._issues, self._judges, self._argued,
					self._duration, self._court_id, 
					self._original_media_type, self._original_media_size,
					self._original_media_url, self._status, self._date_scheduled ))
			except:
				sql = db._last_executed
				err = str(sys.exc_info()[0]) + ' -> ' + str(sys.exc_info()[1])
				log.log('ERROR (DB)', err + ' in ' + sql)
	
	def checkDB(self):
		if str(type(db)) == "<class 'MySQLdb.cursors.DictCursor'>":
			db.execute(""" SHOW TABLES FROM """ + settings.dbname + """ LIKE %s """, 
				(settings.dbtable, ))
			h = db.fetchall()
			if len(h) == 0:
				sql = """ CREATE TABLE IF NOT EXISTS """ + settings.dbname + "." + settings.dbtable \
					+ """ (
							uid VARCHAR(255) PRIMARY KEY,
							court_id INT,
							docket_no VARCHAR(255),
							caption VARCHAR(255),				
							case_url VARCHAR(255),
							media_url VARCHAR(255),
							media_type VARCHAR(10),
							original_media_url VARCHAR(255),
							original_media_type VARCHAR(10),
							original_media_size DOUBLE,
							media_size DOUBLE,
							counsel VARCHAR(255),
							issues VARCHAR(255),
							judges VARCHAR(255),
							argued DATE,
							duration INT,
							modified TIMESTAMP,
							added DATETIME,
							status VARCHAR(255),
							date_scheduled DATETIME,
							date_schedule_added DATETIME,
							KEY date_scheduled_idx(date_scheduled),
							KEY status_idx(status),
							KEY status_argued_idx(status, argued),
							KEY status_argued_court_id_idx(status,argued,court_id),
							KEY docket_no_idx(docket_no),
							KEY added_idx(added),
							KEY modified_idx(modified),
							KEY court_id_idx(court_id),
							KEY court_id_added_idx(court_id,added),
							KEY duration_idx(duration),
							KEY caption_idx(caption),
							KEY media_type_idx(media_type),
							KEY argued_idx(argued),
							KEY argued_court_id_idx(argued, court_id),
							FULLTEXT KEY caption_ftidx(caption),
							FULLTEXT KEY issues_ftidx(issues),
							FULLTEXT KEY counsel_ftidx(counsel),
							FULLTEXT KEY judges_ftidx(judges),
							FULLTEXT KEY all_ftidx(caption,issues,counsel,judges)
						) ENGINE=MyISAM, CHARACTER SET=UTF8"""
				db.execute(sql)
			db.execute(""" SHOW TABLES FROM """ + settings.dbname + """ LIKE %s """, 
				(settings.dbtable_courts, ))
			h = db.fetchall()
			if len(h) == 0:
				sql = """ CREATE TABLE IF NOT EXISTS """ + settings.dbname + """.""" + settings.dbtable_courts \
					+ """ (
							court_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
							short_name VARCHAR(255),
							bluebook_name VARCHAR(255),
							proper_name VARCHAR(255),
							KEY short_name_idx(short_name),
							KEY bluebook_name_idx(bluebook_name)
						) ENGINE=MyISAM """
				db.execute(sql)
				sql = """ INSERT INTO """ + settings.dbname + """.""" + settings.dbtable_courts \
					+ """ (short_name, bluebook_name, proper_name) 
							VALUES(%s, %s, %s) """
				from arguments_courts import courts_list
				
				db.executemany(sql, (courts_list))
			db.execute(""" SHOW TABLES FROM """ + settings.dbname + """ LIKE %s """, (settings.dbtable_urls, ))
			h = db.fetchall()
			if len(h) == 0:
				sql = """ CREATE TABLE IF NOT EXISTS """ + settings.dbname + """.""" + settings.dbtable_urls \
					+ """(
							url VARCHAR(255) PRIMARY KEY,
							modified TIMESTAMP,
							r INT DEFAULT 0
						) ENGINE=MyISAM """
				db.execute(sql)
		return


# Utility class for social tools
class argumentShare:
	
	twitterAPI = ''
	settings = ''
	
	def __init__(self):
		import twitter
		settings = argumentSettings()
		
		if settings.tweetnew:
			self.twitterAPI = twitter.Api(
				consumer_key = settings.twitter_consumer_key,
				consumer_secret = settings.twitter_consumer_secret,
				access_token_key = settings.twitter_access_token_key,
				access_token_secret = settings.twitter_access_token_secret
			)		
		return
		
	def tweet(self, arg):
		c = court(arg._court_id)
		msg = ''
		caption = arg._caption
		yesterday = date.today() - datetime.timedelta(1)
		daybefore = date.today() - datetime.timedelta(1)
		
		# Customize a message based on the day of the week
#		print "Argued: "
#		print arg._argued
#		print "Today:" 
#		print parse(time.strftime("%x"))
		
		if len(arg._caption) > 57:
			caption = arg._caption[:57] + '...'
		if arg._argued == parse(time.strftime("%x")):	
			msg = 'NEW: Today\'s argument in ' + caption + ', ' + c.bluebook_name + ' ' + arg._media_url
		elif(arg._argued == parse(yesterday.strftime("%x"))):
			msg = "Yesterday's " + c.bluebook_name + " argument in " + caption + ": " + arg._media_url
		elif(arg._argued == parse(daybefore.strftime("%x"))):
			msg = c.bluebook_name + " argument in " + caption + ": " + arg._media_url
			
		# Don't share things that are older than the day before yesterday
		if msg != '':
			self.twitterAPI.PostUpdate(msg)
			log.log('share','TWEET: ' + msg)
		return
	
	def fb(self, arg):
		return
	
# Utility class for querying and altering arguments		
class argumentUtils:

	def query(self, court_id = 0, docket_no = '', caption = '', issues = '', status = ''):
		results = []
		
		if court_id == 0 and docket_no == '' and caption == '' and issues == '':
			results = False
		else:
			terms = []
			sql = """ SELECT uid, court_id FROM """ + settings.dbname + """.""" + settings.dbtable \
				+ """ WHERE """
			if status <> '':
				terms.append(' status = "' + status + '" ')
			if court_id <> 0:
				terms.append(" court_id = " + str(court_id))
			if docket_no <> '':
				terms.append(' docket_no = "' + docket_no + '" ')
			if caption <> '':
				terms.append(' caption = "' + caption + '" ')

			i = 0
			for t in terms:
				sql += t
				if i < len(terms) - 1:
					sql += " AND " 
				i += 1
			db.execute(sql)
			h = db.fetchall()
			
			# Return a list of arguments
			for c in h:
				arg = argument()
				arg.load(c['uid'])
				results.append(arg)
		
		return results
				
	def convertMostRecent(self):
		db.execute(""" SELECT uid, court_id, media_url FROM """ + settings.dbname + """.""" + settings.dbtable + """
					WHERE media_type <> 'mp3' 
					AND convert_attempts <= 5
					AND argued >= DATE_ADD(CURRENT_DATE(), INTERVAL -180 DAY)
					ORDER BY argued DESC, modified DESC LIMIT %s""", 
					(settings.convertHowmany,))
		h = db.fetchall()
		if len(h) > 0:
			for case in h:
				arg = argument()
				arg.load(case['uid'])
				arg.convertAttempt()
				newurl = self.convertFile(case['media_url'], self.localFileName(case['media_url'], prefix=case['court_id']))
				if newurl != '':
					arg.updateMediaUrl(newurl)
	
	def convertDate(self, date, format):
		if format == 'rss':
			TS = re.compile('\d\d:\d\d:\d\d')
			date = re.sub(TS, '00:00:00', date)
			d = parse(date,ignoretz=True)
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
		db.execute(""" SELECT r FROM """ + settings.dbname + """.""" + settings.dbtable_urls + """ WHERE
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
			db.execute(""" REPLACE INTO """ + settings.dbname + """.""" + settings.dbtable_urls + """
				(url, r) VALUES(%s, %s)""", (url, r, ))
		else:
			if h[0]['r'] == 1:
				valid = True
		return valid
	
	def localFileName(self, url, prefix = ''): 
		FILESYNTAX = re.compile(r'/(\d.*?)$', re.IGNORECASE)
		if prefix != '':
			prefix = str(prefix) + '_'
		ender = re.search(FILESYNTAX, url).group(1)
		filename = re.sub('[\. ]', '_', prefix) + re.sub(r'[\(\)\.\,\& -\%\*\?\/]','_', ender)
		return filename
	
	def convertFile(self, url, local, verbose=True):
		try:
			if verbose:
				print '   (downloading ' + local + ')'
			format = url[-3:]
			localMp3 = local[:-4] + '.mp3'
			if settings.localTemp[-1] != '/':
				settings.localTemp += '/'
			if settings.localPublish[-1] != '/':
				settings.localPublish += '/'
			localTempFile = settings.localTemp + local
			localMp3File = settings.localPublish + localMp3
			localMp3URL = settings.localPublishRelative + localMp3
			if format != 'mp3':
				if utils.downloadFile(url, localTempFile):
					if settings.FFMpegLocation != '':			
						AudioSegment.converter = settings.FFMpegLocation
					AudioSegment.from_file(localTempFile).export(localMp3File, format='mp3', bitrate='96k')
					# THEN add an updated media URL and media type
					# THEN add a cleanup routine to delete copies that are not in top x00
					# THEN add a routine to do this update for already-stored media
					os.remove(localTempFile)
		except:
			err = str(sys.exc_info()[0]) + ' -> ' + str(sys.exc_info()[1])
			log.log('ERROR', err)
			localMp3URL = ''
		return localMp3URL
	
	def downloadFile(self, url, local):
		try:
			request = urllib2.Request(url)
			urlfile = urllib2.urlopen(request)
			chunk = 4096 * 2
			f = open(local, "wb")
			while 1:
				data = urlfile.read(chunk)
				if not data:
					break
				f.write(data)
			return True
		except:
			return False

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
		db.execute(""" SELECT court_id FROM """ + settings.dbname + """.""" + settings.dbtable_courts + """
					WHERE bluebook_name = %s """, (bluebook, ))
		return db.fetchone()['court_id']
	

# HERE ARE THE ROUTINES THAT SCRAPE INDIVIDUAL COURT SITES
# ----------------------------------------------------------------------

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
		err = 'In scrape_1st(): ' + str(sys.exc_info()[0]) + ' -> ' + str(sys.exc_info()[1])
		log.log('ERROR', err)
		
def scrape_3rd():
	print '-> Updating 3rd Cir. data'
	court_id = utils.getCourt("3d Cir.")
	URL = 'http://www2.ca3.uscourts.gov/oralargument/OralArguments.xml'
	TITLEPARSE = re.compile('^([\d-]{4,})', re.IGNORECASE)
	MEDIAMEAT = re.compile('audio/[\d\-\&]{4,}(.*?)\.(wma|mp3)', re.IGNORECASE);
	try:
		feed = feedparser.parse(URL)
		for item in feed.entries:
			media_url = item.link.replace(' ', '%20')
			if utils.checkValidMediaUrl(media_url):
				if re.search(TITLEPARSE, item.title.replace('_','-')):
					caption = ''
					docket_no = re.search(TITLEPARSE, item.title.replace('_','-')).group(1)
					argued = utils.convertDate(item.description, 'mdy')
					# SOMETHING IS WRONG IN YOUR RE HERE
					if re.search(MEDIAMEAT, media_url):
						caption = re.search(MEDIAMEAT, media_url).group(1)
						caption = re.sub('([a-z])([A-Z])', '\g<1> \g<2>', caption)
						caption = caption.replace('_', ' ').replace('%20',' ')
						caption = re.sub(r'v ', ' v. ', caption)
					
					arg = argument(docket_no = docket_no, court_id = court_id, media_url = 
						media_url, argued = argued, caption = caption)
					if not arg.exists():
						arg.write()
	except:
		err = 'In scrape_3rd(): ' + str(sys.exc_info()[0]) + ' -> ' + str(sys.exc_info()[1])
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
		err = 'In scrape_4th(): ' + str(sys.exc_info()[0]) + ' -> ' + str(sys.exc_info()[1])
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
		err = 'In scrape_5th(): ' + str(sys.exc_info()[0]) + ' -> ' + str(sys.exc_info()[1])
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
		err = 'In scrape_6th(): ' + str(sys.exc_info()[0]) + ' -> ' + str(sys.exc_info()[1])
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
		err = 'In scrape_7th(): ' + str(sys.exc_info()[0]) + ' -> ' + str(sys.exc_info()[1])
		log.log('ERROR', err)	
	return

def scrape_8th():
	print "-> Updating 8th Cir. data"
	court_id = utils.getCourt("8th Cir.")
	URL = 'http://8cc-www.ca8.uscourts.gov/circ8rss.xml'
	TITLEPARSE = re.compile('^([\d-]{4,}):(.*?)$', re.IGNORECASE)
	
	try:
		feed = feedparser.parse(URL)
		for item in feed.entries:
			if utils.checkValidMediaUrl(item.guid):
				docket_no = re.search(TITLEPARSE, item.title).group(1).strip()
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
		err = 'In scrape_8th(): ' + str(sys.exc_info()[0]) + ' -> ' + str(sys.exc_info()[1])
		log.log('ERROR', err)					
	return
	
def scrape_9th():
	print '-> Updating 9th Cir. data'
	court_id = utils.getCourt('9th Cir.')
	URL = 'http://www.ca9.uscourts.gov/media/?z=2'
	DT = re.compile('(\d\d)/(\d\d)/(\d\d\d\d)')
	
	#try:
	if 0 == 0:
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
					
						# See if we already have this in the database
						# If so, load it and update
						# If not, create
						q = utils.query(court_id = court_id, docket_no = docket_no, status = 'scheduled' )
						if q:
							if len(q) == 1:
								arg = q[0]
								arg.update(media_type = media_type, 
									media_url = media_url,
									argued = argued,
									status = 'argued')
								arg.save()
						else:
							arg = argument(docket_no = docket_no, court_id = court_id, 
								media_type = media_type, media_url = media_url, 
								argued = argued, judges = judges, caption = caption)
							if not arg.exists():
								arg.write()
			i += 1
	#except:
	#	err = str(sys.exc_info()[0]) + ' -> ' + str(sys.exc_info()[1])
	#	log.log('ERROR', err)	
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
				media_type = item.link[-3:].lower()
				#file = getFileDetails(item.link)
				argued = utils.convertDate(item.published, 'rss')
				print ' checking ' + caption
				arg = argument(docket_no = docket_no, caption = caption, media_url = media_url,
					argued = argued, court_id = court_id)
				if not arg.exists():
					arg.write()
	except:
		err = 'In scrape_dc(): ' + str(sys.exc_info()[0]) + ' -> ' + str(sys.exc_info()[1])
		log.log('ERROR', err)
	
	return
	
def scrape_scotus():
	print '-> Updating Sup. Ct. data'
	court_id = utils.getCourt('Sup. Ct.')
	URL = 'http://www.supremecourt.gov/oral_arguments/argument_audio/'
	DTARG = re.compile('Date Argued', re.IGNORECASE)
	TITLEPARSE = re.compile("([\d-]{3,})\. (.*?)$", re.IGNORECASE)
	MEDIABASE = 'http://www.supremecourt.gov/media/audio/mp3files/'
	
	try:
		html = urllib2.urlopen(URL).read()
		s = BeautifulSoup(html)
		
		for table in s.find_all('table', { 'class' : 'datatables' }):
			# Parse a results table
			i = 0
			for tr in table.find_all('tr'):
				if i > 0:
					td = tr.find_all('td')
					if not re.search(DTARG, td[1].text):
						argued = utils.convertDate(td[1].text.strip(), 'mdy')
						if re.search(TITLEPARSE, td[0].text):
							caption = re.search(TITLEPARSE, td[0].text).group(2).encode('ascii','ignore')
							print ' Checking ' + caption;
							docket_no = re.search(TITLEPARSE, td[0].text).group(1).encode('ascii','ignore')
							media_type = 'mp3'
							media_url = MEDIABASE + docket_no + '.mp3'
							if utils.checkValidMediaUrl(media_url):
								arg = argument( court_id = court_id, caption = caption,
									docket_no = docket_no, media_type = media_type,
									media_url = media_url, argued = argued)
								if not arg.exists():
									arg.write()
				i += 1
	
	except:
		err = str(sys.exc_info()[0]) + ' -> ' + str(sys.exc_info()[1])
		log.log('ERROR', err)	
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
			argued = utils.convertDate(item.published,'rss')
			if utils.checkValidMediaUrl(media_url):
				arg = argument( media_url = media_url, court_id = court_id, 
					media_type = media_type, docket_no = docket_no, caption = caption,
					argued = argued )
				if not arg.exists():
					arg.write()
	except:
		err = 'In scrape_fed(): ' + str(sys.exc_info()[0]) + ' -> ' + str(sys.exc_info()[1])
		log.log('ERROR', err)
	
	return
	
def scrape_st_ohio():
	return

def scrape_calendar_9th():
	# Scrape the argument calendar for the 9th Circuit
	court_id = utils.getCourt('9th Cir.')
	
	br = mechanize.Browser()
	startpage = 'http://www.ca9.uscourts.gov/calendar/'
	TABLEPATTERN = re.compile('<table class="main_table">.*?<th>(\d\d\d\d)-(\d\d)-(\d\d)\&nbsp;(.*?)<\/table><br\/>', re.IGNORECASE)
	CASEPATTERN = re.compile('<tr class=".*?content_row">.*?<a.*?>(.*?)</a>.*?<strong>(.*?)<\/strong> - (.*?)<span.*?<td.*?>(.*?)<\/td>', re.IGNORECASE)
	
	br.open(startpage)
	links = br.links(url_regex = 'calendar/view.php')
	newlinks = []
	for l in links:
		newlinks.append(l)
	
	for l in newlinks:
		# open argument page
		br.open(l.url)
		
		html = br.response().read()
		html = re.sub('[\n\r]',' ', html)

		for m in re.finditer(TABLEPATTERN, html):
			date_scheduled = m.group(1) + '-' + m.group(2) + '-' + m.group(3)
			#if date_scheduled > str(date.today()):
			if date_scheduled > str(date.today()):

				casehtml = m.group(4)
				for c in re.finditer(CASEPATTERN, casehtml):
					
					docket_no = c.group(1)
					caption = c.group(2)
					issues = c.group(4) + ': ' + c.group(3)
					status = 'scheduled'
				
					arg = argument(docket_no = docket_no, caption = caption,
						issues = issues, status = status, court_id = court_id,
						date_scheduled = date_scheduled )
					if not arg.exists():
						arg.write()
			
	
	return
	
utils = argumentUtils()
share = argumentShare()
	
if __name__ == '__main__':
	log.log('status','Job started')

	# Error checking
	c = argument()
	c.checkDB()

	# Now execute the scrapes
	scrapes = [scrape_1st, scrape_3rd, scrape_4th, scrape_5th, scrape_6th,
		scrape_7th, scrape_8th, scrape_9th, scrape_dc, scrape_fed, scrape_scotus,]

	if settings.multiprocess:
		pool = multiprocessing.Pool(processes=settings.maxprocesses)
	
	for scrape in scrapes:
		if settings.multiprocess:
			pool.apply_async(scrape, args=())
		else:
			scrape()
			
	if settings.multiprocess:
		pool.close()
		pool.join()
	
	log.log('status','Job finished')
