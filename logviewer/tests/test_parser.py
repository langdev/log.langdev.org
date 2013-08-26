# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import pytest
from logviewer import parser


@pytest.mark.parametrize(('message', 'channel'), [
    (r':죽은낚지!nakji@1.234.56.78 JOIN :#langdev', '#langdev'),
    (r':Kroisse!Kroisse@20.42.244.42 JOIN :#rust', '#rust'),
    (r':Kroisse!Kroisse@43.42.41.40 PART #langdev :"Good Bye :)"', '#langdev'),

    (r':Kroisse!Kroisse@12.34.56.78 PRIVMSG #rust :재도전', '#rust'),
    (r'PRIVMSG #hongminhee :<kroisse> asdf', '#hongminhee'),

    (r'PING :ocarina.irc.ozinger.org', 'master'),
    (r'PONG :ocarina.irc.ozinger.org', 'master'),

    (r':냐옹이!meowbot@*ugl.us3.p885ek.IP MODE #hongminhee +ov Kroisse Kroisse', '#hongminhee'),

    (r':ocarina.irc.ozinger.org 376 죽은낚지 :End of message of the day.', 'master'),

    (r':ocarina.irc.ozinger.org 332 죽은낚지 #asdf :Something unusable', '#asdf'),
    (r':ocarina.irc.ozinger.org 353 죽은낚지 @ #asdf :PerhapsSPY @ㅇㅈㅇ Kroisse 죽은낚지', '#asdf'),
    (r':ocarina.irc.ozinger.org 366 죽은낚지 #asdf :End of /NAMES list.', '#asdf'),
])
def test_determine_channel(message, channel):
    assert parser.determine_channel(message) == channel
