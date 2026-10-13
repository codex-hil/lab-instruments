# Physical SDWire bounded read validation — 2026-10-13

**PASS_READ_ONLY.** Real controller `DP04I355` (`0403:6015`, factory FT200X)
with reader `0424:4050`, generic reader serial `000000264001`, card capacity
15716057088 bytes. Identity verified by controller serial, USB2640 hub/sibling
topology, reader VID/PID/serial, stable by-id, removable and capacity.

[report.json](report.json) records:

- topology identity PASS; partitions 1/2/5 identified;
- actual USB IN read-pins request PASS, raw byte 254;
- two equal bounded 1MiB block-device reads PASS, SHA256
  `9b490e44b1f31849e460ab108f802d2f2192aae856df58ed40bf66758612fcc1`;
- no card write, filesystem mount, EEPROM update, mux switching, reset or power action.

The raw factory CBUS byte is **not** qualified as ownership. State remains
unknown / UNCOMMISSIONED_FACTORY. Read-only PASS is not mux isolation, card-write
or Zynq-boot validation. Kernel block reads may use cache; this is not a media
stress/performance test. OFF remains unsupported and all production mutations
are blocked. Shared Genesys lease and SDWire lock held throughout the hardware window.

Administrator granted temporary control USB rw ACL and card **read-only** ACL.
No global disk-group membership. Earlier permission-blocked evidence remains in
[initial report](../hardware-2026-10-13/README.md) and
[USB-only ACL report](../hardware-2026-10-13-usb-acl/report.json).

[storage.json](storage.json) contains generated identity-bound configuration.
For the neighboring thread:

```sh
scripts/hil-storage --config reports/storage/hardware-2026-10-13-read-pass/storage.json sdwire-01 status --json
scripts/hil-storage --config reports/storage/hardware-2026-10-13-read-pass/storage.json sdwire-01 device --json
python3 scripts/bringup-sdwire-readonly.py --serial DP04I355 --output local/sdwire-read-replay
```

USB address and temporary ACLs can change after hotplug. Always re-discover
by serial, never reuse /dev/sdb as a write destination.
