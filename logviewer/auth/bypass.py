# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
import requests
from flask import request, current_app, render_template

from .base import AuthBackend
from ..exc import AuthenticationError


class BypassAuth(AuthBackend):
    def login(self, error=None):
        return render_template('login.html', error=error,
                               next=request.args.get('next'))

    def authenticate(self):
        username = request.form['username']
        if username:
            return {
                'username': username,
            }
        else:
            raise AuthenticationError()

