#!/usr/bin/env python3
# 
# Author: naisanza@gmai.com
# Version: 1.1.0


import asyncio
import json
import os
import requests
import subprocess
import threading
from bs4 import BeautifulSoup
from queue import Queue
from shutil import move
from subprocess import PIPE
from sys import stdout

# This will be depreciated in the next major version
import helpers.operations as ops

# import v1.helpers.threading

import logging
logging.basicConfig(filename=None, level=logging.DEBUG)


q = Queue()

d = r'files/downloading'
f = r'files/finished'
p = r'files/pending'
c = r'files/cookies'
# bin/youtube-dl --get-filename -o files/downloading/'%(title)s.%(ext)s' --restrict-filenames
yt = r'bin/youtube-dl'
yt_name = ' --get-filename -o ' + d + '/%(title)s.%(ext)s '
yt_args = ' -o ' + d + '/%(title)s.%(ext)s '
yt_audio_args = yt_args + ' --extract-audio --audio-format mp3 -k '


# No spaces in filename
# yt_args = ' -o ' + d + '/%(title)s.%(ext)s ' + '--restrict-filenames '
# yt_args = ' --get-filename -o \'' + d + '/%(title)s.%(ext)s\' ' + '--restrict-filenames '


class AsyncYoutube:

    def __init__(self, urls_file=None):
        """A fully asynchronous wrapper for youtube-dl
        
        :param urls_file: Optional file path to a list to use
        """

        self.urls = self._list_builder()
        self.cookies = self._cookie_builder() or []
        self.filename = str()
        self.size = int()
        self.extractAudio = False
        self.queue = asyncio.Queue()
        self.threads = []
        self.urls_file = urls_file

        # Directories
        self.d = r'files/downloading'
        self.f = r'files/finished'
        self.p = r'files/pending'
        self.c = r'files/cookies'
        dirs = [self.d, self.f, self.p, self.c]
        for directory in dirs:
            if not os.path.exists(directory):
                os.makedirs(directory)
            if directory == self.d:
                for directory in os.listdir(self.d):
                    pass
                    # Don't clean up previous downloads
                    # Clean out previous downloads
                    # os.remove(self.d + '/' + directory)

        # Youtube-dl configuration
        self.yt = r'bin/youtube-dl'
        self.yt_name = ' --get-filename -o ' + self.d + '/%(title)s.%(ext)s '
        self.yt_args = ' -o ' + self.d + '/%(title)s.%(ext)s '
        self.yt_audio_args = yt_args + ' --extract-audio --audio-format mp3 -k '

    def _list_builder(self):
        """Create a clean list of urls

        You can put any text file or html file into files/pending

        The list bulider will take any file inside of files/pending
        and create a list of URLs from it
        """

        cookies = self._cookie_jar(c)
        urls = self._read_files(p)

        return urls

    def _read_files(self):
        """Read files from 'pending'
        """

        urls = []

        def html_file(f):
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

        def get_page(url):
            """Download and parse the page
            """

            urls = []
            cookies = self._cookie_jar(c)

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

            for _ in request_page(url):
                urls.append(_)

            return urls

        for _ in os.listdir(p):
            _file = p + '/' + _

            if os.path.isfile(_file):

                fn, fext = os.path.splitext(_)

                if not fn.startswith('.'):

                    with open(_file, 'r') as f:
                        if 'html' in fext.lower() or 'htm' in fext.lower():  # HTML file
                            for _ in html_file(f):
                                urls.append(_)

                        else:
                            for _ in f.read().splitlines():  # Regular text file
                                url = _.strip()
                                if url == '' or _.startswith('#') or _.startswith('/'):
                                    continue

                                if 'youtube.com' in url.lower():
                                    urls.append(url)
                                else:
                                    # TODO: bug - Determine whether to parse the page or not
                                    # If the page needs to be parsed for URLs, parse it
                                    # If the page doesn't need to be parsed for URLS, append it

                                    # for _ in get_page(url):
                                    #     urls.append(_)
                                    urls.append(_)
        return urls

    def _cookie_builder(self):
        """Create a clean list of cookies
        """

        cookies = self._cookie_jar(c)

        return cookies

    def _downloader(self, url):
        """Download the url
        """

        # run youtube-dl
        #os.chmod(yt, 0o555)
        dl = yt + yt_args + url
        dl_audio = yt + yt_audio_args + url
        # subprocess.Popen(url.split(), stdout=PIPE, stderr=PIPE)

        t_name = threading.current_thread().getName()

        try:
            # Download file
            # TODO: bug - Unable to parse through subprocess stdout output
            print('[*] [' + t_name + ']', dl)
            subprocess.Popen(dl.split(), stdout=stdout, stderr=PIPE).communicate()
            # [download] Destination:
            # regex = '^(?<=\[download\] Destination: ).*$'

            # Download audio
            # TODO: Download audio format
            # Requirse ffmpeg or avconv and ffprobe or avprobe
            print('[*] [' + t_name + ']', dl_audio)
            subprocess.Popen(dl_audio.split(), stdout=stdout, stderr=PIPE).communicate()

        except:
            raise

        return

    def _cookie_jar(self, c):
        """Create a list of cookies
        """

        temp_c = []
        cookies = []
        # Open cookies
        # Cookies exported from Google Chrome extension 'EditThisCookie'
        for _ in os.listdir(c):
            with open(c + '/' + _, 'r') as f:
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


