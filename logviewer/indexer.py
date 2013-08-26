import time
import io
import glob
import os.path
from xml.sax.saxutils import escape
from flask import current_app

from logviewer.parser import parse_log
from logviewer import util


def unique_id(channel_id, dt, lineno):
    return '%d%s%08d' % (channel_id, dt.strftime('%Y%m%d'), lineno)


def messages(channel_id, channel, filename):
    with io.open(filename, encoding='utf-8', errors='replace') as fp:
        for msg in parse_log(fp):
            if msg['type'] == 'privmsg':
                print_xml(channel_id, channel, msg)


def print_xml(channel_id, channel, msg):
    id_ = unique_id(channel_id, msg['time'], msg['no'])
    content = escape(msg['text'])
    nick = msg['nick']
    date = msg['time'].strftime('%Y%m%d')
    timestamp = int(time.mktime(msg['time'].timetuple()))
    lineno = msg['no']
    bot = msg['is_bot']

    print '<sphinx:document id="%s">' % id_
    print '<content>%s</content>' % content
    print '<channel>%s</channel>' % channel
    print '<no>%s</no>' % lineno
    print '<nick>%s</nick>' % nick
    print '<date>%s</date>' % date
    print '<time>%s</time>' % timestamp
    print '<bot>%d</bot>' % int(bot)  # 1 or 0
    print '</sphinx:document>'


def main():
    print '''<?xml version="1.0" encoding="utf-8"?>
<sphinx:docset>
<sphinx:schema>
    <sphinx:field name="content" attr="string"/>
    <sphinx:attr name="channel" type="string"/>
    <sphinx:attr name="no" type="int" bits="32"/>
    <sphinx:attr name="nick" type="string"/>
    <sphinx:attr name="date" type="int" bits="32"/>
    <sphinx:attr name="time" type="timestamp"/>
    <sphinx:attr name="bot" type="bool"/>
</sphinx:schema>'''
    log_dir = current_app.config['LOG_DIR']
    channels = util.irc_channels(current_app.config['IRC_CHANNELS'])
    channel_names = [i['name'] for i in channels]
    for i, channel in enumerate(channel_names):
        if not channel.startswith('#'):
            continue
        pattern = os.path.join(log_dir, channel[1:] + '.log.*')
        for filename in glob.glob(pattern):
            messages(i + 1, channel, filename)
    print '</sphinx:docset>'
