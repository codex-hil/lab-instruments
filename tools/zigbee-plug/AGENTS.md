# Zigbee HIL plug

Read README.md before access. Canonical source lives here; deployed backend
is on debug station 2 at ~/zigbee-lan-investigation/scripts/plugctl.py.
From Optiplex use ~/.local/bin/hil-plug. Every thread must reserve with a unique
thread/purpose owner and use its returned token for reads and writes. Release
when finished. No automatic expiry or force takeover. Do not bypass leases via
MQTT or remove another owner's lease. Shared-account leases are cooperative,
not an authentication boundary. Keep tokens and Zigbee network keys out of Git.

Before power changes identify the connected load and ensure user authorization;
no computer mapping is established. Preserve owning station and lease directory.
Never use this plug to cut power to its own control infrastructure.
No automatic power-cycle/watchdog is implemented or validated. A broker ACK is
not physical confirmation. Measurement field freshness remains unknown.

Run python3 -m unittest discover -s tools/zigbee-plug/tests from repo root.
Routine code tests must not switch real power. Physical OFF was user-confirmed
by audible click on 2026-10-30; OFF-to-ON and load operation remain unverified.
