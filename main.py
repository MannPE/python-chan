import black
import boardsettings
import requests
import lxml
import time
import json
import threading
from bs4 import BeautifulSoup
import re
import urllib.request
from pathlib import Path
import os

media_regex = "(\/\/i(?:s|)\d*\.(?:4cdn|4chan)\.org\/\w+\/(\d+\.(?:jpg|png|gif|webm)))"

class ThreadMonitor:
    def __init__(self, thread_url, save_dir, request_queue):
        self.thread_url = thread_url
        self.image_counter = 0
        self.update_timer = 20
        self.save_dir = save_dir
        self.request_queue = request_queue
        self.pending_executions = False
        self.request_failed = False
        if not os.path.exists(save_dir):
            try:
                os.makedirs(save_dir)
            except:
                print("Could not create download directory", save_dir, " closing...")
                self.request_failed = True
    
    def __refresh_thread_images(self):
        print("Getting new images from thread:", self.thread_url)
        self.pending_executions = False
        # try:
        html_text = requests.get(self.thread_url).text
        media_matches = re.findall(media_regex, html_text);
        old_counter = self.image_counter
        for match in media_matches:
            saved_filename = os.path.normpath(self.save_dir + "/" + match[1])
            if not os.path.exists(saved_filename):
                urllib.request.urlretrieve("http:"+match[0], saved_filename)
                self.image_counter = self.image_counter + 1
                print(f'Thread {self.thread_url}: new image #{self.image_counter} downloaded')
        if old_counter >= self.image_counter:
            # delay requests when threads start getting stale
            self.update_timer = self.update_timer + 10
        else:
            # do faster requests when threads are hot
            self.update_timer = max(20, self.update_timer - 20)
        # except:
        #     print(f'Something fucked up - thread {self.thread_url}  will close now')
        #     self.request_failed = True
            
        
    def start_downloading(self):
        print("Start observing thread:", self.thread_url)
        while(not self.request_failed):
            if not self.pending_executions:
                self.request_queue.append(self.__refresh_thread_images)
                self.pending_executions = True
            time.sleep(self.update_timer) 
            


class BoardMonitor:
    def __init__(self, board_name, keywords, queue):
        self.board_name = board_name
        self.keywords = keywords
        self.monitored_threads = {}
        self.ignored_threads = {}
        self.refresh_timer_seconds = 60
        self.request_queue = queue
        self.pending_executions = False
        print("started monitor for:", board_name)

    def __update_catalog(self):
        print("checking catalog for", self.board_name)
        thread_url = f'https://a.4cdn.org/{self.board_name}/catalog.json'
        thread_pages = json.loads(requests.get(thread_url).text)
        new_threads = []
        for page in thread_pages:
            for thread in page["threads"]:
                thread_id = thread["no"]
                if thread_id in self.monitored_threads or thread_id in self.ignored_threads:
                    return
                first_keyword_match = "" 
                for keyword in (self.keywords) :
                    if "com" in thread and keyword in thread["com"]:
                        first_keyword_match = keyword
                        break
                if first_keyword_match == "":
                    self.ignored_threads[thread_id] = False
                else:
                    self.monitored_threads[thread_id] = {"keyword": first_keyword_match, "total": 0}
                    new_threads.append(thread["no"])
        self.__run_new_threads(new_threads)
    
    def __run_new_threads(self, new_threads):
        for thread_id in new_threads:
            cwd = os.getcwd()
            keyword = "/" +self.monitored_threads[thread_id]["keyword"]
            final_dir = os.path.normpath(cwd + "/"+ "downloads" + keyword+ "/"+ self.board_name + "/"+ str(thread_id) + "/")
            thread_monitor = ThreadMonitor(f'https://boards.4chan.org/{self.board_name}/thread/{thread_id}',final_dir, self.request_queue)
            thread = threading.Thread(target = thread_monitor.start_downloading, args = ( ))
            thread.start()

    
    def start_monitoring(self):
        while True: 
            if not self.pending_executions:
                self.request_queue.append(self.__update_catalog)
                self.pending_executions = True
            time.sleep(self.refresh_timer_seconds)

        
        

class GlobalMonitor:
    def __init__(self):
        self.current_execution_seconds = 0
        self.request_queue = []
    
    def start_board_monitors(self):
        try:
            board_list = boardsettings.defaultSettings
            global_keywords = board_list.pop("global")
            for board_name, keywords in board_list.items():
                boardMonitor = BoardMonitor(board_name, keywords + global_keywords, self.request_queue)
                thread = threading.Thread(target = boardMonitor.start_monitoring, args = ( ))
                thread.start()
            
            while True:
                time.sleep(2)
                print("queue length:", len(self.request_queue))
                if len(self.request_queue) > 0:
                    self.request_queue[0]()
                    self.request_queue.pop(0)
        except (KeyboardInterrupt, SystemExit):
            print ("\nKeyboard interrupted\n")


monitor = GlobalMonitor()
monitor.start_board_monitors()

