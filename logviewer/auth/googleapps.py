# -*- coding: utf-8 -*-
import flask
from flask import request, url_for
from flask.ext.oauthlib.client import OAuth, OAuthException
import requests

from .base import AuthBackend
from ..exc import AuthenticationError

oauth = OAuth()


class GoogleAppsAuth(AuthBackend):
    def __init__(self, name, domain, consumer_key, consumer_secret):
        self.domain = domain
        self.remote = oauth.remote_app(
            name,
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            base_url=u'https://www.googleapis.com/',
            request_token_url=None,
            request_token_params={'scope': [
                u'https://www.googleapis.com/auth/userinfo.email',
            ]},
            access_token_url=u'https://accounts.google.com/o/oauth2/token',
            access_token_method='POST',
            authorize_url=u'https://accounts.google.com/o/oauth2/auth',
        )
        self.authenticate = self.remote.authorized_handler(self._authorize)

    def login(self, error=None):
        flask.session['_next_url'] = request.args.get('next')
        callback_url = url_for('authenticate', _external=True)
        return self.remote.authorize(callback=callback_url)

    def _authorize(self, resp):
        if resp is None:
            raise AuthenticationError(
                'Access denied: '
                'reason={0.error_reason} error={0.error_description}'
                .format(request.args))
        elif isinstance(resp, OAuthException):
            error = AuthenticationError()
            error.__cause__ = resp
            raise error
        id_token = _decode_jwt(resp['id_token'])
        username, domain = id_token['email'].rsplit('@', 1)
        if domain != self.domain:
            raise AuthenticationError("user doesn't in the proper group")
        return {'username': username}


def _decode_jwt(token):
    r = requests.post('https://www.googleapis.com/oauth2/v1/tokeninfo',
                      data={'id_token': token})
    return r.json()
