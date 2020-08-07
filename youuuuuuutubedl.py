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
    download_name = str

    def __init__(self, line_file: str):

        self._log = Logging(Url.__name__, Logging.DEBUG)
        self._clean = self._prepare_url(line_file)

        url, name, folder = self._clean

        self.url = url
        self.name = name
        self.folder = folder
        self.download_name = None

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
            return f'{self.folder} {self.name} {self.url}'
        else:
            return f'{self.url}'

    def __eq__(self, other):
        if isinstance(other, Url):
            return (self.url, self.name, self.download_name, self.folder) == \
                   (other.url, self.name, self.download_name, self.folder)
        else:
            return False


class Youtube:

    def __init__(self, thread_pool=None, urls_file=None):
        """A multithreaded wrapper for youtube-dl
        """

        self._log = Logging(Youtube.__name__, Logging.INFO)

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

        self.downloads = []
        self.finished = []

        # Youtube-dl configuration
        self.yt = os.path.join('bin', 'youtube-dl')
        self.yt_name = f' --get-filename -o {self.dir_d} /%(title)s.%(ext)s'
        self.yt_args = f' -o {self.dir_d} /%(title)s.%(ext)s'
        self.yt_audio_args = f'{self.yt_args} --extract-audio --audio-format mp3 -k'

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
            self._log.info('[queue ] {}'.format(url))
            self.queue.put(url)

        urls = len(self.urls)

        if urls > 1:
            self._log.info('[queue ] {} urls added'.format(urls))
        else:
            self._log.info('[queue ] {} url added'.format(urls))

        sleep = 0
        while True:
            if self.queue.empty():
                break

            if self._cpu_usage(80):
                url = self.queue.get()
                self.futures.append(self.pool.submit(self._download, url))
                urls = urls - 1
                self._log.info('[queue] {} left'.format(urls))
                sleep = int(sleep / 2)
            else:
                sleep += int(sleep + 1 * 2)
                # self._log.debug('[_downloader] Sleeping for: {} seconds'.format(sleep))
                time.sleep(sleep)

    def _cpu_usage(self, max_cpu_percentage=80):
        """Limit max cpu usage
        """
        if psutil.cpu_percent() < max_cpu_percentage:
            self._log.debug(f'[cpu ] {psutil.cpu_percent()}%')
            return True
        else:
            self._log.debug(f'[cpu ] {psutil.cpu_percent()}%')
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

            self._log.debug(f'[reading ] {file_}')

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
            TEMPLATE = f"-o {os.path.join(self.dir_d, name)}.%(ext)s"
            dl = f'{self.yt} {TEMPLATE} {url}'
            MP3_TEMPLATE = f"-o {os.path.join(self.dir_d, name)}.mp3"
            dl_audio = f'{self.yt} {MP3_TEMPLATE} --extract-audio --audio-format mp3 -k {url}'
        else:
            dl = f'{self.yt} {self.yt_args} {url}'
            dl_audio = f'{self.yt} {self.yt_audio_args} {url}'

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
            self._log.debug(f'[run ] {command}')
            return subprocess.Popen(command.split(), stdout=PIPE, stderr=PIPE).communicate()

        logs = LogHolder()

        # Download file
        self._log.info(f'[downloading ] {object}')
        self.downloads.append(object)
        logs.store(run(dl))

        # Download audio
        # Requires ffmpeg or avconv and ffprobe or avprobe
        self._log.info(f'[downloading audio ] {object}')
        self.downloads.append(object)
        logs.store(run(dl_audio))

        while True:

            if len(self.finished) == len(self.downloads):
                break

            log = logs.pop()

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
                    self._log.debug(f'[log ] {log}')
                    self._log.debug(f'[log ] [regex] {regex}')
                    self._log.debug(f'[log ] [regex] {filename}')

                    if os.path.exists(filepath):
                        if r_type == 'finished':
                            self.finished.append(object, filename)
                            object.download_name = filename
                            self._log.info(f'[log ] finished: ({len(self.finished)}/{len(self.downloads)}) {filename}')
                        else:
                            object.download_name = filename
                            # self.downloads.append(object)
                            self._log.info(f'[log ] downloading: ({len(self.finished)}/{len(self.downloads)}) {filename}')
                        break

        self._finished(self.finished)

        self._log.info(f'[download ] took {int(time.time() - start)} seconds to complete {url}')

    def _move_file(self, source, target):
        """Move file including metadata
        """
        try:
            self._log.info(f'[moving ] {os.path.split(target)[-1]} ({os.stat(source).st_size} B)')

            # copy content, stat-info (mode too), timestamps...
            shutil.copy2(source, target)
            # copy owner and group
            st = os.stat(source)
            os.chown(target, st[stat.ST_UID], st[stat.ST_GID])
            os.remove(source)

            self._log.info(f'[moved ] {os.path.split(os.path.split(target)[0])[-1]}/{os.path.split(target)[-1]} ({os.stat(target).st_size} B)')
            return True
        except:
            self._log.error(f'[moving ] failed {os.path.split(source)[-1]}')
            return False

    def _finished(self, finished: [(Url, str)]):
        """Move finished download
        """

        for f, filename in finished:

            source = os.path.join(self.dir_d, filename)

            if f.folder:
                if not os.path.exists(os.path.join(self.dir_f, f.folder)):
                    os.mkdir(os.path.join(self.dir_f, f.folder))
                destination = os.path.join(self.dir_f, f.folder, filename)
            else:
                destination = os.path.join(self.dir_f, filename)

            self._log.info(f'[finished ] {f}')
            self._move_file(source, destination)

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


def main():
    """Main

    """
    Youtube()


if __name__ == '__main__':
    main()
