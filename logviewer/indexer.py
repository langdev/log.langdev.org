import time
import io
import glob
import os.path
from xml.sax.saxutils import escape

from logviewer.app import app
from logviewer.parser import parse_log


def unique_id(dt, lineno):
    return '%s%08d' % (dt.strftime('%Y%m%d'), lineno)


def messages(filename):
    with io.open(filename, encoding='utf-8', errors='replace') as fp:
        for msg in parse_log(fp):
            if msg['type'] == 'privmsg':
                print_xml(msg)


def print_xml(msg):
    id_ = unique_id(msg['time'], msg['no'])
    content = escape(msg['text'])
    nick = msg['nick']
    timestamp = int(time.mktime(msg['time'].timetuple()))
    lineno = msg['no']
    bot = msg['is_bot']

    print '<sphinx:document id="%s">' % id_
    print '<content>%s</content>' % content
    print '<no>%s</no>' % lineno
    print '<nick>%s</nick>' % nick
    print '<time>%s</time>' % timestamp
    print '<bot>%d</bot>' % int(bot)  # 1 or 0
    print '</sphinx:document>'


def main():
    print '''<?xml version="1.0" encoding="utf-8"?>
<sphinx:docset>
<sphinx:schema>
    <sphinx:field name="content" attr="string"/>
    <sphinx:attr name="no" type="int" bits="32"/>
    <sphinx:attr name="nick" type="string"/>
    <sphinx:attr name="time" type="timestamp"/>
    <sphinx:attr name="bot" type="bool"/>
</sphinx:schema>'''
    log_dir = app.config['LOG_DIR']
    pattern = os.path.join(log_dir, 'langdev.log.*')
    for filename in glob.glob(pattern):
        messages(filename)
    print '</sphinx:docset>'
