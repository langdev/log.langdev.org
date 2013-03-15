import os
import io
import re
import time
import hmac
import json
import hashlib
import datetime
import functools
import sqlite3
import sphinxapi
from contextlib import closing

import requests
import flask
from flask import Flask, request, redirect, session, url_for, render_template

app = Flask(__name__)

access_log = None

LINE_PATTERN = re.compile('^.*?\[(?P<timestamp>.+?)(?: #.*?)?\].*?'
                          ' (?P<dir><<<|>>>) (?P<data>.+)$')
PRIVMSG_PATTERN = re.compile('^(?::(?P<nick>.+?)!.+? )?PRIVMSG #.+?'
                             ' :(?P<text>.+)$')
PROXY_MSG_PATTERN = re.compile('<(?P<nick>.+?)> (?P<text>.*)')


def parse_log(fp, start=None):
    def extract_time(match):
        timestamp = match.group('timestamp').split('.')[0]
        return datetime.datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S')

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
            m = ((Log(datetime.datetime.strptime(k, "%Y%m%d").date()), v)
                 for k, v in sorted_messages)
            return {
                'total': result['total'],
                'messages': m,
            }


class Log(object):
    def __init__(self, date):
        self.date = date

    @property
    def is_today(self):
        return self.date == datetime.date.today()

    @property
    def path(self):
        path = os.path.join(app.config['LOG_DIR'], 'langdev.log')
        if not self.is_today:
            return path + '.' + self.date.strftime('%Y%m%d')
        else:
            return path

    @property
    def url(self):
        return url_for('log', date=self.date)

    def get_messages(self, start=None):
        with io.open(self.path, encoding='utf-8', errors='replace') as fp:
            for msg in parse_log(fp, start):
                yield msg

    @staticmethod
    def today():
        return Log(datetime.date.today())

    @property
    def yesterday(self):
        return Log(self.date - datetime.timedelta(days=1))


def langdev_sso_call(user_id, user_pass):
    def hmac_sha1(value):
        hash = hmac.new(app.config['LANGDEV_SECRET_KEY'], value, hashlib.sha1)
        return hash.hexdigest()

    def hmac_pass(u_pass):
        return hmac_sha1(hashlib.md5(u_pass).hexdigest())

    auth_url = 'http://www.langdev.org/apps/%s/sso/%s' % (
        app.config['LANGDEV_APP_KEY'], user_id)
    auth_data = {'password': hmac_pass(user_pass)}
    result = requests.post(
        auth_url, data=auth_data, headers={'Accept': 'application/json'},
        allow_redirects=True,
    )

    if result.status_code == requests.codes.ok:
        return json.loads(result.content)
    else:
        return False

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


def login_required(f):
    @functools.wraps(f)
    def _wrapped(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return _wrapped


@app.route('/login', methods=['GET', 'POST'])
def login():
    global access_log
    error = False

    if request.method == 'POST':
        auth = langdev_sso_call(request.form['username'],
                                request.form['password'])
        if auth:
            session['username'] = request.form['username']
            now = datetime.datetime.now()
            if not access_log:
                access_log = io.open(app.config['ACCESS_LOG_PATH'], 'a',
                                     encoding='utf-8')
            access_log.write(u'[%s] %s logged in\n' %
                             (now.isoformat(), session['username']))
            access_log.flush()
            return redirect(request.args.get('next', url_for('index')))
        else:
            error = True

    return render_template('login.html', error=error)


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    del session['username']
    return redirect(url_for('login'))


@app.route('/')
def index():
    today = Log.today()
    return redirect(url_for('log', date=today.date, recent=30))


@app.route('/random')
def random():
    import random
    ago = random.randrange(30, 600)
    rand = datetime.date.today() - datetime.timedelta(days=ago)
    return redirect(url_for('log', date=rand))


@app.route('/<date>')
@login_required
def log(date):
    date = datetime.datetime.strptime(date, '%Y-%m-%d').date()
    log = Log(date)
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
                           today=Log.today(),
                           log=log,
                           messages=messages,
                           options=options,
                           last_no=last_no,
                           username=session['username'])


@app.route('/atom')
def atom():
    # TODO: auth
    # TODO: omit last group
    log = Log.today()
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


@app.route('/<date>/flags')
@login_required
def flags(date):
    with closing(connect_db()) as db:
        c = db.cursor()
        c.execute('select * from flags where date=? order by line', (date, ))
        return json.dumps([dict(row) for row in c])


@app.route('/<date>/<line>/flags', methods=['POST'])
@login_required
def flag(date, line):
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
