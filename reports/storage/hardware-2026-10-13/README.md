# Physical SDWire inventory — 2026-10-13

**HARDWARE_READ_ONLY / PARTIAL.** One SDWire candidate identified by exact factory
FT200X, USB2640 hub and reader topology. No second SDWire was detected.

Controller: FT200X USB I2C `0403:6015`, serial `DP04I355`, path `1-1.1.1.2`.
Reader: `0424:4050`, generic serial `000000264001`, path `1-1.1.1.1`.
Same physical `0424:2640` hub. Card capacity: **15716057088 bytes**.
Stable by-id: `usb-Generic_Ultra_HS-SD_MMC_000000264001-0:0`.
Observed disk at this instant: `/dev/sdb`, removable, partitions 1/2/5.
The reader serial is generic, not the controller serial: topology remains mandatory.

[report.json](report.json) records topology identity PASS, register read and bounded
card read NOT_RUN due OS permissions (ACCESS). User has no disk group or passwordless
sudo. No USB reset, driver detach, mux switching, filesystem mount, card write,
EEPROM programming, DUT reset or power operation occurred. Shared Genesys lease
and SDWire lock held for the bounded hardware window.

Factory EEPROM/product differs from preconfigured `sd-wire`. The status is
**unknown / UNCOMMISSIONED_FACTORY**: presence of block device is not proof of
safe ownership or OFF. Existing safety gate rejects HOST/TARGET/OFF/flash.

[storage.json](storage.json) is a generated, topology/capacity-bound inventory config.
It does not authorize writes. From repo:

```sh
scripts/hil-storage --config reports/storage/hardware-2026-10-13/storage.json sdwire-01 status --json
scripts/hil-storage --config reports/storage/hardware-2026-10-13/storage.json sdwire-01 device --json
python3 scripts/bringup-sdwire-readonly.py --serial DP04I355 --output local/sdwire-retest
```

For bounded read testing, an administrator can grant temporary device ACLs:

```sh
sudo setfacl -m u:codex-hil:rw /dev/bus/usb/001/019
sudo setfacl -m u:codex-hil:r /dev/disk/by-id/usb-Generic_Ultra_HS-SD_MMC_000000264001-0:0
```

USB path 001/019 is specific to this enumeration; verify serial first after replug.
USBDEVFS needs a read/write control-device fd even for IN-only register requests.
The card ACL grants **read only**. No broad disk-group membership or chmod 666.
Read-pins request uses IN `0xc0/0x0c`, index 1; factory raw pins are not interpreted
as ownership until EEPROM role is qualified. Protocol reference:
[libftdi request definitions](https://www.intra2net.com/en/developer/libftdi/documentation/ftdi_8h.html).

Raw card test performs two identical bounded 1MiB reads, verifies the opened fd
against sysfs major/minor and full identity before/after, stores only SHA256.
It does not change partitions or filesystem state. A successful read does not
qualify electrical isolation or full autonomous programming.
