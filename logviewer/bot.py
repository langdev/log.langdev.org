import eventlet
import hashlib
import re
import time

import requests

from .app import app


URL_REG = re.compile(r'(http|https):\/\/(\w+:{0,1}\w*@)?(\S+)(:[0-9]+)?'
                     r'(\/|\/([\w#!:.?+=&%@!\-\/]))?')


class action(object):
    def __init__(self, pattern):
        self.pattern = re.compile(pattern)

    def __call__(self, func):
        self.handlers.append((self.pattern, func))
        return func


@action(r'^PING :(.+)')
def pong(stream, m):
    send_line(stream, 'PONG :' + m[1])


@action(r'^:(.+?) 001')
def join_channel(stream):
    send_line(stream, 'JOIN ' + channels)


@action(r'^\:(.+)\!(.+) PRIVMSG \#(.+) :(.+)')
def update(stream, m):
    io.sockets.emit('update')
    check_link(stream, m)


def check_link(stream, m):
    nick = m[1]
    message = m[4]
    url_m = URL_REG.match(message)
    if url_m:
        url = url_m[0]
        ts = time.time()
        auth = hashlib.md5(app.config['LANGDEV_LINKS_API_KEY'] + str(int(ts)) +
                           hashlib.md5(url).hexdigest()).hexdigest()
        data = {
            'ts': ts,
            'q': url,
            'author': nick,
        }
        requests.post('http://langdevlinks.appspot.com/api/link',
                      data=data,
                      headers={'X-LINKS-AUTH': auth})


def get_date_str(date):
    return date.strftime('%Y%m%d')


def get_timestamp(dt):
    return dt.isoformat().split('.', 2)[0]
