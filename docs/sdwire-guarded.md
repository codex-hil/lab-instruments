# SDWire v1: guarded HOST/DUT image programming

Added 2026-10-27 following the owner's explicit instruction to repair the
controller/library. A persistent OFF is not a requirement for this separate
workflow. SDWire still has **no OFF**, and this software does not claim
power isolation, electrical measurements or host-crash fail safety.

The original `SDWireStorage`/isolated `RemovableStorage` and existing CLI
retain their old contract. New Python APIs are `GuardedSDWire` and
`SDWireSession` in `labinstruments.storage_sdwire`. They support whole-image
flashing, not mounted boot-file updates. No configuration boolean enables
writes on the old backend.

## Workflow and ownership

The caller holds the actual shared DUT lease for the entire operation,
including restore/boot validation. `SDWireSession` holds the existing
`~/.local/state/hil-storage/hil-storage-SERIAL.lock` throughout the session.
Do not change the lock runtime to bypass another owner.

Supply `stop_target()` and `target_stopped()` callbacks from the DUT owner.
The latter must read back the actual continuously held stop/reset/power state;
returning a configured `True` is not hardware verification. Stopping a running
Linux rootfs requires orderly flush/shutdown before holding the SD controller
or DUT stopped. A processor halt alone does not prove SD DMA stopped.

The session verifies the guard before HOST/DUT selection and each streaming
write/readback block, rejects mounted filesystems, validates the reader's
serial/topology/by-id/major:minor/capacity, and opens the block writer with
O_EXCL and O_NOFOLLOW. Full readback is mandatory. bmap delegation is disabled
because its external write cannot check the guard between blocks.

Success selects DUT while the DUT remains stopped. Only the board owner may
then release reset/power and validate boot. No programming code automatically
starts a DUT. Failure attempts to retain HOST with the DUT stopped and keeps
the dirty journal. If the guard fails, ownership remains unknown; no false
OFF is logged. Explicit recovery requires the same guard and inspection of
the interrupted image. A dry-run may select HOST but opens no writer and
retains HOST. Host power loss/SIGKILL has no guaranteed cleanup.

Example API nesting (callbacks are supplied by the existing board wrapper):

```python
# The caller already holds the board's canonical flock.
with FT200XControl(library, serial) as controller:
    backend = GuardedSDWire(serial, '0403', '6015', reader=qualified_reader,
                           transport=controller, stop_target=stop_target,
                           target_stopped=target_stopped)
    with SDWireSession('zc706', backend, storage_runtime) as session:
        result = session.flash(image, verify=True)
# DUT is STILL STOPPED. Board wrapper can now release/reset and capture boot.
```

## Factory FT200X commissioning

`FT200XControl` selects by exact serial. For factory FT200X, CBUS0 must be
IOMODE (8). EEPROM readback checks this before mux control. Control uses only
CBUS0 (CBUS mask0x11 HOST /0x10 DUT), leaving the other CBUS pins inputs.
It checks the selection readback, rather than trusting command success.

`commission_cbus0(new_private_backup_path, target_stopped)` first checks the
DUT guard, reads and backs up the original 256-byte MTP image with fsync,
validates its checksum, and prepares a minimal patch: byte0x1a plus checksum
bytes0xfe/0xff. It preserves VID/PID, product/serial descriptors, user data
and factory bytes. It does not call EEPROM init-defaults or `--set-serial`.
The libftdi write skips reserved factory words; full readback must match.
No automatic write retry or automatic restore follows an error. Physical
reconnection may be necessary to activate the configuration; qualify real
HOST/DUT behavior before using the backend to write a card.

Sources reviewed:
- 3mdeb sd-mux `9dd189d973da64e033a0c5c2adb3d94b23153d94`,
  `src/main.cpp`: SDWire CBUS0 IOMODE and HOST/DUT polarity.
- libftdi `9da4394efeafa2fcfdc809a9bec3219c0a95e77a`, `src/ftdi.c`:
  TYPE_230X CBUS mapping, checksum excluding words0x12..0x3f, factory
  words0x40..0x4f included in checksum and skipped by MTP writes.

## Current validation and hardware block

50 storage tests ran successfully (one existing optional skip), including
nine new simulated tests for direct transitions, failed DUT stop, failed write,
explicit recovery, dry-run, unknown controller state, and minimal MTP patching.
These are **SIMULATED**, not physical switching/write qualification.

Physical controller DP04I33Y is positively associated with USB2640 reader
000000264001 and the 32-GB card. The read attempt with Nix Python/libftdi
failed `usb_open() failed`: device ACL grants greg but not codex-hil access.
The block device likewise has no codex-hil ACL. `sudo -n` requires a password.
No EEPROM backup/read completed, no EEPROM or SD content was written, and
no mux selection changed. Evidence: `reports/storage/controller-DP04I33Y-20261027`.
Next: administrator grants access to these exact two devices, read/backup MTP,
verify DUT stop path, then commission only if necessary and qualify switching.

