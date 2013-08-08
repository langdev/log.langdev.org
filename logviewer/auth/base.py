# -*- coding: utf-8 -*-


class AuthBackend(object):
    def login(self, error=None):
        raise NotImplementedError()

    def authenticate(self):
        raise NotImplementedError()
