from __future__ import unicode_literals

import logging
import hashlib
import re
import time
import io
import os.path
import datetime
import socket

import requests
import tornado.ioloop
import tornado.iostream
import tornadio2

from .app import app


_log = logging.getLogger(__name__)


URL_REG = re.compile(r'(http|https):\/\/(\w+:{0,1}\w*@)?(\S+)(:[0-9]+)?'
                     r'(\/|\/([\w#!:.?+=&%@!\-\/]))?')


def action(pattern):
    pattern = re.compile(pattern)

    def decorate(func):
        action.handlers.append((pattern, func))
        return func
    return decorate
action.handlers = []


@action(r'^PING :(.+)')
def pong(stream, m):
    send_line(stream, 'PONG :' + m.group(1))


@action(r'^:(.+?) 001')
def join_channel(stream, m):
    logger = _log.getChild('join_channel')
    for channel in app.config['IRC_CHANNELS']:
        send_line(stream, 'JOIN ' + channel)
        logger.info('Joining channel: %s', channel)


@action(r'^\:(.+)\!(.+) PRIVMSG \#(.+) :(.+)')
def update(stream, m):
    ChatConnection.emit_all('update')
    check_link(stream, m)


def check_link(stream, m):
    nick = m.group(1)
    message = m.group(4)
    url_m = URL_REG.match(message)
    if url_m:
        url = url_m.group(0)
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


log_file = None
logfile_path = os.path.join(app.config['LOG_DIR'], 'langdev.log')
try:
    today = datetime.datetime.fromtimestamp(os.path.getmtime(logfile_path))
except OSError:
    today = datetime.datetime.today()


def rotate_log_file():
    global log_file
    if log_file:
        log_file.close()
    log_file = None
    os.rename(logfile_path, logfile_path + '.' + get_date_str(today))


def get_log_file(date):
    global today, log_file
    if today.date() != date.date():
        rotate_log_file()
        today = date
    if not log_file:
        log_file = io.open(logfile_path, 'a', encoding='utf-8')
    return log_file


def log(text):
    now = datetime.datetime.now()
    msg = '[{0}] {1}'.format(get_timestamp(now), text)
    logfile = get_log_file(now)
    print >> logfile, msg
    logfile.flush()


def send_line(stream, line):
    log('>>> ' + line)
    stream.write(line.encode('utf-8') + b'\r\n')


def receive_line(line):
    global stream
    if not line:
        return
    line = line.decode('utf-8')
    log('<<< ' + line)
    for pattern, handler in action.handlers:
        match = pattern.match(line)
        if match:
            handler(stream, match)
    stream.read_until(b'\r\n', receive_line)


def send_request():
    global stream
    logger = _log.getChild('send_request')
    logger.info('Socket connected: %s:%s' % (host, port))
    send_line(stream, 'USER bot 0 * :fishing')
    send_line(stream, 'NICK ' + app.config['IRC_NICKNAME'])
    stream.read_until(b'\r\n', receive_line)


class ChatConnection(tornadio2.SocketConnection):
    connections = set()

    def on_open(self, request):
        logger = _log.getChild(self.__class__.__name__ + '.on_open')
        self.connections.add(self)
        logger.debug('Current connections: %s', self.connections)

    def on_close(self):
        logger = _log.getChild(self.__class__.__name__ + '.on_close')
        self.connections.remove(self)
        logger.debug('Current connections: %s', self.connections)

    @tornadio2.conn.event
    def msg(self, nick, msg):
        channel = app.config['IRC_CHANNELS'][0]
        message = '<{0}> {1}'.format(nick, msg)
        message = message.replace('\r\n', ' ')
        send_line(stream, 'PRIVMSG {0} :{1}'.format(channel, message))
        self.emit('update')

    @classmethod
    def emit_all(cls, event, *args, **kwargs):
        for conn in cls.connections:
            conn.emit(event, *args, **kwargs)


if __name__ == '__main__':
    _log.setLevel(logging.INFO)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    stream = tornado.iostream.IOStream(sock)
    host, port = app.config['IRC_HOST'], app.config['IRC_PORT']
    stream.connect((host, port), send_request)

    chat_router = tornadio2.TornadioRouter(ChatConnection)
    application = tornado.web.Application(chat_router.urls,
                                          socket_io_port=8888)
    socketio_server = tornadio2.SocketServer(application, auto_start=False)
    socketio_server.start()
    tornado.ioloop.IOLoop.instance().start()
