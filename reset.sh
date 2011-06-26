#!/bin/bash
rm -rf sphinx/data sphinx/log sphinx/index
./gen_sphinx_conf.sh
indexer --config sphinx.conf --all --rotate

