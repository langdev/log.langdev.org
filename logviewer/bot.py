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
from flask import current_app


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
def pong(bot, m):
    bot.send_line('PONG :' + m.group(1))


@action(r'^:(.+?) 001')
def join_channel(bot, m):
    logger = _log.getChild('join_channel')
    for channel in current_app.config['IRC_CHANNELS']:
        bot.send_line('JOIN ' + channel)
        logger.info('Joining channel: %s', channel)


@action(r'^\:(.+)\!(.+) PRIVMSG \#(.+) :(.+)')
def update(bot, m):
    ChatConnection.emit_all('update')
    check_link(bot, m)


def check_link(stream, m):
    nick = m.group(1)
    message = m.group(4)
    url_m = URL_REG.match(message)
    if url_m:
        url = url_m.group(0)
        ts = time.time()
        auth = hashlib.md5(current_app.config['LANGDEV_LINKS_API_KEY'] + str(int(ts)) +
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


class LogWriter(object):
    def __init__(self, log_dir):
        self.log_file = None
        self.logfile_path = os.path.join(log_dir, 'langdev.log')
        try:
            mtime = os.path.getmtime(self.logfile_path)
            self.today = datetime.datetime.fromtimestamp(mtime)
        except OSError:
            self.today = datetime.datetime.today()

    def rotate_log_file(self):
        if self.log_file:
            self.log_file.close()
        self.log_file = None
        os.rename(self.logfile_path,
                  self.logfile_path + '.' + get_date_str(self.today))

    def get_log_file(self, date):
        if self.today.date() != date.date():
            self.rotate_log_file()
            self.today = date
        if not self.log_file:
            self.log_file = io.open(self.logfile_path, 'a', encoding='utf-8')
        return self.log_file

    def log(self, text):
        now = datetime.datetime.now()
        msg = '[{0}] {1}'.format(get_timestamp(now), text)
        logfile = self.get_log_file(now)
        print >> logfile, msg
        logfile.flush()


class Bot(object):
    def __init__(self, logger):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        self.stream = tornado.iostream.IOStream(sock)
        self.logger = logger

    def connect(self, host, port):
        logger = _log.getChild('send_request')

        def logged_request():
            logger.info('Socket connected: %s:%s' % (host, port))
            self.send_request()
        self.stream.connect((host, port), logged_request)

    def send_request(self):
        self.send_line('USER nakji 0 * :fisher')
        self.send_line('NICK ' + current_app.config['IRC_NICKNAME'])
        self.stream.read_until(b'\r\n', self.receive_line)

    def receive_line(self, line):
        if not line:
            return
        line = line.decode('utf-8')
        self.logger.log('<<< ' + line)
        for pattern, handler in action.handlers:
            match = pattern.match(line)
            if match:
                handler(self, match)
        self.stream.read_until(b'\r\n', self.receive_line)

    def send_line(self, line):
        self.logger.log('>>> ' + line)
        self.stream.write(line.encode('utf-8') + b'\r\n')


class ChatConnection(tornadio2.SocketConnection):
    connections = set()
    bot = None

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
        channel = current_app.config['IRC_CHANNELS'][0]
        message = '<{0}> {1}'.format(nick, msg)
        message = message.replace('\r\n', ' ')
        self.bot.send_line('PRIVMSG {0} :{1}'.format(channel, message))
        self.emit('update')

    @classmethod
    def emit_all(cls, event, *args, **kwargs):
        for conn in cls.connections:
            conn.emit(event, *args, **kwargs)


def launch_bot(config):
    logger = LogWriter(config['LOG_DIR'])
    host, port = config['IRC_HOST'], config['IRC_PORT']
    bot = Bot(logger=logger)
    bot.connect(host, port)
    return bot


def launch_chatserver(bot):
    ChatConnection.bot = bot
    chat_router = tornadio2.TornadioRouter(ChatConnection)
    application = tornado.web.Application(chat_router.urls,
                                          socket_io_port=8888)
    socketio_server = tornadio2.SocketServer(application, auto_start=False)
    socketio_server.start()


if __name__ == '__main__':
    _log.setLevel(logging.INFO)
    from .app import app
    with app.app_context():
        bot = launch_bot(current_app.config)
        launch_chatserver(bot)
        tornado.ioloop.IOLoop.instance().start()
