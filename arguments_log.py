import re
import datetime

class argumentLog:

	# FORMAT FOR LOG FILE
	# Message Type (error, status, etc.)
	# Date/time
	# Error msg

	_logfile = ''
	
	def __init__(self, logfile = 'argument-scrape.log' ):
		self._logfile = logfile
		return
	
	def _formatLog(self, type, msg):
		time = str(datetime.datetime.now())
		msg = re.sub(r'[\n\r]', ' ', msg)
		return type + '\t' + time + '\t' + msg + '\n'
	
	def log(self, type, msg):
		logfile = open(self._logfile, 'a')
		logfile.write(self._formatLog(type,msg))
		logfile.close()