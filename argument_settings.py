import sys

class argumentSettings: 

	# SETTINGS FOR DATABASE ACCESS
	# MINE ARE IMPORTED FROM AN INTERNAL FILE (IN ROOT)
	sys.path.append('/')
	from dbaccess import dbinfo
	dbhost = dbinfo.dbhost
	dbuser = dbinfo.dbuser
	dbpass = dbinfo.dbpass
	
	# SETTINGS FOR DATA STROAGE LOCATIONS
	dbname = 'court'
	dbtable = 'arguments'
	dbtable_courts = dbtable + '_courts'
	dbtable_urls = dbtable + '_urls'
	
	# SETTINGS FOR MULTIPROCESSING THE SCRAPE
	multiprocess = False
	maxprocesses = 4
		
	# THESE CONSTANTS DESCRIBE WHERE TO PUT FILES FOR MEDIA CONVERSION
	# NOTE THAT THIS REQUIRES ACCESS TO FFMPEG OR OTHER CONVERSION SOFTWARE
	# MEDIA CONVERSION IS AN OPTIONAL FEATURE
	# IF YOU ENABLE IT, THE SCRIPT WILL DOWNLOAD NON-MP3 FILES AND CONVERT
	# THEM TO MP3, THEN STORE THE RESULTS IN A FOLDER FOR PUBLIC ACCESS.
	# THIS WILL EAT UP DRIVE SPACE QUICKLY. 
	downloadandconvert = False
	localTemp = '/PATH/TO/TEMP/FOLDER/'
	localPublish = '/PATH/TO/PUBLIC/FOLDER/FOR/MEDIA/PUBLICATION/'
	localPublishRelative = '/Relative/Path/For/Online/Use'
	convertHowmany = 4
	FFMpegLocation = ''	# (Optional, only if it can't find ffmpeg)
	
	# SETTINGS FOR LOGFILE
	logfile = 'arguments.log'
