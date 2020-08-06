#!/usr/bin/env python3
#
# Author: naisanza@gmail.com


import re
import os
import json
import stat
import time
import psutil
import shutil
import requests
import subprocess

from queue import Queue
from shutil import move
from subprocess import PIPE
from bs4 import BeautifulSoup
from concurrent.futures import (ThreadPoolExecutor, wait, as_completed)

from automon.log import Logging
from automon.helpers.sanitation import Sanitation


class Url:
    url = str
    name = str
    folder = str

    def __init__(self, url: str):

        self._log = Logging(Url.__name__, Logging.DEBUG)

        self._clean = self._prepare_url(url)

        url, name, folder = self._clean

        self.url = url
        self.name = name
        self.folder = folder

        self._log.debug(f'{self.__str__()}')

    def _prepare_url(self, raw_url: str) -> tuple:

        if not isinstance(raw_url, str) and not raw_url:
            return False

        regex = [
            ('all', f'(.*),(.*),(.*)'),
            ('no folder', f'(.*),(.*)'),
            ('url only', f'(.*)')
        ]

        for s, r in regex:
            result = re.search(r, raw_url)

            if result:
                if s == 'all':
                    url, name, folder = result.groups()

                if s == 'no folder':
                    url, name = result.groups()
                    folder = ''

                if s == 'url only':
                    url = result.groups()[0]
                    name = ''
                    folder = ''

                break

        url = Sanitation.strip(url)
        name = Sanitation.safe_filename(name)
        folder = Sanitation.safe_foldername(folder)

        return url, name, folder

    def __str__(self):
        if self.folder or self.name:
            return f'{self.folder}/{self.name} {self.url}'
        else:
            return f'{self.url}'

    def __eq__(self, other):
        if isinstance(other, Url):
            return self.url == self.url
        else:
            return False


