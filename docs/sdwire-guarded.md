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
