#!/bin/sh
set -eu
# OS packages are installed explicitly by administrator; this script needs no root/network.
cd "$(dirname "$0")/.."
python3 -c 'import sys; assert sys.version_info >= (3,11), "Install Python >= 3.11"'
python3 scripts/build.py
./dist/labinst.pyz models