class Youtube:

    def __init__(self, thread_pool=None, urls_file=None):
        """A multithreaded wrapper for youtube-dl
        """

        self._log = Logging(Youtube.__name__, Logging.DEBUG)

        # Directories
        self.path = os.path.split(os.path.realpath(__file__))[0]
        self.dir_d = os.path.join(self.path, 'files', 'downloading')
        self.dir_f = os.path.join(self.path, 'files', 'finished')
        self.dir_p = os.path.join(self.path, 'files', 'pending')
        self.dir_c = os.path.join(self.path, 'files', 'cookies')
        _dirs = [self.dir_d, self.dir_f, self.dir_p, self.dir_c]
        for directory in _dirs:
            if not os.path.exists(directory):
                os.makedirs(directory)
            if directory == self.dir_d:
                for directory in os.listdir(self.dir_d):
                    # Don't clean up previous downloads
                    # Clean out previous downloads
                    # os.remove(self.dir_d + '/' + directory)
                    pass

        self.urls_file = urls_file
        self.urls = self._url_builder() or list()
        self.cookies = self._cookie_builder(self.dir_c) or list()

        # Youtube-dl configuration
        self.yt = os.path.join('bin', 'youtube-dl')
        self.yt_name = ' --get-filename -o ' + self.dir_d + '/%(title)s.%(ext)s '
        self.yt_args = ' -o ' + self.dir_d + '/%(title)s.%(ext)s '
        self.yt_audio_args = self.yt_args + ' --extract-audio --audio-format mp3 -k '

        # Thread pool
        if thread_pool:
            self.pool = thread_pool
        else:
            if self.urls:
                self.pool = ThreadPoolExecutor(len(self.urls))
            else:
                self.pool = ThreadPoolExecutor()

        # Queue
        self.queue = Queue()

        # Run Downloader
        self.futures = list()
        for url in self.urls:
            self._log.info('queued: {}'.format(url))
            self.queue.put(url)

        urls = len(self.urls)

        if urls > 1:
            self._log.info('{} urls added to queue'.format(urls))
        else:
            self._log.info('{} url added to queue'.format(urls))

        sleep = 0
        while True:
            if self.queue.empty():
                break

            if self._cpu_usage(80):
                url = self.queue.get()
                self.futures.append(self.pool.submit(self._download, url))
                urls = urls - 1
                self._log.info('{} left'.format(urls))
                sleep = int(sleep / 2)
            else:
                sleep += int(sleep + 1 * 2)
                # self._log.debug('[_downloader] Sleeping for: {} seconds'.format(sleep))
                time.sleep(sleep)

    def _cpu_usage(self, max_cpu_percentage=80):
        """Limit max cpu usage
        """
        if psutil.cpu_percent() < max_cpu_percentage:
            self._log.debug('cpu usage: {}'.format(psutil.cpu_percent()))
            return True
        else:
            self._log.debug('cpu usage: {}'.format(psutil.cpu_percent()))
            return False

    def _url_builder(self) -> [Url]:
        """Create a clean list of urls

        You can put any text file or html file into files/pending

        The list builder will take any file inside of files/pending
        and create a list of URLs from it
        """

        return self._read_files(self.dir_p)

    def _read_files(self, directory) -> [Url]:
        """Read files from 'pending'
        """

        urls = []

        def html_file(f: str) -> [Url.url]:
            """Read HTML file
            """

            urls = []

            # Read with Beautifulsoup
            soup = BeautifulSoup(f.read(), 'html.parser')
            for a in soup.find_all('a', href=True):
                a = a['href'].strip()
                # TODO: bug - Need to append originating URL to <href> link
                if a == '' or a.startswith('#') or a.startswith('/'):
                    continue
                else:
                    urls.append(a)

            return urls

        def get_page(url: str) -> [Url.url]:
            """Download and parse the page
            """

            urls = []
            cookies = self.cookies

            def request_page(url):
                """Download the page

                Try using each cookie with every page
                """

                urls = []

                # TODO: feat - Add URL regex
                r = ''

                # TODO: feat - Make downloading multithreaded
                # Run a new thread for each cookie

                for _ in cookies:
                    jar = _
                    # TODO: feat - Add logic to only use cookie if url is in cookie['domain']
                    # If url is in cookie, use cookie
                    r = requests.get(url, cookies=jar)
                    soup = BeautifulSoup(r.text, 'html.parser')
                    for a in soup.find_all('a', href=True):
                        a = a['href'].strip()
                        url = url + a
                        # TODO: bug - Assert string is a URL
                        # if re.findall(r, _):
                        urls.append(url)

                return urls

            for page_urls in request_page(url):
                urls.extend(page_urls)

            return urls

        for item in os.listdir(directory):
            file_ = os.path.join(directory, item)

            self._log.debug(f'Parsing: {file_}')

            if os.path.isfile(file_):

                fn, fext = os.path.splitext(item)

                # ignore hidden files
                if not fn.startswith('.') and not fn.startswith('#'):

                    with open(file_, 'r') as f:
                        if 'html' in fext.lower() or 'htm' in fext.lower():  # HTML file
                            urls.extend(html_file(f))

                        else:
                            for line in f.read().splitlines():  # Regular text file
                                url = line.strip()
                                if url == '' or line.startswith('#') or line.startswith('/'):
                                    continue

                                url_ = Url(url)

                                if url_ in urls:
                                    continue

                                if 'youtube.com' in url_.url.lower():
                                    urls.append(url_)
                                elif url:
                                    urls.append(url_)
                                else:
                                    # TODO: bug - Determine whether to parse the page or not
                                    # If the page needs to be parsed for URLs, parse it
                                    # If the page doesn't need to be parsed for URLS, append it

                                    # for _ in get_page(url):
                                    #     urls.append(_)
                                    urls.append(url_)
        return urls

    def _download(self, object: Url):
        """Download the url
        """

        start = int(time.time())

        url = object.url
        name = object.name
        folder = object.folder

        # run youtube-dl
        # os.chmod(yt, 0o555)
        if name:
            TEMPLATE = f'-o {name}.%(ext)s'
            dl = self.yt + self.yt_args + TEMPLATE + url
        else:
            dl = self.yt + self.yt_args + url
        dl_audio = self.yt + self.yt_audio_args + url

        regexes = [
            # merging files into better format
            {'type': 'finished', 'regex': '(?<=Merging formats into ").*(?=")'},
            # file exists
            {'type': 'finished', 'regex': '(?<=^\[download\] ).*(?= has already been downloaded)(?= and merged)?'},
            # create new file
            {'type': 'finished', 'regex': '(?<=Merging formats into ").*(?=")'},
            # new audio file
            {'type': 'finished', 'regex': '(?<=Destination: ).*mp3'},
            # catch all files
            {'type': 'finished', 'regex': '(?<=Destination: ).*'},
        ]

        def run(command):
            """Run a Popen process
            """
            self._log.debug(f'Run {command}')
            return subprocess.Popen(command.split(), stdout=PIPE, stderr=PIPE).communicate()

        logs = LogHolder()

        finished = list()
        downloads = list()

        # Download file
        self._log.info(f'Downloading {object}')
        # logs.store(run(dl))

        # Download audio
        # Requires ffmpeg or avconv and ffprobe or avprobe
        self._log.info(f'Downloading audio {object}')
        # logs.store(run(dl_audio))

        while True:

            log = logs.pop()

            if log is not False:

                self._log.debug(f'[log ] {log}')

                # find matching downloads
                for r in regexes:

                    regex = r.get('regex')
                    r_type = r.get('type')

                    m = re.search(regex, log)
                    if m:
                        g = m.group()

                        filename = os.path.split(g)[-1]
                        filepath = os.path.join(self.dir_d, filename)

                        # don't show line unless it matches
                        self._log.debug(f'[_downloader] {log}')
                        self._log.debug(f'[regex] {regex}')
                        self._log.debug(f'[regex] {filename}')

                        if os.path.exists(filepath):
                            if r_type == 'finished':
                                self._log.info(f'finished: {filename}')
                                if filename not in finished:
                                    finished.append(filename)
                            else:
                                self._log.info(f'downloading: {filename}')
                                if filename not in downloads:
                                    downloads.append(filename)
                            break
            else:
                break

        # move all finished files
        self._finished(finished)

        self._log.info(f'Download took {int(time.time() - start)} seconds to complete {url}')

    def _url(self, raw: str) -> str:
        return

    def _name(self, raw):
        return

    def _folder(self, raw):
        return

    def _move_file(self, source, target):
        """Move file including metadata
        """
        try:
            self._log.info(f'Moving: {os.path.split(target)[-1]} ({os.stat(source).st_size} B)')

            # copy content, stat-info (mode too), timestamps...
            shutil.copy2(source, target)
            # copy owner and group
            st = os.stat(source)
            os.chown(target, st[stat.ST_UID], st[stat.ST_GID])
            os.remove(source)

            self._log.info(f'Moved: {os.path.split(target)[-1]} ({os.stat(source).st_size} B)')
            return True
        except:
            self._log.error(f'Failed to move: {os.path.split(source)[-1]}')
            return False

    def _finished(self, finished):
        """Move finished download
        """
        for file in finished:
            source = os.path.join(self.dir_d, file)
            target = os.path.join(self.dir_f, file)

            self._log.info(f'Finished {file}')
            self._move_file(source, target)

    def _cookie_builder(self, cookies):
        """Create a clean list of cookies
        """

        cookies = self._cookie_jar(cookies)

        return cookies

    def _cookie_jar(self, cookie_path):
        """Create a list of cookies
        """

        temp_c = []
        cookies = []
        # Open cookies
        # Cookies exported from Google Chrome extension 'EditThisCookie'
        for _ in os.listdir(cookie_path):
            with open(cookie_path + '/' + _, 'r') as f:
                cookie = f.read()
                temp_c.append(cookie)

        for _ in temp_c:
            # TODO: bug - self._cookie_jar() should return ready-to-use cookie objects built by requests.cookies
            cookie = json.loads(_)  # list of dicts

            # TODO: bug - requests.cookies.RequestsCookieJar() is broken
            # jar = requests.cookies.RequestsCookieJar()

            if len(cookie) > 1:
                for _ in cookie:
                    # TODO: bug - build cookie object with requests
                    pass

        return cookies


