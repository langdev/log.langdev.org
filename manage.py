#!/usr/bin/env python
from flask.ext import script
from logviewer.app import app


def create_app(config=None):
    if config:
        app.config.from_pyfile(config)
    return app

manager = script.Manager(app)
manager.add_option('-c', '--config', dest='config', required=False)


if __name__ == '__main__':
    manager.run()
