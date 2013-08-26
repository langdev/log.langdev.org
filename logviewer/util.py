# -*- coding: utf-8 -*-


def irc_channels(config):
    result = []
    for i in config:
        if isinstance(i, basestring):
            # supports legacy configs
            channel = dict(
                name=i,
                password='',
            )
        else:
            channel = dict(
                name=i['name'],
                password=i.get('password', ''),
            )
        if not channel['name'].startswith('#'):
            raise ValueError("channel name should starts with '#', not {0}"
                             .format(channel['name']))
        result.append(channel)
    return result