class LogHolder:
    def __init__(self):
        """Hold a bunch of logs
        """
        self.logs = list()

    def store(self, log):
        """Logs are expected as a string list
        """
        output, error = log

        output = output.decode().splitlines()
        error = error.decode().splitlines()

        self.logs.extend(output)
        self.logs.extend(error)

    def pop(self, index=0):
        """Pop a log off the top
        """
        try:
            return self.logs.pop(index)
        except:
            return False


#
# q = Queue()
#
# # relative paths
# script = os.path.realpath(__file__)
# path = os.path.split(script)[0]
# d = path + r'/files/downloading'
# f = path + r'/files/finished'
# p = path + r'/files/pending'
# c = path + r'/files/cookies'
# # bin/youtube-dl --get-filename -o files/downloading/'%(title)s.%(ext)s' --restrict-filenames
# yt = r'bin/youtube-dl'
# yt_name = ' --get-filename -o ' + d + '/%(title)s.%(ext)s '
# yt_args = ' -o ' + d + '/%(title)s.%(ext)s '
# yt_audio_args = yt_args + ' --extract-audio --audio-format mp3 -k '
#
#
# # No spaces in filename
# # yt_args = ' -o ' + d + '/%(title)s.%(ext)s ' + '--restrict-filenames '
# # yt_args = ' --get-filename -o \'' + d + '/%(title)s.%(ext)s\' ' + '--restrict-filenames '
#
#
# # This will be depreciated in the version 1.3
# def go(thread_pool):
#     """Go, go, go!
#     """
#
#     dirs = [d, f, p, c]
#
#     for _ in dirs:
#         if not os.path.exists(_):
#             os.makedirs(_)
#         if _ == d:
#             for _ in os.listdir(d):
#                 pass
#                 # Clean out previous downloads
#                 # os.remove(d + '/' + _)
#
#     return run_queue()
#
#
# # This will be depreciated in the version 1.3
# def list_builder():
#     """Create a clean list of urls
#
#     You can put any text file or html file into files/pending
#
#     The list bulider will take any file inside of files/pending
#     and create a list of URLs from it
#     """
#
#     cookies = ops.cookie_jar(c)
#     urls = ops.read_files(p)
#
#     return urls
#
#
# # This will be depreciated in the version 1.3
# def downloader(url):
#     """Download the url
#     """
#
#     # run youtube-dl
#     # os.chmod(yt, 0o555)
#     dl = yt + yt_args + url
#     dl_audio = yt + yt_audio_args + url
#     # subprocess.Popen(url.split(), stdout=PIPE, stderr=PIPE)
#
#     t_name = threading.current_thread().getName()
#
#     try:
#         # Download file
#         # TODO: bug - Unable to parse through subprocess stdout output
#         print('[*] [' + t_name + ']', 'Running command:', dl)
#         print('[*] [' + t_name + ']', 'Downloading:', url)
#         _stdout, _stderr = subprocess.Popen(dl.split(), stdout=PIPE, stderr=PIPE).communicate()
#         print('[*] [' + t_name + ']', _stdout.decode())
#         print('[*] [' + t_name + ']', _stderr.decode())
#         # [download] Destination:
#         # regex = '^(?<=\[download\] Destination: ).*$'
#
#         # Download audio
#         # TODO: Download audio format
#         # Requires ffmpeg or avconv and ffprobe or avprobe
#         print('[*] [' + t_name + ']', 'Running command:', dl_audio)
#         print('[*] [' + t_name + ']', 'Converting to mp3:', url)
#         _stdout, _stderr = subprocess.Popen(dl_audio.split(), stdout=PIPE, stderr=PIPE).communicate()
#         print('[*] [' + t_name + ']', _stdout.decode())
#         print('[*] [' + t_name + ']', _stderr.decode())
#
#     except:
#         raise
#
#
# # This will be depreciated in the version 1.3
# def run_queue(thread_pool):
#     """Start queue processing
#     """
#
#     for _ in list_builder():
#         print('[*]', 'Added to queue:', _)
#         q.put(_)
#
#     print('[*]', q.qsize(), 'items in queue')
#
#     def threader(threads=q.qsize()):
#         """Create threads
#         """
#
#         ts = []
#         for _ in range(threads):
#             t = threading.Thread(target=worker)
#             # t.setDaemon(True)
#             t.start()
#             ts.append(t)
#
#         print('[*] Threads started', len(ts))
#
#         # Stop threads
#         for _ in range(threads):
#             q.put(None)
#
#         # Wait on threads to finish
#         for _ in ts:
#             _.join()
#
#         # Move completed downloads
#         for _, __, ___ in os.walk(d):
#             for _ in ___:
#                 src = d + '/' + _
#                 dst = f + '/' + _
#                 print('[*] Finished', dst)
#                 move(src, dst)
#
#         # print('[*] >>', '[' + t_name + ']', dl)
#         # if relpath:
#         #     move(relpath, f + '/' + dl_name_name)
#         # if dl_path:
#         #     move(dl_path, f + '/' + dl_path_name)
#
#     def worker():
#         """Create workers
#         """
#
#         while True:
#             url = q.get()
#
#             if url is None:
#                 break
#
#             print('[*] Running queue:', q.qsize(), 'item(s) left')
#             thread_pool.submit(downloader, url)
#
#     return threader()
#
#
# # This will be depreciated in the version 1.3
# def main():
#     """Main
#
#     """
#     while True:
#         Youtube()
#         print('sleep for 3600')
#         time.sleep(3600)


def main():
    """Main

    """
    Youtube()


if __name__ == '__main__':
    main()
