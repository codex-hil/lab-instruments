#!/bin/sh
set -eu
# Build a COMMITTED revision in a clean temporary directory; no network/pip needed.
cd "$(dirname "$0")/.."
revision=${1:-HEAD}
replay_dir=$(mktemp -d)
trap 'rm -rf "$replay_dir"' EXIT HUP INT TERM
git archive "$revision" > "$replay_dir/source.tar"
tar -xf "$replay_dir/source.tar" -C "$replay_dir"
python3 "$replay_dir/scripts/build.py"
cat "$replay_dir/dist/SHA256SUMS"
