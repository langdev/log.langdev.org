#!/usr/bin/env python
from flask.ext import script
from flask import current_app
import tornado

from logviewer.app import app


def create_app(config=None):
    if config:
        app.config.from_pyfile(config)
    else:
        app.config.from_envvar('LOGVIEWER_SETTINGS')
    return app


manager = script.Manager(create_app)
manager.add_option('-c', '--config', dest='config', required=False)


@manager.command
def runbot():
    port = current_app.config.get('LOGBOT_LISTEN', 8888)
    import logviewer.bot
    bot = logviewer.bot.launch_bot(current_app.config)
    logviewer.bot.launch_chatserver(bot, port).start()
    tornado.ioloop.IOLoop.instance().start()


@manager.command
def indexer():
    import logviewer.indexer
    logviewer.indexer.main()


if __name__ == '__main__':
    manager.run()
