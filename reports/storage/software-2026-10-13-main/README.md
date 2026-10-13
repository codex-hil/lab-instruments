# Validation on current origin/main base — 2026-10-13

**83 tests PASS**, including all 41 storage tests, without skips in pinned Nix.
[report.json](report.json) includes exact source SHA256; [software-tests.log](software-tests.log)
has full results. Storage and Zynq/UART test cases here remain SIMULATED.

The storage commit was rebased onto origin/main `f31649a`, preserving neighboring
instrument changes and excluding unrelated Keithley feature commits. Hence the
suite differs from the historical 121-test feature-branch run.

Real, separately executed hardware evidence:
[PASS_READ_ONLY](../hardware-2026-10-13-read-pass/README.md).
