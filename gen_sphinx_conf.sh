#!/bin/sh
mkdir -p sphinx/index sphinx/log sphinx/data
LANGDEV=`pwd`
sed -e "s|LANGDEV_DIR|$LANGDEV|g" <sphinx/sphinx.conf >sphinx.conf