## Physical commissioning and first SD boot (2026-10-27)

The access issue was resolved by an administrator granting ACLs only to the
identified control USB device and card. Original MTP read/backup PASS:
CBUS0 was AWAKE21, not GPIO. Private backup:
`~/.local/share/sdwire-backups/DP04I33Y/original-20261027.bin`, SHA256
`5923d46ed4cc7d8315f21789c67ace26385dcd2784ec57dfb33dd4c172172dca`.
Commissioning changed only byte0x1a and0xfe/0xff; full MTP readback PASS,
CBUS0=8, VID0403/PID6015 and serial DP04I33Y retained. One USB reset of the
exact controller activated the new function; no identity-default rewrite.

The old running ZC706 rootfs was already in ext4 `shutdown` and external
commands returned EIO. Its kernel lacks SysRq; attempted init halt was not
confirmed. These failures are retained. Recovery verified SDIO idle and SD
clock stopped, halted both A9s and held SDIO0 reference/CPU resets, with live
readback before the MTP change. This was not a clean filesystem shutdown.
Later, the freshly booted system completed a normal BusyBox-init halt,
rootfs read-only remount and kernel `System halted` before the next update.

HOST/DUT/HOST physically passed: card capacity becomes0 on HOST while DUT
owns it, then returns to31,914,983,424 bytes. The first test exposed a transient
zero-capacity enumeration bug; missing/zero-capacity media now returns
NO_CARD so the existing bounded wait retries, while wrong nonzero capacity
remains an identity error. Two regression tests were added. Full suite:
94 tests run,93 passed, one existing optional skip.

First image:335,544,832 bytes written and fully read back with matching SHA256
`921d516751de261b32bdc9d68513b7a96f1260a1b4d67c7a5f2c2cafad3dba1a`.
Before writing, all original partition extents and the entire overwritten
range were backed up and read a second time; untouched card tail was not
copied or overwritten. Backup on NVMe:
`/srv/codex-hil-nvme/sdwire-backups/DP04I33Y/pre-integrated-20261027.img`,
335,544,832 bytes, SHA256
`25dfb1311fbc924c558fc22c762b3e1072db10fb0a8b7260c9ecaca8198f028a`.
SPL/U-Boot/Linux/login/DHCP then passed from SD, with PL loaded by U-Boot,
no JTAG PL programming. Image packaging had omitted executable permissions
on the DDR tool; that service-start failure is retained, and the ZC706 project
is correcting and retesting the image. Do not equate the first boot PASS with
automatic PLL startup PASS. Manual permission correction did start both PLLs.

Scripts `commission-sdwire-zc706.py` and `flash-sdwire-zc706.py` are bounded
board-specific owners, not generic reset tools. They use the actual shared
board/storage leases, fixed verified JTAG identity, UART identity checks,
backup/readback and a hardware stop guard. They never write QSPI or persistent
U-Boot environment. After successful SD boot, the board is intentionally left
running the new image with SD Wire on DUT. This supersedes golden restoration
for this explicitly authorized standalone SD installation.

## Corrected image: automatic runtime PASS

The replacement image (expanded SHA256
`effe3ec9a450952cb57d917b790245bdf81025b7440ad823d9df951aae5305b8`)
was separately written and fully read back, then booted through SPL/U-Boot/
Linux with no JTAG PL load. No manual chmod or service-start command was used
on this boot. Automatic DDR initialization and three whole-1-GiB BIST passes,
both ADC receiver initializations/calibrations, SSH/DHCP and both PLLs PASS.
Both PLL `locked` statuses remained true over42.19 seconds of sampled status
observation; the 4,096-record bound was retained. SFP switch test:20/20 ICMP,
350/350 exact UDP, CRC/preamble/clock deltas all0; both PLLs remained locked.
This is finite startup/status qualification, not long-duration timing/jitter
or continuous ADC streaming qualification. Cold power removal was NOT_RUN;
SD BootROM startup was triggered by PS system reset through JTAG.

The board intentionally retains this corrected image and continuous PLL
service, management IP192.168.2.21, PL IP192.168.2.206, SD Wire on DUT.
Stop the service and perform orderly shutdown/verified hardware stop before
any further HOST selection. Current UART CP2103 USB1-1.3 was positively verified
as ZC706 by hostname and correlated boot, resolving the older PM12 assignment
for this current cabling. The obsolete Spartan CP2103 lock did not indicate
an open UART (its holder was an unrelated network viewer); no owner was stopped
or preempted. Actual ZC706/PM12 leases and tty-open checks covered UART access.

Evidence: `reports/storage/zc706-sdwire-boot-mode-fix-20261027` and
`reports/storage/zc706-sdwire-autostart-20261027`. Raw per-block JTAG evidence
archives and hashes are recorded there; private SD/MTP backups stay outside
Git. `qualify-zc706-sd-service.py` provides the bounded leased status/network
qualification using the existing ZC706 network probe.