def go():
    """Go, go, go!
    """

    dirs = [d, f, p, c]

    for _ in dirs:
        if not os.path.exists(_):
            os.makedirs(_)
        if _ == d:
            for _ in os.listdir(d):
                pass
                # Clean out previous downloads
                # os.remove(d + '/' + _)

    def run_queue():
        """Start queue processing
        """

        for _ in list_builder():
            print('[*]', 'adding', _, 'to queue')
            q.put(_)

        print('[*]', q.qsize(), 'items in queue')

        def threader(threads=q.qsize()):
            """Create threads
            """

            ts = []
            for _ in range(threads):
                t = threading.Thread(target=worker)
                # t.setDaemon(True)
                t.start()
                ts.append(t)

            print('[*] Threads started', len(ts))

            # Stop threads
            for _ in range(threads):
                q.put(None)

            # Wait on threads to finish
            for _ in ts:
                _.join()

            # Move completed downloads
            for _, __, ___ in os.walk(d):
                for _ in ___:
                    src = d + '/' + _
                    dst = f + '/' + _
                    print('[*] Finished', dst)
                    move(src, dst)

            # print('[*] >>', '[' + t_name + ']', dl)
            # if relpath:
            #     move(relpath, f + '/' + dl_name_name)
            # if dl_path:
            #     move(dl_path, f + '/' + dl_path_name)

            return

        def worker():
            """Create workers
            """

            while True:
                url = q.get()

                if url is None:
                    break

                print('[*] >> [queue]', q.qsize(), 'items left')
                downloader(url)
            return

        def downloader(url):
            """Download the url
            """

            # run youtube-dl
            #os.chmod(yt, 0o555)
            dl = yt + yt_args + url
            dl_audio = yt + yt_audio_args + url
            # subprocess.Popen(url.split(), stdout=PIPE, stderr=PIPE)

            t_name = threading.current_thread().getName()

            try:
                # Download file
                # TODO: bug - Unable to parse through subprocess stdout output
                print('[*] [' + t_name + ']', dl)
                subprocess.Popen(dl.split(), stdout=stdout, stderr=PIPE).communicate()
                # [download] Destination:
                # regex = '^(?<=\[download\] Destination: ).*$'

                # Download audio
                # TODO: Download audio format
                # Requirse ffmpeg or avconv and ffprobe or avprobe
                print('[*] [' + t_name + ']', dl_audio)
                subprocess.Popen(dl_audio.split(), stdout=stdout, stderr=PIPE).communicate()

            except:
                raise

        return threader()

    return run_queue()


def list_builder():
    """Create a clean list of urls

    You can put any text file or html file into files/pending

    The list bulider will take any file inside of files/pending
    and create a list of URLs from it
    """

    cookies = ops.cookie_jar(c)
    urls = ops.read_files(p)

    return urls


def main():
    """Main
    """

    # go()
    AsyncYoutube()


if __name__ == '__main__':
    main()
