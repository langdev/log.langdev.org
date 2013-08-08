#!/usr/bin/env python
try:
    from setuptools import setup, find_packages
except ImportError:
    from distribute_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages  # NOQA
from setuptools.command.test import test as TestCommand


class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import pytest
        errno = pytest.main(self.test_args)
        exit(errno)


setup(
    name='log.langdev.org',
    version='0.1.0',
    author='Taeho Kim',
    author_email='dittos@gmail.com',
    maintainer='Eunchong Yu',
    maintainer_email='kroisse@gmail.com',
    url='http://log.langdev.org/',
    description='',
    license='MIT License',
    keywords='irc',
    packages=find_packages(exclude=[]),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'requests',
        'flask >= 0.9',
        'Flask-Script >= 0.5',
        'pytz',
        'tornadio2',
    ],
    extras_require={
        'doc': [
            'Sphinx',
        ],
        'google_apps': [
            'Flask-OAuthlib',
        ],
    },
    tests_require=[
        'pytest',
    ],
    cmdclass={
        'test': PyTest,
    },
    dependency_links=[
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 2 :: Only',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Communications :: Chat',
        'Topic :: Communications :: Chat :: Internet Relay Chat',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Application',
    ],
)
