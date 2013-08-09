import pytest
from .. import bot
from .. import util
import datetime
import pytz


class TestDateTime(object):
    date1 = datetime.date(2012, 1, 23)
    dt1 = datetime.datetime(2013, 3, 3, 16, 06, 18, 123821)
    dt2 = datetime.datetime(2013, 2, 27, 16, 18, 37, 92341,
                            tzinfo=pytz.timezone('Asia/Seoul'))

    def test_get_date_str(self):
        assert bot.get_date_str(self.date1) == '20120123'
        assert bot.get_date_str(self.dt1) == '20130303'
        assert bot.get_date_str(self.dt2) == '20130227'

    def test_get_timestamp(self):
        assert bot.get_timestamp(self.dt1) == '2013-03-03T16:06:18'
        assert bot.get_timestamp(self.dt2) == '2013-02-27T16:18:37'


class TestIRCChannels(object):
    data1 = (
        {'name': '#langdev'},
        {'name': '#hongminhee', 'password': 'asdf'},
        '#rust',  # legacy
    )
    data2 = (
        {'name': '#hongminhee'},
        {'name': 'master'},
    )

    def test_irc_channels(self):
        assert util.irc_channels(self.data1) == [
            {'name': '#langdev', 'password': ''},
            {'name': '#hongminhee', 'password': 'asdf'},
            {'name': '#rust', 'password': ''},
        ]
        pytest.raises(ValueError, util.irc_channels, self.data2)
