#!/bin/bash
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Run as root'; exit 1; }
base=/var/log/timelab-setup
install -d -m 0755 "$base"
exec > >(tee -a "$base/setup.log") 2>&1
date -Is
apt-get update
apt-get -s --no-install-recommends install wine wine64 xvfb xauth xdotool x11-apps fonts-liberation python3-venv innoextract cabextract fonts-wine
# Abort if the package solver proposes removing existing packages.
if apt-get -s --no-install-recommends install wine wine64 xvfb xauth xdotool x11-apps fonts-liberation python3-venv innoextract cabextract fonts-wine | grep -q '^Remv '; then
 echo 'Package removal proposed; stopping'; exit 1
fi
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends wine wine64 xvfb xauth xdotool x11-apps fonts-liberation python3-venv innoextract cabextract fonts-wine
if ! getent passwd timelab >/dev/null; then
 useradd --create-home --shell /bin/bash timelab
fi
[ "$(id -u timelab)" -ne 0 ]
[ "$(id -G timelab | wc -w)" -eq 1 ] || { echo 'Review existing timelab supplementary groups'; exit 1; }
install -d -o timelab -g timelab -m 0700 /home/timelab/wr-timing /home/timelab/wr-timing/logs /home/timelab/wr-timing/results
# No Wine execution here: subsequent application setup must run as timelab.
date -Is
