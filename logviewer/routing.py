# -*- coding: utf-8 -*-
import datetime
from werkzeug.routing import BaseConverter, ValidationError


class DateConverter(BaseConverter):
    def to_python(self, value):
        try:
            return datetime.datetime.strptime(value, u'%Y-%m-%d').date()
        except ValueError:
            raise ValidationError()

    def to_url(self, value):
        return unicode(value)
