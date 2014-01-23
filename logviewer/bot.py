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

from . import util, parser


_log = logging.getLogger(__name__)


URL_REG = re.compile(r'(http|https):\/\/(\w+:{0,1}\w*@)?(\S+)(:[0-9]+)?'
                     r'(\/|\/([\w#!:.?+=&%@!\-\/]))?')


def action(pattern):
    if not hasattr(pattern, 'match'):
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
    for i in util.irc_channels(current_app.config['IRC_CHANNELS']):
        bot.send_line('JOIN {0[name]} {0[password]}'.format(i))
        logger.info('Joining channel: %s', i['name'])


@action(parser.PRIVMSG_PATTERN)
def update(bot, m):
    ChatConnection.emit_all('update')
    check_link(bot, m)


def check_link(stream, m):
    api_key = current_app.config.get('LANGDEV_LINKS_API_KEY')
    if not api_key:
        return
    nick = m.group('nick')
    message = m.group('text')
    url_m = URL_REG.match(message)
    if url_m:
        url = url_m.group(0)
        ts = time.time()
        auth = hashlib.md5()
        auth.update(api_key)
        auth.update(str(int(ts)))
        auth.update(hashlib.md5(url).hexdigest())
        auth = auth.hexdigest()
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
    def __init__(self, log_dir, name):
        if name.startswith('#'):
            name = name[1:] + '.log'
        else:
            name += '.global-log'
        self.log_file = None
        self.logfile_path = os.path.join(log_dir, name)
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
        msg = '[{0}] {1}\n'.format(get_timestamp(now), text)
        logfile = self.get_log_file(now)
        logfile.write(msg)
        logfile.flush()


class LogWriterFactory(object):
    def __init__(self, log_dir):
        self.log_dir = log_dir
        self.loggers = {}

    def get(self, name):
        if name not in self.loggers:
            self.loggers[name] = LogWriter(self.log_dir, name)
        return self.loggers[name]


class Bot(object):
    def __init__(self, logger_factory, use_ssl=False):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        if use_ssl:
            self.stream = tornado.iostream.SSLIOStream(sock)
        else:
            self.stream = tornado.iostream.IOStream(sock)
        self.logger_factory = logger_factory

    def log(self, channel, text):
        self.logger_factory.get(channel).log(text)

    def connect(self, host, port):
        logger = _log.getChild('send_request')

        def logged_request():
            logger.info('Socket connected: %s:%s' % (host, port))
            self.send_request()
        self.stream.connect((host, port), logged_request)

    def send_request(self):
        self.send_line('USER nakji 0 * :fisher')
        password = current_app.config['IRC_PASSWORD']
        if password:
            self.send_line('PASS ' + password)
        self.send_line('NICK ' + current_app.config['IRC_NICKNAME'])
        self.stream.read_until(b'\r\n', self.receive_line)

    def receive_line(self, line):
        if not line:
            return
        line = line.decode('utf-8', 'replace').rstrip('\r\n')
        channel = parser.determine_channel(line)
        self.log(channel, '<<< ' + line)
        for pattern, handler in action.handlers:
            match = pattern.match(line)
            if match:
                handler(self, match)
        self.stream.read_until(b'\r\n', self.receive_line)

    def send_line(self, line):
        channel = parser.determine_channel(line)
        self.log(channel, '>>> ' + line)
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
    def msg(self, nick, channel, msg):
        logger = _log.getChild(self.__class__.__name__ + '.msg')
        channels = util.irc_channels(current_app.config['IRC_CHANNELS'])
        if channel not in (i['name'] for i in channels):
            logger.warning('%s not in the channel list', channel)
            return
        message = '<{0}> {1}'.format(nick, msg)
        message = message.replace('\r\n', ' ')
        self.bot.send_line('PRIVMSG {0} :{1}'.format(channel, message))
        self.emit('update')

    @classmethod
    def emit_all(cls, event, *args, **kwargs):
        for conn in cls.connections:
            conn.emit(event, *args, **kwargs)


def launch_bot(config):
    logger_factory = LogWriterFactory(config['LOG_DIR'])
    host, port = config['IRC_HOST'], config['IRC_PORT']
    bot = Bot(logger_factory=logger_factory,
              use_ssl=config.get('IRC_USE_SSL', False))
    bot.connect(host, port)
    return bot


def launch_chatserver(bot, port=8888):
    ChatConnection.bot = bot
    chat_router = tornadio2.TornadioRouter(ChatConnection)
    application = tornado.web.Application(chat_router.urls,
                                          socket_io_port=port)
    return tornadio2.SocketServer(application, auto_start=False)


if __name__ == '__main__':
    _log.setLevel(logging.INFO)
    from .app import app
    with app.app_context():
        bot = launch_bot(current_app.config)
        launch_chatserver(bot).start()
        tornado.ioloop.IOLoop.instance().start()
