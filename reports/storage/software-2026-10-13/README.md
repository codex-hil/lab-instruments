# Storage software validation — 2026-10-13

**121 tests PASS**, including 41 storage tests, in pinned Nix environment.
Storage tests are **SIMULATED**, including synthetic factory FT200X topology,
unknown factory ownership, missing/wrong hub or reader, safe inventory proposal,
OFF gate, subprocess locking/SIGINT/SIGKILL, bmaptool and mocked boot/UART.

[report.json](report.json) includes CLI outcomes, source hashes and read-only USB
discovery of actual `DP04I355`. Presence of hardware in discovery is not a
physical mux test. [software-tests.log](software-tests.log) has all test outcomes;
[zynq-simulated](zynq-simulated/result.json) remains explicitly SIMULATED.

[Physical inventory report](../hardware-2026-10-13/README.md) is separate and
records identity PASS plus permission blockers. Neither report claims switching,
writing, EEPROM provisioning or Zynq boot was tested.

Reproduce into a new directory:

```sh
nix --extra-experimental-features 'nix-command flakes' develop path:. --command \
  python3 scripts/validate-storage.py --output local/storage-replay
```
