#!/usr/bin/env python3
"""Emit an allowlist rule; does not install it or change permissions."""
import argparse
import re

p = argparse.ArgumentParser()
p.add_argument('--vendor', required=True)
p.add_argument('--product', required=True)
selector = p.add_mutually_exclusive_group(required=True)
selector.add_argument('--serial')
selector.add_argument('--topology')
a = p.parse_args()
if not re.fullmatch('[0-9a-fA-F]{4}', a.vendor) or not re.fullmatch('[0-9a-fA-F]{4}', a.product):
    p.error('invalid USB vendor/product')
if a.serial is not None:
    if not re.fullmatch('[A-Za-z0-9_.:/-]+', a.serial):
        p.error('invalid USB serial')
    match = f'ATTRS{{serial}}=="{a.serial}"'
else:
    if not re.fullmatch('[0-9]+-[0-9]+(?:[.][0-9]+)*', a.topology):
        p.error('invalid USB topology')
    match = f'KERNELS=="{a.topology}"'
print(f'SUBSYSTEM=="usbmisc", KERNEL=="usbtmc*", ATTRS{{idVendor}}=="{a.vendor.lower()}", ATTRS{{idProduct}}=="{a.product.lower()}", {match}, GROUP="labinst", MODE="0660"')
