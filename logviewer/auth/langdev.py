# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
import requests
from flask import request, current_app, render_template

from .base import AuthBackend
from ..exc import AuthenticationError


class LangDevAuth(AuthBackend):
    def __init__(self, app_key=None, secret_key=None):
        self._app_key = app_key
        self._secret_key = secret_key

    def login(self, error=None):
        return render_template('login.html', error=error,
                               next=request.args.get('next'))

    def authenticate(self):
        auth = self.langdev_sso_call(request.form['username'],
                                     request.form['password'])
        if auth:
            return {
                'username': request.form['username'],
            }
        else:
            raise AuthenticationError()

    def langdev_sso_call(self, user_id, user_pass):
        auth_url = 'http://www.langdev.org/apps/%s/sso/%s' % (self.app_key,
                                                              user_id)
        auth_data = {'password': _hmac_pass(self.secret_key, user_pass)}
        result = requests.post(
            auth_url, data=auth_data, headers={'Accept': 'application/json'},
            allow_redirects=True,
        )

        if result.status_code == requests.codes.ok:
            return json.loads(result.content)
        else:
            return False

    @property
    def app_key(self):
        if not self._app_key:
            self._app_key = current_app.config['LANGDEV_APP_KEY']
        return self._app_key

    @property
    def secret_key(self):
        if self._secret_key is None:
            self._secret_key = current_app.config['LANGDEV_SECRET_KEY']
        return self._secret_key


def _hmac_sha1(secret_key, value):
    hash_ = hmac.new(secret_key, value, hashlib.sha1)
    return hash_.hexdigest()


def _hmac_pass(secret_key, u_pass):
    return _hmac_sha1(secret_key, hashlib.md5(u_pass).hexdigest())
