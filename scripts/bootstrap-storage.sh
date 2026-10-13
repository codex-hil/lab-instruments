#!/bin/sh
set -eu
install_user=false
case "${1:-}" in
  --install) install_user=true ;;
  "") ;;
  *) printf "%s\n" "Usage: $0 [--install]" >&2; exit 2 ;;
esac
cd "$(dirname "$0")/.."
python3 -c 'import sys; assert sys.version_info >= (3,11)'
python3 -m unittest discover -s tests -p test_storage.py -v
nix --extra-experimental-features 'nix-command flakes' build \
  path:. --out-link local/storage-tools
nix --extra-experimental-features 'nix-command flakes' develop path:. --command \
  python3 -m unittest discover -s tests -p test_storage.py -v
printf '%s\n' "Run: local/storage-tools/bin/hil-storage --config examples/storage/mock.json --json list"
if "$install_user"; then
  python3 - <<'INSTALL'
from pathlib import Path
import os
root = Path.cwd()
link = Path.home() / '.local/bin/hil-storage'
target = root / 'local/storage-tools/bin/hil-storage'
link.parent.mkdir(parents=True, exist_ok=True)
if link.is_symlink() and os.readlink(link) == str(target):
    pass
elif link.exists() or link.is_symlink():
    raise SystemExit(f'Refusing to replace existing {link}')
else:
    link.symlink_to(target)
print(f'Installed launcher: {link} -> {target}')
INSTALL
fi
