"""Bounded, read-only Tektronix discovery; return the verified open connection."""
import ipaddress
import socket
import time
from concurrent.futures import ThreadPoolExecutor


def connect(config):
    selector = config['discover']
    if selector.get('model') != 'DPO4104' or not selector.get('serial'):
        raise ValueError('discovery requires DPO4104 model and exact serial')
    network = ipaddress.ip_network(selector['subnet'], strict=True)
    if network.version != 4 or network.num_addresses > 256:
        raise ValueError('discovery subnet must be IPv4 /24 or smaller')
    if int(config['port']) != 4000:
        raise ValueError('DPO4104 discovery only supports TCP 4000')
    timeout = float(selector.get('probe_timeout', 1))
    if not 0 < timeout <= 3:
        raise ValueError('probe timeout must be >0 and <=3 seconds')

    def probe(host):
        sock = None
        try:
            sock = socket.create_connection((host, 4000), timeout,
                source_address=(config['source_ip'], 0) if config.get('source_ip') else None)
            sock.settimeout(timeout)
            sock.sendall(b'*IDN?\n')
            data = b''; deadline = time.monotonic() + timeout
            while b'\n' not in data and len(data) < 1024:
                remaining = deadline - time.monotonic()
                if remaining <= 0: raise TimeoutError('identity timeout')
                sock.settimeout(remaining)
                chunk = sock.recv(1024-len(data))
                if not chunk: raise OSError('incomplete identity')
                data += chunk
            if b'\n' not in data: raise OSError('missing identity terminator')
            parts = [p.strip() for p in data.decode('ascii').split(',')]
            if len(parts) < 3 or parts[:3] != ['TEKTRONIX', selector['model'], selector['serial']]:
                raise OSError('identity mismatch')
            return host, sock
        except (OSError, UnicodeError):
            if sock is not None: sock.close()
            return None

    hint = config.get('host')
    if hint and ipaddress.ip_address(hint) not in network:
        raise ValueError('host hint outside discovery subnet')
    if hint:
        found = probe(hint)
        if found: return found
    hosts = [str(ip) for ip in network.hosts() if str(ip) != hint]
    with ThreadPoolExecutor(max_workers=16) as pool:
        matches = [item for item in pool.map(probe, hosts) if item is not None]
    if len(matches) != 1:
        for _, sock in matches: sock.close()
        raise OSError(f'DPO4104 discovery found {len(matches)} matching devices; expected one')
    return matches[0]
