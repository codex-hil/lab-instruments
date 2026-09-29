#!/bin/sh
# Build a RAM-only EEPROM reader from a pinned upstream source.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
dest=${1:?Usage: build-reader.sh NEW_BUILD_DIRECTORY}
revision=16cdf948a964dbc3506f42753a335db91b63a39b
if [ -e "$dest" ]; then
    echo "Build directory already exists: $dest" >&2
    exit 1
fi
git clone https://github.com/whitequark/libfx2.git "$dest"
git -C "$dest" checkout --detach "$revision"
git -C "$dest" apply "$here/eeprom-read-only.patch"
make -C "$dest/firmware/library"
make -C "$dest/firmware/boot-cypress"
