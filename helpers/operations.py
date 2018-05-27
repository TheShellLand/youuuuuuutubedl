import os
from queue import Queue
import json
from bs4 import BeautifulSoup
import requests

# debugging
c = r'files/cookies'
p = r'files/pending'

cookie_q = Queue()


def read_files(p):
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
        cookies = cookie_jar(c)

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


def cookie_jar(c):
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
        # TODO: bug - cookie_jar() should return ready-to-use cookie objects built by requests.cookies
        cookie = json.loads(_)  # list of dicts

        # TODO: bug - requests.cookies.RequestsCookieJar() is broken
        # jar = requests.cookies.RequestsCookieJar()

        if len(cookie) > 1:
            for _ in cookie:
                # TODO: bug - build cookie object with requests
                pass

    return cookies


if __name__ == '__main__':
    read_files(p)
