import re
import email.utils
import time
from datetime import datetime

LINE_PATTERN = re.compile('^.*?\[(?P<timestamp>.+?)(?: #.*?)?\].*?'
                          ' (?P<dir><<<|>>>) (?P<data>.+)$')
PRIVMSG_PATTERN = re.compile('^(?::(?P<nick>.+?)!.+? )?PRIVMSG #.+?'
                             ' :(?P<text>.+)$')
PROXY_MSG_PATTERN = re.compile('<(?P<nick>.+?)> (?P<text>.*)')

def parse_log(fp, start=None):
    def extract_time(match):
        t = match.group('timestamp')
        try:
            # ISO 8601
            timestamp = t.split('.')[0]
            return datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            # RFC 2822
            t = email.utils.parsedate(t)
            if t is not None:
            	t = time.mktime(t)
            else:
            	t = 0 # fail
            return datetime.fromtimestamp(t)

    no = 0
    for line in fp:
        m = LINE_PATTERN.match(line)
        if not m:
            continue

        if 'PRIVMSG' in m.group('data'):
            no += 1

            if start and no < start:
                continue
            pm = PRIVMSG_PATTERN.match(m.group('data'))
            if not pm:
                continue

            is_bot = not pm.group('nick')
            pmm = PROXY_MSG_PATTERN.match(pm.group('text'))
            if is_bot and pmm:
                nick = pmm.group('nick')
                text = pmm.group('text')
                is_bot = False
            else:
                nick = pm.group('nick')
                text = pm.group('text')

            yield dict(type='privmsg', no=no,
                time=extract_time(m),
                nick=nick, text=text, is_bot=is_bot)
        elif (m.group('dir') == '>>>' and start is None and
              m.group('data').startswith('JOIN #langdev')):
            yield dict(type='join', time=extract_time(m), is_bot=True, no=-1)
