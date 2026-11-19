# USB-TSMC2 / MP750288 cross-thread access

Read README.md here before using the host or AWG. Reuse the existing Driver and
Transport; do not create another device driver or credential store in Git.
Expected AWG serial 1944201, Pi serial 7379fa4619d5d5f0. IP is only a hint.
On Optiplex acquire both shared flocks, sorted, nonblocking, for the entire operation:
- ~/.cache/instrument-mp750288-1944201.lock
- ~/.cache/rpi-7379fa4619d5d5f0.lock
Hold through cleanup; release partial acquisitions if busy. Do not remove locks.
The check_access.py helper acquires these itself; do not nest it under the same locks.
Credentials reside only in ~/.config/labinst/usb-tsmc2/. Never print or commit tokens.
Check model/serial before commands. No automatic output enable/reset on connect.
The September analog wiring map is historical, not revalidated after the Pi5 move.
Active experiments require confirmed wiring and task-specific limits; gateway has
no output watchdog and does not enforce commissioned:false from client examples.
