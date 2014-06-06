import re
import datetime

from arguments_settings import argumentSettings
settings = argumentSettings


class argumentLog:

	_logfile = ''
	
	def __init__(self, logfile = settings.logfile ):
		self._logfile = logfile
		return
	
	def _formatLog(self, type, msg):
		time = str(datetime.datetime.now())
		msg = re.sub(r'[\n\r]', ' ', msg)
		return type + '\t' + time + '\t' + msg + '\r\n'
	
	def log(self, type, msg):
		logfile = open(self._logfile, 'a')
		logfile.write(self._formatLog(type,msg))
		logfile.close()