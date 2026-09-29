#!/usr/bin/env python3
"""Read FT24C128A twice through FX2; never issue an EEPROM write command."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--libfx2', type=Path, required=True,
                        help='source directory produced by build-reader.sh')
    parser.add_argument('--restore-firmware', type=Path, required=True,
                        help='raw fx2lafw-cypress-fx2.fw to restore in RAM')
    parser.add_argument('--output', type=Path, required=True,
                        help='new directory for two dumps and report')
    args = parser.parse_args()
    source = args.libfx2.resolve()
    sys.path.insert(0, str(source / 'software'))
    import usb1
    from fx2 import FX2Device
    from fx2.format import input_data

    firmware = args.restore_firmware.read_bytes()
    if not 0 < len(firmware) <= 0x4000:
        parser.error('restore firmware must be a raw FX2 RAM image, at most 16 KiB')
    with (source / 'firmware/boot-cypress/boot-cypress.ihex').open('rb') as f:
        reader = list(input_data(f))
    with usb1.USBContext() as context:
        devices = [d for d in context.getDeviceList()
                   if (d.getVendorID(), d.getProductID()) == (0x04b4, 0x8613)]
        if len(devices) != 1:
            parser.error(f'expected exactly one 04b4:8613 device, found {len(devices)}')
    args.output.mkdir(parents=True, exist_ok=False)
    dev = FX2Device()
    try:
        dev.load_ram(reader)
        time.sleep(0.2)
        found = []
        for chip in range(0x50, 0x58):
            try:
                head = bytes(dev.control_read(usb1.REQUEST_TYPE_VENDOR, 0xA9, 0, chip, 16))
                if len(head) != 16:
                    raise RuntimeError('short EEPROM probe read')
                print(f'I2C 0x{chip:02x}: {head.hex(" ")}', flush=True)
                found.append(chip)
            except usb1.USBErrorPipe:
                print(f'I2C 0x{chip:02x}: no ACK', flush=True)
        if len(found) != 1:
            raise RuntimeError(f'expected one responding EEPROM, found {found}')
        chip = found[0]
        reads = []
        for n in (1, 2):
            data = bytearray()
            for addr in range(0, 16384, 64):
                chunk = dev.control_read(usb1.REQUEST_TYPE_VENDOR, 0xA9, addr, chip, 64)
                if len(chunk) != 64:
                    raise RuntimeError(f'short read at 0x{addr:04x}')
                data.extend(chunk)
            name = args.output / f'ft24c128a-0x{chip:02x}-read{n}.bin'
            with name.open('xb') as f:
                f.write(data)
            reads.append(bytes(data))
            print(f'{name}: {len(data)} bytes; SHA256 {hashlib.sha256(data).hexdigest()}')
        report = dict(address=hex(chip), length=len(reads[0]),
                      identical_reads=reads[0] == reads[1],
                      sha256=hashlib.sha256(reads[0]).hexdigest(),
                      all_ff=all(b == 255 for b in reads[0]),
                      first64=reads[0][:64].hex(' '))
        (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        if not report['identical_reads']:
            raise RuntimeError('two reads differ; do not treat as a verified backup')
        print('Two reads match.')
    finally:
        # Only RAM writes (request A0); no EEPROM writes (A9 OUT).
        dev.load_ram([(0, firmware)])
        print('Restored sigrok firmware in RAM.')


if __name__ == '__main__':
    main()
