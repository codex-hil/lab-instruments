"""Explicit write/query transactions; no automatic retries of instrument commands."""
import array
import base64
import fcntl
import json
import os
from pathlib import Path
import socket
import ssl
import time
import urllib.request

MAX_MESSAGE = 16 * 1024 * 1024


def usb_devices():
    result = []
    for node in sorted(Path('/sys/class/usbmisc').glob('usbtmc*')):
        interface = (node / 'device').resolve()
        parent = interface
        while parent != parent.parent and not (parent / 'idVendor').exists():
            parent = parent.parent
        def read(name):
            try:
                return (parent / name).read_text().strip()
            except OSError:
                return ''
        result.append(dict(path='/dev/' + node.name, topology=parent.name,
                           serial=read('serial'), vendor=read('idVendor'),
                           product_id=read('idProduct'), model=read('product')))
    return result


def select_usb(config):
    selectors = {k: config[k] for k in ('serial', 'topology', 'vendor', 'product_id') if k in config}
    if not selectors or not any(k in selectors for k in ('serial', 'topology')):
        raise ValueError('USB requires serial or topology, never an unstable /dev/usbtmcN')
    matches = [d for d in usb_devices() if all(d[k] == v for k, v in selectors.items())]
    if len(matches) != 1:
        raise OSError(f'USB selector matches {len(matches)} devices')
    return matches[0]['path']


class Transport:
    def __init__(self, config):
        self.config = dict(config)
        self.timeout = float(config.get('timeout', 4))
        self.delay = float(config.get('delay', 0.05))
        self.maximum = int(config.get('max_message', MAX_MESSAGE))
        if not 0 < self.maximum <= MAX_MESSAGE or not 0 < self.timeout <= 30:
            raise ValueError('invalid transport bounds')
        self.handle = None
        self.buffer = b''

    def __enter__(self):
        kind = self.config['kind']
        if kind == 'tcp':
            self.handle = socket.create_connection((self.config['host'], int(self.config['port'])), self.timeout,
                                                   source_address=(self.config['source_ip'], 0) if self.config.get('source_ip') else None)
            self.handle.settimeout(self.timeout)
        elif kind == 'usb':
            self.handle = os.open(select_usb(self.config), os.O_RDWR)
            try:
                fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.ioctl(self.handle, 0x40045b0a, array.array('I', [int(self.timeout * 1000)]))
            except BaseException:
                os.close(self.handle)
                self.handle = None
                raise
        elif kind == 'gateway':
            if not self.config['url'].startswith('https://'):
                raise ValueError('gateway transport requires HTTPS')
        else:
            raise ValueError('unknown transport kind')
        return self

    def __exit__(self, *args):
        if self.handle is not None:
            if self.config['kind'] == 'usb':
                os.close(self.handle)
            else:
                self.handle.close()
        self.handle = None

    def transaction(self, data, expect_reply=True):
        if not data or len(data) > self.maximum:
            raise ValueError('invalid message length')
        kind = self.config['kind']
        if kind == 'gateway':
            body = dict(slot=self.config['slot'], data=base64.b64encode(data).decode(), reply=expect_reply)
            token = Path(self.config['token_file']).read_text().strip()
            req = urllib.request.Request(self.config['url'].rstrip('/') + '/v1/transaction',
                    json.dumps(body).encode(), {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
            context = ssl.create_default_context(cafile=self.config.get('ca_file'))
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context))
            with opener.open(req, timeout=self.timeout + 2) as response:
                result = json.load(response)
            return base64.b64decode(result['data'], validate=True)
        if kind == 'usb':
            if os.write(self.handle, data) != len(data):
                raise OSError('short USB write; command outcome unknown')
        else:
            self.handle.sendall(data)
        time.sleep(self.delay)
        if not expect_reply:
            return b''
        if kind == 'usb':
            # MSG_IN_ATTR bit 0 is EOM. Short reads alone are NOT message boundaries.
            result = bytearray()
            while len(result) < self.maximum:
                chunk = os.read(self.handle, min(65536, self.maximum - len(result)))
                if not chunk:
                    raise OSError('USB empty response')
                result.extend(chunk)
                attr = array.array('B', [0])
                fcntl.ioctl(self.handle, 0x80015b18, attr, True)
                if attr[0] & 1:
                    return bytes(result)
            raise ValueError('USB response exceeds cap; reconnect/recovery required')
        return self._tcp_message()

    def _tcp_message(self):
        end = self.config.get('read_termination', '\n').encode('ascii')
        if not end:
            raise ValueError('empty TCP terminator')
        deadline = time.monotonic() + self.timeout
        def fill(n):
            while len(self.buffer) < n:
                if n > self.maximum or len(self.buffer) >= self.maximum:
                    raise ValueError('response exceeds cap')
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('response deadline')
                self.handle.settimeout(remaining)
                part = self.handle.recv(min(65536, self.maximum - len(self.buffer)))
                if not part:
                    raise OSError('TCP EOF before complete response')
                self.buffer += part
        fill(1)
        # Some Tektronix port-4000 firmware sends LF followed by CR. The CR belongs
        # between messages, never inside a length-delimited binary payload.
        padding = self.config.get('read_padding', '').encode('ascii')
        while self.buffer[:1] in padding:
            self.buffer = self.buffer[1:]
            fill(1)
        # Definite IEEE 488.2 block, optionally preceded by an ASCII header (Tek HEADER ON).
        # Drivers explicitly disable headers for binary reads. #0 requires device-specific framing.
        if self.buffer.startswith(b'#'):
            fill(2)
            if self.buffer[1:2] not in b'123456789':
                raise ValueError('indefinite or malformed binary block not supported over raw TCP')
            digits = int(self.buffer[1:2]); fill(2 + digits)
            length = int(self.buffer[2:2+digits]); total = 2 + digits + length
            fill(total + len(end))
            if self.buffer[total:total+len(end)] != end:
                raise ValueError('binary block missing configured terminator')
            total += len(end)
        else:
            while end not in self.buffer:
                fill(len(self.buffer) + 1)
            total = self.buffer.index(end) + len(end)
        result, self.buffer = self.buffer[:total], self.buffer[total:]
        return result

    def write(self, command):
        self.transaction(command.encode('ascii') + self.config.get('write_termination', '\n').encode(), False)

    def query(self, command):
        return self.transaction(command.encode('ascii') + self.config.get('write_termination', '\n').encode()).decode('ascii').strip()
