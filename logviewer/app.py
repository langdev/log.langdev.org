import os
import io
import re
import time
import json
import datetime
import functools
import sqlite3
import sphinxapi
from contextlib import closing

import flask
from flask import (Flask, request, redirect, session, url_for, render_template,
                   current_app)

from logviewer.exc import AuthenticationError
from logviewer.parser import parse_log
from logviewer import routing, util


app = Flask(__name__)
app.url_map.converters['date'] = routing.DateConverter

access_log = None

def filter_recent(messages, minutes):
    n = len(messages)
    now = datetime.datetime.now()
    delta = datetime.timedelta(minutes=minutes)
    # loop from n-1 to 0
    count = 0
    for i in xrange(n - 1, -1, -1):
        if now - messages[i]['time'] <= delta:
            count += 1
        else:
            break

    limit = max(count, 50)
    if limit == n:
        return messages, False
    else:
        return messages[-limit:], True


def group_messages(messages, thres):
    it = iter(messages)
    msg = next(it)
    prev_time = msg['time']
    group = [msg]
    for msg in it:
        if (msg['time'] - prev_time).seconds > thres:
            yield group
            group = []
        group.append(msg)
        prev_time = msg['time']
    if group:
        yield group


def expand_synonyms(query):
    d = {}
    with io.open(app.config['SYNONYM_PATH'], encoding='utf-8') as fp:
        for line in fp:
            words = line.rstrip().split(' ')
            words.sort(key=len, reverse=True)
            for word in words:
                d[word] = words

    terms = query.split()
    expanded_terms = []
    for term in terms:
        if term in d:
            expanded_terms.append('(' + ')|('.join(d[term]) + ')')
        else:
            expanded_terms.append('(' + term + ')')
    return ' '.join(expanded_terms)


def sphinx_search(query, offset, count):
    client = sphinxapi.SphinxClient()
    client.SetServer('localhost', 9312)
    client.SetWeights([100, 1])
    client.SetSortMode(sphinxapi.SPH_SORT_EXTENDED, '@id DESC')
    client.SetLimits(offset, count, 100000)
    client.SetRankingMode(sphinxapi.SPH_RANK_PROXIMITY_BM25)

    client.SetMatchMode(sphinxapi.SPH_MATCH_BOOLEAN)
    result = client.Query(query, '*')
    if result:
        if 'matches' in result:
            messages = {}
            for msg in result['matches']:
                attrs = msg['attrs']
                t = time.localtime(attrs['time'])
                key = time.strftime('%Y%m%d', t)
                if key not in messages:
                    messages[key] = []
                messages[key].append({
                    'type': 'privmsg',
                    'no': attrs['no'],
                    'time': datetime.datetime(*t[:7]),
                    'nick': attrs['nick'].decode('utf-8'),
                    'text': attrs['content'].decode('utf-8'),
                    'is_bot': attrs['bot'],
                })
            sorted_messages = sorted(messages.iteritems(),
                                     key=lambda (k, v): k,
                                     reverse=True)
            # TODO: should fix indexer.py
            m = ((Log('#langdev', datetime.datetime.strptime(k, "%Y%m%d").date()), v)
                 for k, v in sorted_messages)
            return {
                'total': result['total'],
                'messages': m,
            }


class Log(object):
    def __init__(self, channel, date):
        if not channel.startswith('#'):
            raise ValueError()
        self.name = channel[1:]
        self.date = date

    @property
    def is_today(self):
        return self.date == datetime.date.today()

    @property
    def path(self):
        path = os.path.join(app.config['LOG_DIR'], self.name + '.log')
        if not self.is_today:
            return path + '.' + self.date.strftime('%Y%m%d')
        else:
            return path

    def url(self, recent=None):
        return url_for('log', channel=self.name, date=self.date, recent=recent)

    def get_messages(self, start=None):
        with io.open(self.path, encoding='utf-8', errors='replace') as fp:
            for msg in parse_log(fp, start):
                yield msg

    @staticmethod
    def today(channel):
        return Log(channel, datetime.date.today())

    @property
    def yesterday(self):
        return Log('#' + self.name, self.date - datetime.timedelta(days=1))


CANONICAL_PATTERN = re.compile(r'^[\^\|_]*([^\^\|_]*).*$')
def canonical(value):
    value = value.lower()
    m = CANONICAL_PATTERN.search(value)
    if m is not None:
        return m.group(1)
    else:
        return value


def hashed(value, limit):
    return hash(value) % limit

app.jinja_env.filters.update(canonical=canonical, hash=hashed)


def get_default_channel():
    return util.irc_channels(current_app.config['IRC_CHANNELS'])[0]


def verify_channel(channel):
    channels = util.irc_channels(current_app.config['IRC_CHANNELS'])
    if channel is None:
        return channels[0]['name']
    channel = u'#' + channel
    channel_names = (i['name'] for i in channels)
    if channel not in channel_names:
        flask.abort(404)
    return channel


