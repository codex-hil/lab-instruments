#!/usr/bin/env python3
"""Emit an allowlist rule; does not install it or change permissions."""
import argparse
import re
p=argparse.ArgumentParser();p.add_argument('--vendor',required=True);p.add_argument('--product',required=True);p.add_argument('--serial',required=True);a=p.parse_args()
if not re.fullmatch('[0-9a-fA-F]{4}',a.vendor) or not re.fullmatch('[0-9a-fA-F]{4}',a.product) or not re.fullmatch('[A-Za-z0-9_.:/-]+',a.serial):p.error('invalid USB selector')
print(f'SUBSYSTEM=="usbmisc", KERNEL=="usbtmc*", ATTRS{{idVendor}}=="{a.vendor.lower()}", ATTRS{{idProduct}}=="{a.product.lower()}", ATTRS{{serial}}=="{a.serial}", GROUP="labinst", MODE="0660"')
