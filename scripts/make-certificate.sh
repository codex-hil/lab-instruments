#!/bin/sh
set -eu
[ "$(id -u)" = 0 ] || { echo 'Run as root after install.sh.' >&2; exit 1; }
[ "$#" = 1 ] || { echo 'Usage: make-certificate.sh SERVER_IPV4' >&2; exit 1; }
python3 -c 'import ipaddress,sys; ipaddress.IPv4Address(sys.argv[1])' "$1"
[ ! -e /etc/labinst/server.key ] || { echo 'Existing key preserved; refusing overwrite.' >&2; exit 1; }
umask 077
openssl req -x509 -newkey rsa:3072 -nodes -days 365 -subj /CN=labinst \
    -addext "subjectAltName=IP:$1" -keyout /etc/labinst/server.key -out /etc/labinst/server.crt
chown root:labinst /etc/labinst/server.key /etc/labinst/server.crt
chmod 0640 /etc/labinst/server.key
chmod 0644 /etc/labinst/server.crt
printf '%s\n' 'Distribute server.crt as the client CA/pin; never distribute server.key.'
