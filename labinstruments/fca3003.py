"""Tektronix FCA3003 scalar SCPI measurements (manual 077049400, rev A).

Configuration deliberately replaces the current measurement setup. Use one
client per instrument. No automatic retries after transport failures.
"""
import csv
import math

from .drivers import Driver, numeric


class InstrumentError(OSError):
    """SCPI error or invalid measurement status."""


class FCA3003(Driver):
    # operation: (SCPI function, unit, supported physical input channels)
    OPERATIONS = {
        'frequency': ('FREQ', 'Hz', (1, 2, 3, 4, 6)),
        'period': ('PER', 's', (1, 2, 3)),
        'period_average': ('PER:AVER', 's', (1, 2, 3)),
        'positive_width': ('PWID', 's', (1, 2)),
        'negative_width': ('NWID', 's', (1, 2)),
        'duty_cycle': ('PDUT', '1', (1, 2)),
        'negative_duty_cycle': ('NDUT', '1', (1, 2)),
        'rise_time': ('RTIM', 's', (1, 2)),
        'fall_time': ('FTIM', 's', (1, 2)),
        'vpp': ('VOLT:PTP', 'V', (1, 2)),
        'voltage_max': ('VOLT:MAX', 'V', (1, 2)),
        'voltage_min': ('VOLT:MIN', 'V', (1, 2)),
        'frequency_ratio': ('FREQ:RAT', '1', (1, 2, 3)),
        'phase': ('PHAS', 'deg', (1, 2)),
        'time_interval': ('TINT', 's', (1, 2)),
    }
    DUAL = {'frequency_ratio', 'phase', 'time_interval'}

    def __init__(self, transport, serial=None):
        super().__init__(transport, 'fca3003', serial)

    def error(self):
        """Pop one error from the instrument's queue (does not clear all errors)."""
        reply = self.io.query('SYST:ERR?')
        try:
            parts = next(csv.reader([reply], skipinitialspace=True))
            if len(parts) != 2:
                raise ValueError()
            return int(parts[0]), parts[1]
        except (ValueError, csv.Error) as exc:
            raise InstrumentError(f'malformed SCPI error response: {reply!r}') from exc

    def check_error(self):
        code, message = self.error()
        if code:
            raise InstrumentError(f'FCA3003 SCPI error {code}: {message}')

    def abort(self):
        """Explicitly stop acquisition; does not drain a pending USB/TCP reply."""
        self.identify()
        self.io.write('ABOR')

    def measure_raw(self, operation='frequency', channel=1, *,
                    second_channel=None, aperture=0.1, measurement_timeout=1.0):
        """Configure and acquire one validated scalar, returning original ASCII.

        A/B are channels 1/2; C (3 GHz input) is channel 3. Frequency also accepts
        channel 4 (rear arming input) and 6 (internal reference). Pair measurements
        default to the other A/B input. CONFigure resets input/trigger settings;
        gate and timeout are therefore applied AFTER CONFigure, before READ?.
        Instrument timeout must fit inside the transport's read timeout.
        """
        if operation not in self.OPERATIONS:
            raise ValueError('unsupported FCA3003 operation')
        function, _, channels = self.OPERATIONS[operation]
        if type(channel) is not int or channel not in channels:
            raise ValueError('invalid channel for FCA3003 operation')
        if operation in self.DUAL:
            if second_channel is None:
                second_channel = 2 if channel == 1 else 1
            if type(second_channel) is not int or second_channel not in channels:
                raise ValueError('invalid second channel for FCA3003 operation')
        elif second_channel is not None:
            raise ValueError('second channel requires a dual-input operation')
        aperture = numeric(aperture)
        measurement_timeout = numeric(measurement_timeout)
        transport_timeout = getattr(self.io, 'timeout', 4.0)
        if not 20e-9 <= aperture <= 1000:
            raise ValueError('aperture must be 20 ns..1000 s')
        if not 0.01 <= measurement_timeout <= 1000:
            raise ValueError('measurement timeout must be 0.01..1000 s')
        if measurement_timeout <= aperture:
            raise ValueError('measurement timeout must exceed aperture')
        if measurement_timeout + 0.5 >= transport_timeout:
            raise ValueError('transport timeout must exceed measurement timeout by >0.5 s')
        self.identify()
        if self.io.query('SYST:LANG?').strip().upper() not in {'NAT', 'NATIVE'}:
            raise InstrumentError('FCA3003 requires native SCPI mode (SYST:LANG NAT)')
        self.check_error()  # Preserve/report a pre-existing error; never hide it with *CLS.
        selection = f'(@{channel})'
        if second_channel is not None:
            selection += f',(@{second_channel})'
        for command in (
            'ABOR', f'CONF:{function} {selection}', 'FORM ASC',
            'FORM:TINF OFF', 'INIT:CONT OFF',
            f'ACQ:APER {aperture:.12g}', 'SYST:TOUT:AUTO OFF',
            f'SYST:TOUT:TIME {measurement_timeout:.12g}', 'SYST:TOUT ON',
        ):
            self.io.write(command)
        self.check_error()
        self.io.query('STAT:QUES?')  # Clear stale event bits before the new acquisition.
        reply = self.io.query('READ?')
        status = int(self.io.query('STAT:QUES?'))
        code, message = self.error()
        if status & 1024:
            raise TimeoutError('FCA3003 measurement timed out (missing input signal); '
                               f'SCPI {code}: {message}')
        if code:
            raise InstrumentError(f'FCA3003 SCPI error {code}: {message}')
        if status & (16384 | 2048 | 512 | 256):
            raise InstrumentError(f'FCA3003 questionable measurement status: {status}')
        try:
            value = float(reply)
        except ValueError as exc:
            raise InstrumentError(f'invalid FCA3003 scalar response: {reply!r}') from exc
        if not math.isfinite(value) or abs(value) >= 1e30:
            raise InstrumentError(f'invalid FCA3003 measurement: {reply!r}')
        return reply

    def measure(self, operation='frequency', channel=1, **options):
        """Return a float, in OPERATIONS[operation][1] units."""
        return float(self.measure_raw(operation, channel, **options))
