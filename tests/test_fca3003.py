import unittest

from labinstruments.drivers import Driver
from labinstruments.fca3003 import FCA3003, InstrumentError


class CounterFake:
    timeout = 4.0

    def __init__(self, reply='1.00000000000E+007', status=0):
        self.commands = []
        self.reply = reply
        self.status = iter((0, status))
        self.identity = 'TEKTRONIX,FCA3003,TEST,V1.0'
        self.language = 'NAT'
        self.errors = iter(('0,"No error"',) * 3)

    def write(self, command):
        self.commands.append(command)

    def query(self, command):
        self.commands.append(command)
        if command == '*IDN?': return self.identity
        if command == 'SYST:LANG?': return self.language
        if command == 'SYST:ERR?': return next(self.errors)
        if command == 'STAT:QUES?': return str(next(self.status))
        if command == 'READ?': return self.reply
        raise AssertionError(command)


class CounterTests(unittest.TestCase):
    def test_generic_driver_and_input_c(self):
        io = CounterFake()
        self.assertEqual(Driver(io, 'fca3003', 'TEST').read('frequency', 3), io.reply)
        self.assertIn('CONF:FREQ (@3)', io.commands)
        self.assertLess(io.commands.index('CONF:FREQ (@3)'), io.commands.index('SYST:TOUT ON'))
        self.assertLess(io.commands.index('ACQ:APER 0.1'), io.commands.index('READ?'))
        self.assertFalse(any(c.startswith('MEAS:') for c in io.commands))

    def test_all_operations_and_units(self):
        for operation, (function, unit, channels) in FCA3003.OPERATIONS.items():
            for channel in channels:
                with self.subTest(operation=operation, channel=channel):
                    io = CounterFake('0.5')
                    self.assertEqual(FCA3003(io).measure(operation, channel), 0.5)
                    selection = f'(@{channel})'
                    if operation in FCA3003.DUAL:
                        selection += f',(@{2 if channel == 1 else 1})'
                    self.assertIn(f'CONF:{function} {selection}', io.commands)
        self.assertEqual(FCA3003.OPERATIONS['duty_cycle'][1], '1')

    def test_explicit_pair(self):
        io = CounterFake()
        FCA3003(io).measure('frequency_ratio', 3, second_channel=2)
        self.assertIn('CONF:FREQ:RAT (@3),(@2)', io.commands)

    def test_reject_invalid_arguments_before_io(self):
        invalid = [
            {'operation': 'raw'}, {'channel': True}, {'channel': 5},
            {'operation': 'vpp', 'channel': 3}, {'second_channel': 2},
            {'operation': 'phase', 'second_channel': 3},
            {'aperture': 0}, {'aperture': float('nan')}, {'aperture': True},
            {'measurement_timeout': 0.001}, {'measurement_timeout': 4},
            {'aperture': 2, 'measurement_timeout': 1},
        ]
        for args in invalid:
            with self.subTest(args=args):
                io = CounterFake()
                with self.assertRaises(ValueError): FCA3003(io).measure(**args)
                self.assertEqual(io.commands, [])

    def test_identity_and_language_fail_before_configuration(self):
        for identity, serial, language in (
            ('TEKTRONIX,FCA3000,TEST,V1', None, 'NAT'),
            ('TEKTRONIX,FCA3003,OTHER,V1', 'TEST', 'NAT'),
            ('TEKTRONIX,FCA3003,TEST,V1', None, 'COMP'),
        ):
            io = CounterFake()
            io.identity, io.language = identity, language
            with self.assertRaises((ValueError, InstrumentError)):
                FCA3003(io, serial).measure()
            self.assertFalse(any(c.startswith('CONF') for c in io.commands))

    def test_missing_signal_is_timeout_even_with_finite_reply(self):
        io = CounterFake('0', status=1024)
        with self.assertRaises(TimeoutError): FCA3003(io).measure()
        self.assertEqual(io.commands.count('READ?'), 1)

    def test_invalid_scalars_and_questionable_status(self):
        for reply in ('NaN', 'Inf', '-Inf', '9.9e37', 'garbage', '1,2', ''):
            with self.subTest(reply=reply), self.assertRaises(InstrumentError):
                FCA3003(CounterFake(reply)).measure()
        for status in (512, 256, 2048, 16384):
            with self.subTest(status=status), self.assertRaises(InstrumentError):
                FCA3003(CounterFake(status=status)).measure()

    def test_existing_error_is_reported_without_clearing_queue(self):
        io = CounterFake()
        io.errors = iter(('-100,"Command error, previous client"',))
        with self.assertRaisesRegex(InstrumentError, 'previous client'):
            FCA3003(io).measure()
        self.assertNotIn('*CLS', io.commands)
        self.assertNotIn('READ?', io.commands)

    def test_configuration_error_prevents_acquisition(self):
        io = CounterFake()
        io.errors = iter(('0,"No error"', '-113,"Undefined header"'))
        with self.assertRaisesRegex(InstrumentError, 'Undefined header'):
            FCA3003(io).measure()
        self.assertNotIn('READ?', io.commands)

    def test_transport_failure_is_not_retried(self):
        class Broken(CounterFake):
            def query(self, command):
                if command == 'READ?':
                    self.commands.append(command)
                    raise TimeoutError('transport deadline')
                return super().query(command)
        io = Broken()
        with self.assertRaisesRegex(TimeoutError, 'transport deadline'):
            FCA3003(io).measure()
        self.assertEqual(io.commands.count('READ?'), 1)


if __name__ == '__main__':
    unittest.main()
