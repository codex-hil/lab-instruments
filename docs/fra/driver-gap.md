# Driver capability gap — independent of FRA mathematics

Before FRA, the existing MSO4104 driver could read immediate frequency and Vpp;
Transport could return a binary waveform block, as proven in the earlier HIL report.
There was no semantic API for configuring record duration/sample rate or obtaining
simultaneous, scaled channel arrays. Reimplementing this inside FRA would duplicate
instrument logic, so it is a separate extension of the existing Driver.

Added methods:

- `configure_acquisition(channels, plan, volts_per_div)` → actual sample rate, record
  length, timebase and channel settings (including probe gain).
- `acquire_waveforms(timeout, cancel)` → channel-keyed dict with `values` in volts,
  `dt_s`, `t0_s`, preamble, record length, clipping indication.
- `stop_acquisition()` → defined stopped scope state.

Only `mso4104` is implemented, using the vendor's
[MSO4000/DPO4000 programmer manual 077024801](https://download.tek.com/manual/077024801web.pdf).
Existing `mso2002b` remains available for its former methods; FRA rejects it until
its waveform capability is independently implemented and commissioned.
Commands/IEEE block decoding are confined to `scope_acquisition.py` (driver layer).
No existing trusted method is changed to force an FRA test to pass.

The extension explicitly uses sample mode, DC coupling, 1 MΩ termination,
zero offset/position, one stopped sequence and signed 8-bit waveform transfer.
It preserves configured probe factor and records it. A real 1× BNC cable with a
scope mistakenly set to 10× is an operator configuration error that cannot be
inferred from samples alone. Confirm probe factors before loopback commissioning.

OPEN ITEM: physical validation of this new semantic capability (fresh acquisition,
actual timing, clipping rails, manual sample-rate behavior, probe scaling and STOP).
Previous binary-transfer HIL is useful evidence but does not validate the new
configuration/acquisition sequence or two-channel phase accuracy. The extension
and FRA are UNTRUSTED pending those tests. Mock tests check command placement,
shared-record behavior, scaling, timeout/cancel and malformed-block handling.
