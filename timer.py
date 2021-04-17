
from datetime import datetime, time

class Timer:

    def start(self):
        self.start_time = datetime.now()
        
    def get_time(self):
        return datetime.timedelta(datetime.now(), self.start_time)