import os
import io
import re
import time
import json
import random
import datetime
import itertools
import functools
import sqlite3
import sphinxapi
from contextlib import closing

import flask
from flask import (Flask, request, redirect, session, url_for, render_template,
                   current_app, jsonify)

from logviewer.exc import AuthenticationError
from logviewer.parser import parse_log
from logviewer import routing, util


app = Flask(__name__)
app.url_map.converters['date'] = routing.DateConverter


@app.before_first_request
def init_jinja_env():
    current_app.jinja_env.globals.update(
        LOGBOT_PORT=current_app.config['LOGBOT_LISTEN'],
    )

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
    client.SetSortMode(sphinxapi.SPH_SORT_EXTENDED,
                       'date DESC, channel ASC, @id DESC')
    client.SetLimits(offset, count, 100000)
    client.SetRankingMode(sphinxapi.SPH_RANK_PROXIMITY_BM25)

    client.SetMatchMode(sphinxapi.SPH_MATCH_BOOLEAN)
    result = client.Query(query, '*')
    if result and 'matches' in result:
        messages = []
        for msg in result['matches']:
            attrs = msg['attrs']
            channel = attrs['channel']
            t = time.localtime(attrs['time'])
            d = str(attrs['date'])
            date = datetime.datetime.strptime(d, '%Y%m%d').date()
            key = (channel, date)
            messages.append((key, {
                'type': 'privmsg',
                'channel': channel,
                'no': attrs['no'],
                'time': datetime.datetime(*t[:7]),
                'nick': attrs['nick'].decode('utf-8'),
                'text': attrs['content'].decode('utf-8'),
                'is_bot': attrs['bot'],
            }))
        m = []
        for k, v in itertools.groupby(messages, lambda x: x[0]):
            channel, date = k
            m.append((Log(channel, date), list(i[1] for i in v)))
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

    @property
    def exists(self):
        return os.path.isfile(self.path)

    def url(self, recent=None, **kwargs):
        return url_for('log', channel=self.name, date=self.date, recent=recent, **kwargs)

    def get_messages(self, start=None):
        if not self.exists:
            return
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


@app.route('/favicon.ico')
def favicon():
    flask.abort(404)  # it's very annoying.


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
    redirect_url = request.args.get('next')
    if not redirect_url:
        redirect_url = flask.session['_next_url']
        if not redirect_url:
            redirect_url = url_for('index')
    return redirect(redirect_url)


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    del session['username']
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    channels = util.irc_channels(current_app.config['IRC_CHANNELS'])
    if len(channels) == 1:
        return redirect(url_for('channel', channel=channels[0]['name'][1:]))
    logs = []
    for i in channels:
        log = Log.today(i['name'])
        message = list(log.get_messages())[-5:]
        logs.append(dict(
            log=log,
            message=message,
        ))
    return render_template('index.html',
                           logs=logs)


@app.route('/<channel>', endpoint='channel')
def channel_(channel):
    channel = verify_channel(channel)
    today = Log.today(channel)
    return redirect(today.url(recent=30))


@app.route('/random', defaults={'channel': None}, endpoint='random')
@app.route('/<channel>/random', endpoint='random')
def random_(channel):
    if channel is None:
        channels = util.irc_channels(current_app.config['IRC_CHANNELS'])
        channel_names = [i['name'] for i in channels]
    else:
        channel = verify_channel(channel)
    for _ in range(10):
        chan = channel or random.choice(channel_names)
        ago = random.randrange(30, 600)
        rand = datetime.date.today() - datetime.timedelta(days=ago)
        log = Log(chan, rand)
        if log.exists:
            break
    else:
        return redirect(url_for('index'))
    return redirect(log.url())


@app.route('/<date:date>', defaults={'channel': None})
@app.route('/<channel>/<date:date>')
@login_required
def log(channel, date):
    if channel is None:
        channel = get_default_channel()['name'][1:]
        return redirect(url_for('log', channel=channel, date=date))
    channel = verify_channel(channel)
    channels = util.irc_channels(current_app.config['IRC_CHANNELS'])
    channel_names = [i['name'][1:] for i in channels
                                   if i['name'].startswith('#')]
    log = Log(channel, date)
    if not log.exists and not log.is_today:
        flask.abort(404)
    if 'from' in request.args:
        start = int(request.args['from'])
    else:
        start = None
    messages = list(log.get_messages(start=start))
    if messages:
        last_no = max(msg['no'] for msg in messages)
    else:
        last_no = 0
    if request.is_xhr:
    	if messages:
            html = render_template('_messages.html',
                                   log=log, messages=messages, last_no=last_no)
            return jsonify(html=html, last_no=last_no)
        else:
        	return jsonify(html=None)
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
                           channel=channel,
                           channels=channel_names)


@app.route('/atom', defaults={'channel': None})
@app.route('/<channel>/atom')
def atom(channel):
    # TODO: auth
    # TODO: omit last group
    if channel is None:
        return redirect(url_for('atom', channel=get_default_channel()['name'][1:]))
    channel = verify_channel(channel)
    log = Log.today(channel)
    if not log.exists:
        flask.abort(404)
    messages = group_messages(log.get_messages(), app.config['GROUP_THRES'])
    messages = reversed(list(messages))
    return render_template('atom_feed.xml',
        log=log,
        messages=messages,
        channel=channel,
    )


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
        c.execute('select * from flags where channel=? and date=? '
                  'order by line',
                  (channel, date))
        return json.dumps([dict(row) for row in c])


@app.route('/<channel>/<date:date>/<line>/flags', methods=['POST'])
@login_required
def flag(channel, date, line):
    channel = verify_channel(channel)
    db = connect_db()
    c = db.cursor()
    c.execute('insert into flags (channel, date, time, line, title, user) '
              'values(?, ?, ?, ?, ?, ?)',
              (channel, date, request.form['time'], int(line),
               request.form['title'], session['username']))
    db.commit()
    id = c.lastrowid
    db.close()
    return str(id)


if __name__ == '__main__':
    app.config.from_envvar('LOGVIEWER_SETTINGS')
    app.run(host='0.0.0.0', port=5000)