def login_required(f):
    @functools.wraps(f)
    def _wrapped(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return _wrapped


@app.route('/login', methods=['GET', 'POST'])
def login():
    auth = app.config['AUTH_BACKEND']
    return auth.login(error=None)


@app.route('/login/authenticate', methods=['GET', 'POST'])
def authenticate():
    auth = app.config['AUTH_BACKEND']
    try:
        result = auth.authenticate()
    except AuthenticationError as e:
        return auth.login(error=e)
    global access_log
    session['username'] = result['username']
    now = datetime.datetime.now()
    if not access_log:
        access_log = io.open(app.config['ACCESS_LOG_PATH'], 'a',
                             encoding='utf-8')
    access_log.write(u'[%s] %s logged in\n' %
                     (now.isoformat(), session['username']))
    access_log.flush()
    return redirect(request.args.get('next', url_for('index')))


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    del session['username']
    return redirect(url_for('login'))


@app.route('/', defaults={'channel': None})
@app.route('/<channel>')
def index(channel):
    channel = verify_channel(channel)
    today = Log.today(channel)
    return redirect(today.url(recent=30))


@app.route('/random')
def random():
    import random
    ago = random.randrange(30, 600)
    rand = datetime.date.today() - datetime.timedelta(days=ago)
    return redirect(url_for('log', date=rand))


@app.route('/<date:date>', defaults={'channel': None})
@app.route('/<channel>/<date:date>')
@login_required
def log(channel, date):
    if channel is None:
        channel = get_default_channel()['name']
        return redirect(url_for('log', channel=channel, date=date))
    channel = verify_channel(channel)
    log = Log(channel, date)
    if 'from' in request.args:
        start = int(request.args['from'])
    else:
        start = None
    try:
        messages = list(log.get_messages(start=start))
    except IOError:
        flask.abort(404)
    if messages:
        last_no = max(msg['no'] for msg in messages)
    else:
        last_no = 0
    if request.is_xhr:
        return render_template('_messages.html',
                               log=log, messages=messages, last_no=last_no)
    options = {}
    if log.is_today and 'recent' in request.args:
        recent = int(request.args['recent'])
        messages, truncated = filter_recent(messages, recent)
        if truncated:
            options['recent'] = recent
    messages = group_messages(messages, app.config['GROUP_THRES'])
    return render_template('log.html',
                           today=Log.today(channel),
                           log=log,
                           messages=messages,
                           options=options,
                           last_no=last_no,
                           username=session['username'],
                           channel=channel)


@app.route('/atom', defaults={'channel': None})
@app.route('/<channel>/atom')
def atom(channel):
    # TODO: auth
    # TODO: omit last group
    if channel is None:
        return redirect(url_for('atom', channel=get_default_channel()['name']))
    channel = verify_channel(channel)
    log = Log.today(channel)
    messages = group_messages(log.get_messages(), app.config['GROUP_THRES'])
    messages = reversed(list(messages))
    return render_template('atom_feed.xml', log=log, messages=messages)


@app.route('/search')
@login_required
def search():
    query = request.args['q']
    offset = int(request.args.get('offset', '0'))
    per_page = app.config['SEARCH_RESULTS_PER_PAGE']
    query_pattern = expand_synonyms(query)
    result = sphinx_search(query_pattern, offset=offset, count=per_page)
    page = offset / per_page
    pages = [{'url': url_for('search', q=query, offset=n * per_page),
              'number': n + 1,
              'current': n == page}
             for n in xrange(result['total'] / per_page)]
    return render_template('search_result.html',
                           query=query,
                           total=result['total'],
                           result=result['messages'],
                           pages=pages,
                           query_pattern=query_pattern)


def connect_db():
    conn = sqlite3.connect(app.config['FLAG_DB'])
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/<channel>/<date:date>/flags')
@login_required
def flags(channel, date):
    channel = verify_channel(channel)
    with closing(connect_db()) as db:
        c = db.cursor()
        c.execute('select * from flags where date=? order by line', (date, ))
        return json.dumps([dict(row) for row in c])


@app.route('/<channel>/<date:date>/<line>/flags', methods=['POST'])
@login_required
def flag(channel, date, line):
    channel = verify_channel(channel)
    db = connect_db()
    c = db.cursor()
    c.execute('insert into flags (date, time, line, title, user) '
              'values(?, ?, ?, ?, ?)',
              (date, request.form['time'], int(line),
               request.form['title'], session['username']))
    db.commit()
    id = c.lastrowid
    db.close()
    return str(id)


if __name__ == '__main__':
    app.config.from_envvar('LOGVIEWER_SETTINGS')
    app.run(host='0.0.0.0', port=5000)
