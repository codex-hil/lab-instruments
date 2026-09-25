#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
[ "$(id -u)" = 0 ] || { echo 'Run as root after reviewing configuration and scripts.' >&2; exit 1; }
[ "$#" = 1 ] || { echo 'Usage: install.sh examples/protected.json' >&2; exit 1; }
python3 -c 'import sys; assert sys.version_info >= (3,11)'
[ -f dist/labinst.pyz ] || { echo 'First run scripts/bootstrap.sh as an ordinary user.' >&2; exit 1; }
(cd dist && sha256sum -c SHA256SUMS)
getent group labinst >/dev/null || groupadd --system labinst
id labinst >/dev/null 2>&1 || useradd --system --gid labinst --no-create-home --shell /usr/sbin/nologin labinst
install -d -o root -g root -m 0755 /opt/labinst
install -d -o root -g labinst -m 0750 /etc/labinst
install -o root -g root -m 0755 dist/labinst.pyz /opt/labinst/labinst.pyz
if [ ! -f /etc/labinst/config.json ]; then
    install -o root -g labinst -m 0640 "$1" /etc/labinst/config.json
fi
if [ ! -f /etc/labinst/access.token ]; then
    umask 077
    python3 -c 'import secrets; print(secrets.token_urlsafe(48))' > /etc/labinst/access.token
    chown root:labinst /etc/labinst/access.token
    chmod 0640 /etc/labinst/access.token
fi
install -o root -g root -m 0644 deploy/labinst.service /etc/systemd/system/labinst.service
systemctl daemon-reload
printf '%s\n' 'Installed, NOT started. Existing policy/token preserved.' 'Next: TLS certificate, USB allowlist, NIC/firewall review, then systemctl enable --now labinst.'
