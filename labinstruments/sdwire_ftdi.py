"""Serial-selected libftdi SDWire control; never rebuild USB identity defaults."""
import ctypes as c
from pathlib import Path
from .storage import fail


def ftx_checksum(raw):
    """FT-X 256-byte MTP checksum, including factory words 0x40..0x4f.

    Matches libftdi TYPE_230X: user words 0x12..0x3f are excluded.
    """
    if len(raw) != 256:fail('PROTOCOL','Expected 256-byte FT-X EEPROM')
    value=0xaaaa
    for index in list(range(0x12))+list(range(0x40,0x7f)):
        value ^= int.from_bytes(raw[2*index:2*index+2],'little')
        value=((value<<1)|(value>>15)) & 0xffff
    return value.to_bytes(2,'little')


def cbus0_iomode_image(raw):
    if ftx_checksum(raw) != raw[-2:]:fail('VERIFY','Original FT-X EEPROM checksum invalid')
    result=bytearray(raw)
    result[0x1a]=8
    result[-2:]=ftx_checksum(result)
    return bytes(result)


class FT200XControl:
    def __init__(self, library, serial, vid=0x0403, pid=0x6015):
        self.lib = c.CDLL(str(library))
        signatures = {
            'ftdi_new': (c.c_void_p, []),
            'ftdi_free': (None, [c.c_void_p]),
            'ftdi_usb_open_desc': (c.c_int, [c.c_void_p,c.c_int,c.c_int,c.c_char_p,c.c_char_p]),
            'ftdi_usb_close': (c.c_int, [c.c_void_p]),
            'ftdi_read_eeprom': (c.c_int, [c.c_void_p]),
            'ftdi_eeprom_decode': (c.c_int, [c.c_void_p,c.c_int]),
            'ftdi_get_eeprom_value': (c.c_int, [c.c_void_p,c.c_int,c.POINTER(c.c_int)]),
            'ftdi_get_eeprom_buf': (c.c_int, [c.c_void_p,c.c_void_p,c.c_int]),
            'ftdi_set_eeprom_buf': (c.c_int, [c.c_void_p,c.c_void_p,c.c_int]),
            'ftdi_eeprom_build': (c.c_int, [c.c_void_p]),
            'ftdi_write_eeprom': (c.c_int, [c.c_void_p]),
            'ftdi_read_pins': (c.c_int, [c.c_void_p,c.POINTER(c.c_ubyte)]),
            'ftdi_set_bitmode': (c.c_int, [c.c_void_p,c.c_ubyte,c.c_ubyte]),
            'ftdi_get_error_string': (c.c_char_p, [c.c_void_p]),
        }
        for name,(result,args) in signatures.items():
            fn=getattr(self.lib,name);fn.restype=result;fn.argtypes=args
        self.ctx=self.lib.ftdi_new()
        if not self.ctx:fail('IO','ftdi_new failed')
        try:self.check(self.lib.ftdi_usb_open_desc(self.ctx,vid,pid,None,serial.encode()))
        except BaseException:
            self.lib.ftdi_free(self.ctx);self.ctx=None;raise

    def check(self, value):
        if value < 0:
            fail('IO', self.lib.ftdi_get_error_string(self.ctx).decode(errors='replace'))
        return value

    def eeprom(self):
        self.check(self.lib.ftdi_read_eeprom(self.ctx))
        self.check(self.lib.ftdi_eeprom_decode(self.ctx,0))
        def get(field):
            value=c.c_int();self.check(self.lib.ftdi_get_eeprom_value(self.ctx,field,c.byref(value)))
            return value.value
        size=get(43)
        if not 128 <= size <= 4096:fail('PROTOCOL','Unexpected EEPROM size')
        buf=c.create_string_buffer(size)
        self.check(self.lib.ftdi_get_eeprom_buf(self.ctx,buf,size))
        return dict(cbus0=get(17),vid=get(0),pid=get(1),size=size),buf.raw

    def state(self):
        config,_=self.eeprom()
        if config['cbus0'] != 8:
            fail('UNCOMMISSIONED_FACTORY','FT200X CBUS0 is not IOMODE; back up and commission it first')
        value=c.c_ubyte();self.check(self.lib.ftdi_read_pins(self.ctx,c.byref(value)))
        return 'host' if value.value & 1 else 'target'

    def select(self, state):
        if state not in ('host','target'):fail('OFF_UNSUPPORTED','No OFF on SDWire v1')
        self.state()  # Verify CBUS function before driving the mux.
        # Upstream sd-mux selectTarget uses 0xf1/0xf0. Only CBUS0 is needed;
        # keep other CBUS pins inputs, preserving unrelated factory functions.
        self.check(self.lib.ftdi_set_bitmode(self.ctx,0x11 if state=='host' else 0x10,0x20))
        if self.state()!=state:fail('PROTOCOL','SDWire CBUS readback mismatch')

    def commission_cbus0(self, backup, target_stopped):
        """Preserve USB IDs/strings/user data; change only CBUS0 and checksum.

        Caller owns SDWire and DUT leases. Backup must be a new private path.
        Physical reconnect may be required to activate new MTP configuration.
        """
        if target_stopped() is not True:fail('DUT_NOT_QUIESCED','Stop DUT before MTP write')
        config,raw=self.eeprom()
        if config['vid']!=0x0403 or config['pid']!=0x6015:
            fail('IDENTITY','Commissioning supports factory FT200X only')
        path=Path(backup)
        with path.open('xb') as stream:
            path.chmod(0o600)
            stream.write(raw);stream.flush()
            import os
            os.fsync(stream.fileno())
        updated=cbus0_iomode_image(raw)
        if updated==raw:return dict(written=False,cbus0=8)
        # Initialize libftdi's connected-device validation. Discard its rebuilt
        # defaults and replace the buffer with the minimally patched original.
        self.check(self.lib.ftdi_eeprom_build(self.ctx))
        buffer=c.create_string_buffer(updated,len(updated))
        self.check(self.lib.ftdi_set_eeprom_buf(self.ctx,buffer,len(updated)))
        if target_stopped() is not True:fail('DUT_NOT_QUIESCED','DUT guard lost before MTP write')
        self.check(self.lib.ftdi_write_eeprom(self.ctx))
        actual,readback=self.eeprom()
        if readback!=updated:fail('VERIFY','MTP readback mismatch; retain original backup')
        return dict(written=True,cbus0=actual['cbus0'],
                    changed_offsets=[i for i in range(len(raw)) if raw[i]!=updated[i]])

    def close(self):
        if self.ctx:
            self.lib.ftdi_usb_close(self.ctx);self.lib.ftdi_free(self.ctx);self.ctx=None

    def __enter__(self):return self
    def __exit__(self,*args):self.close()
