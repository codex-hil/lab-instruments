"""Small model profiles. Active methods are intentionally narrower than full SCPI."""
import math
import time

PROFILES = {
 'psw800-1.44': ('PSW800-1.44', 'supply', 1, 2268),
 'ngp814': ('NGP814', 'supply', 4, 5025),
 'b2910bl': ('B2910BL', 'smu', 1, 5025),
 'smb100a': ('SMB100A', 'rf', 1, 5025),
 'afg1062': ('AFG1062', 'awg', 2, None),
 'mp750288': ('MP750288', 'awg', 2, 3000),
 'mso4104': ('MSO4104', 'scope', 4, 4000),
 'mso2002b': ('MSO2002B', 'scope', 2, None),
 'tbs1022': ('TBS 1022', 'scope', 2, None),
 'dmm7510': ('MODEL DMM7510', 'meter', 1, 5025),
 '6487': ('MODEL 6487', 'picoammeter', 1, 4001),
 '8550': ('8550', 'load', 1, 4001),
 'n9918b': ('N9918B', 'analyzer', 1, 5025),
}
ACTIVE = {'supply', 'smu', 'rf', 'awg', 'load', 'picoammeter'}


def numeric(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('expected finite JSON number, not text or boolean')
    return float(value)


def validate(model, params, limits):
    """Validate a COMPLETE desired state before any I/O, including OFF or ON choice."""
    category = PROFILES[model][1]
    fields = {
        'supply': {'voltage', 'current'},
        'smu': {'voltage', 'current'},
        'picoammeter': {'voltage', 'current'},
        'rf': {'frequency', 'dbm'},
        'awg': {'frequency', 'vpp', 'offset'},
        'load': {'current'},
    }
    if category not in fields:
        raise ValueError('model has no validated source/load API')
    if set(params) != fields[category] | {'channel', 'enable'}:
        raise ValueError('complete state required; unknown fields forbidden')
    if type(params['channel']) is not int or not 1 <= params['channel'] <= PROFILES[model][2]:
        raise ValueError('invalid channel')
    if type(params['enable']) is not bool:
        raise ValueError('enable must be boolean')
    for key in fields[category]:
        numeric(params[key])
    if not limits.get('allow_output', False) and params['enable']:
        raise ValueError('output enable disabled by administrator')
    def check(value, lo, hi):
        low, high = numeric(limits[lo]), numeric(limits[hi])
        if not low <= value <= high:
            raise ValueError(f'outside policy: {lo}..{hi}')
    if category in {'supply', 'smu', 'picoammeter'}:
        check(params['voltage'], 'voltage_min', 'voltage_max')
        check(params['current'], 'current_min', 'current_max')
        if params['current'] <= 0 or (category == 'supply' and params['voltage'] < 0):
            raise ValueError('invalid source setpoint')
        if category == 'picoammeter':
            if abs(params['voltage']) > 500:
                raise ValueError('6487 voltage must be within -500..500 V')
            if params['current'] not in (25e-6, 250e-6, 2.5e-3, 25e-3):
                raise ValueError('6487 current limit must be 25uA, 250uA, 2.5mA or 25mA')
            if abs(params['voltage']) > 10 and params['current'] > 2.5e-3:
                raise ValueError('6487 50/500 V ranges allow at most 2.5mA')
        power = abs(params['voltage']) * params['current']
    elif category == 'rf':
        check(params['frequency'], 'frequency_min', 'frequency_max')
        check(params['dbm'], 'dbm_min', 'dbm_max')
        power = 10 ** (params['dbm'] / 10) / 1000
    elif category == 'awg':
        check(params['frequency'], 'frequency_min', 'frequency_max')
        check(params['vpp'], 'vpp_min', 'vpp_max')
        if params['vpp'] <= 0:
            raise ValueError('vpp must be positive')
        # Conservative envelope: assume display calibrated for 50 ohm, actual open circuit.
        peak = 2 * (abs(params['offset']) + params['vpp'] / 2)
        if peak > numeric(limits['voltage_peak_max']) or peak / 50 > numeric(limits['current_max']):
            raise ValueError('AWG peak voltage/current envelope exceeds policy')
        power = peak * peak / 50
    else:
        check(params['current'], 'current_min', 'current_max')
        if params['current'] <= 0:
            raise ValueError('load current must be positive')
        # Supply voltage can change externally; this is a design envelope, NOT a measured trip.
        power = numeric(limits['external_voltage_max']) * params['current']
    if power > numeric(limits['power_max']):
        raise ValueError('worst-case setpoint power exceeds policy')
    return dict(params)


class Driver:
    def __init__(self, transport, model, serial=None):
        if model not in PROFILES:
            raise ValueError('unknown model')
        self.io, self.model, self.serial = transport, model, serial
        self.category = PROFILES[model][1]
        if model == 'mso4104' and getattr(transport, 'config', {}).get('kind') == 'tcp':
            transport.config.setdefault('read_padding', '\r')

    def identify(self):
        text = self.io.query('*IDN?')
        parts = [x.strip() for x in text.split(',')]
        if len(parts) < 3 or parts[1].upper() != PROFILES[self.model][0].upper():
            raise ValueError(f'unexpected instrument identity: {text}')
        if self.serial and parts[2] != self.serial:
            raise ValueError('serial number mismatch; possible swapped instrument')
        return text

    def off(self):
        commands = {
            'supply': ['OUTP:GEN 0'] if self.model == 'ngp814' else ['OUTP OFF'],
            'smu': ['OUTP:OFF:MODE HIZ', 'OUTP OFF'], 'rf': ['OUTP OFF'],
            'awg': ['OUTP1 OFF', 'OUTP2 OFF'], 'load': ['INP OFF'],
            'picoammeter': ['SOUR:VOLT:SWE:ABOR', 'SOUR:VOLT:STAT OFF'],
        }.get(self.category, [])
        for command in commands:
            self.io.write(command)
        queries = {
            'supply': ['OUTP:GEN?'] if self.model == 'ngp814' else ['OUTP?'],
            'smu': ['OUTP?'], 'rf': ['OUTP?'], 'awg': ['OUTP1?', 'OUTP2?'],
            'load': ['INP:STAT?'], 'picoammeter': ['SOUR:VOLT:STAT?']
        }.get(self.category, [])
        if any(self.io.query(c).upper() not in {'0', 'OFF'} for c in queries):
            raise OSError('output OFF not confirmed')
        return {'off_confirmed': bool(queries)}

    def apply(self, params, limits):
        p = validate(self.model, params, limits)
        self.identify()
        self.off()  # All outputs OFF, including other channels; no hidden parallel activity.
        ch = p['channel']; w = self.io.write; q = self.io.query
        expected = {}; checks = {}
        def setting(cmd, value):
            w(f'{cmd} {value:.12g}'); expected[cmd + '?'] = value
        try:
            if self.category == 'supply':
                if self.model == 'ngp814':
                    for i in range(1,5):
                        w(f'INST OUT{i}'); w('OUTP:SEL 0')
                        if q('OUTP:SEL?') not in {'0','OFF'}:
                            raise OSError('NGP channel deselection not confirmed')
                    w(f'INST OUT{ch}')
                    vp, ip = 'VOLT', 'CURR'
                else:
                    vp, ip = 'SOUR:VOLT', 'SOUR:CURR'
                setting(ip, p['current']); setting(vp, p['voltage'])
                enable = ['OUTP:SEL 1', 'OUTP:GEN 1'] if self.model == 'ngp814' else ['OUTP ON']
                output_query = 'OUTP:GEN?' if self.model == 'ngp814' else 'OUTP?'
            elif self.category == 'smu':
                # Only DC voltage sourcing, local sense. Current compliance is mandatory.
                for c in ['ABOR','OUTP:ON:AUTO OFF','OUTP:OFF:MODE HIZ','SENS:REM OFF','SOUR:FUNC:MODE VOLT','SOUR:VOLT:MODE FIX']:
                    w(c)
                checks.update({'OUTP:ON:AUTO?':'0','OUTP:OFF:MODE?':'HIZ','SOUR:FUNC:MODE?': 'VOLT', 'SOUR:VOLT:MODE?': 'FIX', 'SENS:REM?': '0'})
                setting('SENS:CURR:PROT', p['current']); setting('SOUR:VOLT', p['voltage'])
                enable, output_query = ['OUTP ON'], 'OUTP?'
            elif self.category == 'picoammeter':
                # Set a conservative limit before changing range; never bypass interlock.
                setting('SOUR:VOLT:ILIM', 25e-6)
                voltage_range = 10 if abs(p['voltage']) <= 10 else 50 if abs(p['voltage']) <= 50 else 500
                setting('SOUR:VOLT:RANG', voltage_range)
                setting('SOUR:VOLT:ILIM', p['current'])
                setting('SOUR:VOLT', p['voltage'])
                checks['SOUR:VOLT:SWE:STAT?'] = '0'
                enable, output_query = ['SOUR:VOLT:STAT ON'], 'SOUR:VOLT:STAT?'
            elif self.category == 'rf':
                w('UNIT:POW DBM'); checks['UNIT:POW?']='DBM'
                for c in ['AM:STAT OFF','FM:STAT OFF','PM:STAT OFF','PULM:STAT OFF','FREQ:MODE CW','POW:MODE CW']:
                    w(c); checks[c.split()[0]+'?'] = '0' if c.endswith('OFF') else 'CW'
                setting('POW', p['dbm']); setting('FREQ', p['frequency'])
                enable, output_query = ['OUTP ON'], 'OUTP?'
            elif self.category == 'awg':
                prefix = f'SOUR{ch}:'
                modes = ['MOD','SWE','BURS'] if self.model == 'mp750288' else ['AM','FM','PM','FSK','PSK','ASK','PWM','BURS']
                for mode in modes:
                    w(prefix + mode + ':STAT OFF'); checks[prefix+mode+':STAT?'] = '0'
                if self.model == 'afg1062':
                    w(prefix+'FREQ:MODE CW'); checks[prefix+'FREQ:MODE?'] = 'CW'
                w(prefix+'FUNC SIN'); checks[prefix+'FUNC?'] = 'SIN'
                setting(prefix+'VOLT', p['vpp']); setting(prefix+'VOLT:OFFS', p['offset'])
                setting(prefix+'FREQ', p['frequency'])
                enable, output_query = [f'OUTP{ch} ON'], f'OUTP{ch}?'
            else:
                w('INP:SHOR OFF'); w('FUNC CURR'); w('CURR:RANG 3')
                checks.update({'FUNC?':'CURR','INP:SHOR?':'0'})
                setting('CURR', p['current'])
                enable, output_query = ['INP ON'], 'INP:STAT?'
            actual = {}
            for cmd, val in expected.items():
                got = float(q(cmd)); actual[cmd] = got
                if not math.isfinite(got) or not math.isclose(got, val, rel_tol=1e-6, abs_tol=1e-9):
                    raise OSError(f'setpoint readback mismatch: {cmd}')
            for cmd, val in checks.items():
                actual_mode = q(cmd).strip('"').upper()
                allowed = {'0', 'OFF'} if val == '0' else {'1', 'ON'} if val == '1' else {val}
                if actual_mode not in allowed:
                    raise OSError(f'mode readback mismatch: {cmd}')
            # Readback rounding must also satisfy the policy exactly.
            readback = dict(p)
            for key, cmd in {
                'supply': {'voltage':vp+'?', 'current':ip+'?'} if self.category=='supply' else {},
                'smu': {'voltage':'SOUR:VOLT?','current':'SENS:CURR:PROT?'},
                'rf': {'dbm':'POW?','frequency':'FREQ?'},
                'awg': {k:f'SOUR{ch}:{c}?' for k,c in [('vpp','VOLT'),('offset','VOLT:OFFS'),('frequency','FREQ')]},
                'picoammeter': {'voltage':'SOUR:VOLT?', 'current':'SOUR:VOLT:ILIM?'},
                'load': {'current':'CURR?'}
            }[self.category].items(): readback[key] = actual[cmd]
            validate(self.model, readback, limits)
            if p['enable']:
                if self.category == 'picoammeter' and q('SOUR:VOLT:INT:FAIL?').strip().upper() not in {'0', 'OFF'}:
                    raise OSError('6487 interlock open or status unknown; output enable refused')
                for cmd in enable:w(cmd)
                if q(output_query).upper() not in {'1','ON'}:
                    raise OSError('output ON not confirmed')
            return {'state':readback,'readback':actual}
        except BaseException:
            # Never retry an ambiguous ON; best effort OFF, report uncertainty if it fails.
            try:self.off()
            except Exception as error:raise OSError('operation failed AND output OFF could not be confirmed') from error
            raise

    def read(self, operation, channel=1):
        if type(channel) is not int or not 1 <= channel <= PROFILES[self.model][2]:
            raise ValueError('invalid channel')
        self.identify()
        if operation == 'identity': return self.io.query('*IDN?')
        if self.category in {'supply','smu','load'} and operation in {'voltage','current'}:
            if self.model=='ngp814': self.io.write(f'INST OUT{channel}')
            prefix = 'FETC' if self.category=='smu' else 'MEAS'
            return self.io.query(prefix + (':VOLT?' if operation=='voltage' else ':CURR?'))
        if self.category == 'meter' and operation == 'reading': return self.io.query('READ?')
        if self.category == 'picoammeter':
            if operation == 'reading': return self.io.query('READ?')
            if operation == 'source_state':
                # These are source SETTINGS, not a measurement of terminal voltage.
                return {key: self.io.query(cmd) for key, cmd in {
                    'voltage_setpoint_v': 'SOUR:VOLT?', 'current_limit_a': 'SOUR:VOLT:ILIM?',
                    'voltage_range_v': 'SOUR:VOLT:RANG?', 'enabled': 'SOUR:VOLT:STAT?',
                    'interlock_asserted': 'SOUR:VOLT:INT:FAIL?',
                    'sweep_running': 'SOUR:VOLT:SWE:STAT?',
                }.items()}
        if self.category == 'scope' and operation in {'frequency','vpp'}:
            self.io.write('HEADER OFF'); self.io.write(f'MEASU:IMMED:SOURCE1 CH{channel}')
            self.io.write('MEASU:IMMED:TYPE '+('FREQ' if operation=='frequency' else 'PK2PK'))
            return self.io.query('MEASU:IMMED:VALUE?')
        if self.category=='analyzer' and operation=='marker': return self.io.query('CALC:MARK1:Y?')
        raise ValueError('unsupported operation; no raw SCPI in protected API')

    def configure_acquisition(self, channels, plan, volts_per_div):
        """Configure simultaneous DC voltage acquisition and return actual settings."""
        from .scope_acquisition import configure
        return configure(self, channels, plan, volts_per_div)

    def acquire_waveforms(self, timeout=10, cancel=None):
        """Return channels from ONE stopped acquisition, scaled to volts and seconds."""
        from .scope_acquisition import acquire
        return acquire(self, timeout, cancel)

    def stop_acquisition(self):
        if self.model != 'mso4104': raise ValueError('unsupported acquisition capability')
        self.io.write('ACQ:STATE STOP')
