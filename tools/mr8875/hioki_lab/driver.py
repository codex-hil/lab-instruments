"""MR8875 LAN driver. Source: supplied HIOKI interface manual, chapters 2/3."""
import math
import socket
import threading
import time

MODULES = {0: 'empty', 1: 'MR8901', 2: 'MR8903', 3: 'MR8902', 4: 'MR8904', 5: 'MR8905'}
VOLT_RANGES = [.0005, .001, .005, .01, .05, .1, .5, 1., 5.]
TEMP_RANGES = [10., 20., 50., 100.]

class InstrumentError(RuntimeError):
    pass

class MR8875:
    def __init__(self, host='192.168.2.13', port=8802, timeout=4):
        self.host, self.port, self.timeout = host, port, timeout
        self.lock = threading.RLock()
        self.sock = None
        self.buffer = b''
        self.channels = []
        self.identity = None
        self.modules = []
        self.capture_config = None

    def close(self):
        with self.lock:
            if self.sock:
                self.sock.close()
            self.sock, self.buffer = None, b''

    def _send(self, command):
        if '\n' in command or '\r' in command:
            raise ValueError('One command per call')
        if not self.sock:
            self.sock = socket.create_connection((self.host, self.port), self.timeout)
            self.sock.settimeout(self.timeout)
        self.sock.sendall((command + '\r\n').encode('ascii'))

    @staticmethod
    def payload(line):
        # Optional SCPI response header, independent of the instrument setting.
        if line.startswith((':', '*')):
            line = line.split(' ', 1)[-1]
        return line.strip()

    def query(self, command):
        with self.lock:
            try:
                self._send(command)
                while b'\n' not in self.buffer:
                    part = self.sock.recv(65536)
                    if not part:
                        raise InstrumentError('Urządzenie zamknęło połączenie')
                    self.buffer += part
                    if len(self.buffer) > 2_000_000:
                        raise InstrumentError('Odpowiedź przekracza limit')
                line, self.buffer = self.buffer.split(b'\n', 1)
                return self.payload(line.decode('ascii').strip())
            except (OSError, UnicodeError, InstrumentError) as e:
                self.close()  # Never reuse a socket with an unread/partial response.
                raise InstrumentError(str(e)) from e

    def write(self, command):
        with self.lock:
            try:
                self._send(command)
            except OSError as e:
                self.close()
                raise InstrumentError(str(e)) from e

    def checked(self, command):
        with self.lock:
            # :ERROR? reports the last front-panel warning, not a SCPI error queue.
            # ESR query clears the event register; bits 4/5 flag execution/command errors.
            self.query('*ESR?')
            self.write(command)
            self.query('*OPC?')
            events = int(self.query('*ESR?'))
            if events & 0x30:
                raise InstrumentError(f'{command}: błąd komendy (ESR {events})')

    def discover(self):
        with self.lock:
            identity = self.query('*IDN?')
            if ',MR8875,' not in identity:
                raise InstrumentError('Pod tym adresem nie ma MR8875')
            slots = [int(v) for v in self.query('*OPT?').split(',')]
            if len(slots) != 4:
                raise InstrumentError('Niepoprawna lista modułów')
            self.identity = identity
            self.modules = [{'slot': i+1, 'model': MODULES.get(v, f'unknown:{v}')}
                            for i, v in enumerate(slots)]
            self.channels = [f'CH{i+1}_{n}' for i, v in enumerate(slots)
                             for n in range(1, (15 if v in (3, 4) else 2 if v == 5 else 4)+1) if v]
            return self.configuration()

    def validate_channel(self, channel):
        if channel not in self.channels:
            raise ValueError('Nieznany kanał')
        return channel

    def idle(self):
        status = int(self.query(':STATus?'))
        if status:
            raise InstrumentError(f'Urządzenie jest zajęte (status {status})')

    def channel_config(self, channel):
        self.validate_channel(channel)
        mode = self.query(f':UNIT:MODE? {channel}').split(',')[-1]
        enabled = self.query(f':CONFigure:CHENable? {channel}').split(',')[-1] == 'ON'
        scale = float(self.query(f':UNIT:RANGe? {channel}').split(',')[-1])
        scaling = self.query(f':SCALing:SET? {channel}').split(',')[-1]
        unit = ('°C' if mode == 'TEMP' else 'CAN' if mode == 'CAN' else 'V')
        if scaling != 'OFF':
            unit = self.query(f':SCALing:UNIT? {channel}').split(',', 1)[-1].strip('"')
        result = {'id': channel, 'mode': mode, 'enabled': enabled, 'range': scale,
                  'unit': unit, 'scaling': scaling}
        if mode == 'TEMP':
            result['sensor'] = self.query(f':UNIT:SENSor? {channel}').split(',')[-1]
        return result

    def configuration(self):
        with self.lock:
            return {'identity': self.identity, 'host': self.host, 'port': self.port,
                    'modules': self.modules, 'status': int(self.query(':STATus?')),
                    'sample_seconds': float(self.query(':CONFigure:SAMPle?')),
                    'divisions': int(self.query(':CONFigure:SHOT?')),
                    'channels': [self.channel_config(ch) for ch in self.channels]}

    def live(self, channels):
        with self.lock:
            for ch in channels:
                self.validate_channel(ch)
            self.write(':MEMory:GETReal')
            values = {}
            for ch in channels:
                value = float(self.query(f':MEMory:REAL? {ch}').split(',')[-1])
                values[ch] = value if math.isfinite(value) and abs(value) < 1e20 else None
            return {'time': time.time(), 'values': values,
                    'status': int(self.query(':STATus?'))}

    def configure_channel(self, channel, mode, scale, enabled, sensor='K'):
        with self.lock:
            self.validate_channel(channel)
            slot = int(channel.split('_')[0][2:])
            if self.modules[slot-1]['model'] != 'MR8902':
                raise ValueError('Edycja w tej wersji jest dostępna dla MR8902')
            if mode not in ('VOLT', 'TEMP'):
                raise ValueError('Tryb: VOLT lub TEMP')
            if sensor not in ('K', 'J', 'E', 'T', 'N', 'R', 'S', 'B', 'W'):
                raise ValueError('Nieznana termopara')
            scale = float(scale)
            if scale not in (VOLT_RANGES if mode == 'VOLT' else TEMP_RANGES):
                raise ValueError('Nieprawidłowy zakres /div')
            if not isinstance(enabled, bool):
                raise ValueError('enabled musi być boolean')
            self.idle()
            self.checked(f':UNIT:MODE {channel},{mode}')
            if mode == 'TEMP':
                self.checked(f':UNIT:SENSor {channel},{sensor}')
            self.checked(f':UNIT:RANGe {channel},{scale:.12g}')
            self.checked(f':CONFigure:CHENable {channel},{"ON" if enabled else "OFF"}')
            return self.channel_config(channel)

    def configure_acquisition(self, sample, divisions):
        sample, divisions = float(sample), int(divisions)
        if not math.isfinite(sample) or not .01 <= sample <= 3:
            raise ValueError('Okres: 0,01–3 s')
        if not 5 <= divisions <= 1000:
            raise ValueError('Długość: 5–1000 działek')
        with self.lock:
            self.idle()
            self.checked(f':CONFigure:SAMPle {sample:.12g}')
            self.checked(f':CONFigure:SHOT {divisions}')
            return {'sample_seconds': float(self.query(':CONFigure:SAMPle?')),
                    'divisions': int(self.query(':CONFigure:SHOT?'))}

    def start(self):
        with self.lock:
            self.idle()
            config = self.configuration()
            self.checked(':STARt')
            self.capture_config = config
            return int(self.query(':STATus?'))

    def stop(self):
        with self.lock:
            self.checked(':STOP')
            return int(self.query(':STATus?'))

    def waveform(self, channels, max_points=100000):
        with self.lock:
            self.idle()
            count = int(self.query(':MEMory:MAXPoint?'))
            if count == 0:
                raise InstrumentError('Brak przebiegu w pamięci')
            if count > max_points:
                raise InstrumentError(f'Przebieg ma {count} próbek; limit tej wersji: {max_points}')
            # Capture settings before reading; sampling time is relative to first stored point.
            config = self.capture_config or self.configuration()
            data = {}
            for ch in channels:
                self.validate_channel(ch)
                if not next(c for c in config['channels'] if c['id'] == ch)['enabled']:
                    raise ValueError(f'{ch}: kanał wyłączony')
                self.checked(f':MEMory:POINt {ch},0')
                values = []
                while len(values) < count:
                    n = min(2000, count-len(values))
                    part = [float(v) for v in self.query(f':MEMory:VDATa? {n}').split(',')]
                    if len(part) != n:
                        raise InstrumentError('Niepełny blok przebiegu')
                    values.extend(v if math.isfinite(v) and abs(v)<1e20 else None for v in part)
                data[ch] = values
            return {'config': config, 'points': count, 'data': data,
                    'time_reference': 'seconds_from_first_stored_sample',
                    'sample_time_source': 'captured_before_start' if self.capture_config else 'current_settings_unverified'}
