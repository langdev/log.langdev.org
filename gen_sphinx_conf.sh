#!/bin/sh
LANGDEV=`pwd`
sed -e "s|LANGDEV_DIR|$LANGDEV|g" <sphinx/sphinx.conf >sphinx.conf

