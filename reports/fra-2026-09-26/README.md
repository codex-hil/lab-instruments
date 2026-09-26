# FRA commissioning record — 2026-09-26

**Proposed state: UNTRUSTED.** Software milestone complete; physical commissioning
remains OPEN ITEM. No physical loopback/RC pass or hardware error figures are claimed.

## Implementation and driver boundary

FRA is part of `lab-instruments` / `labinst fra`, not a second instrument stack.
The engine uses existing AWG `Driver.apply/off/identify` and a separately documented
MSO4104 waveform extension. CLI and HTTP GUI share configuration and engine. No SCPI
is in FRA. Core methods on existing AWG profiles remain unchanged. The new scope
acquisition methods are not yet commissioned on real hardware.

Source modules: `fra_math`, `fra_engine`, `fra_export`, `fra_validation`, `fra_cli`,
`fra_web`, `fra_gui`, `fra_simulation`, plus driver-side `scope_acquisition`.
[API and commands](../../docs/fra/README.md), [driver gap](../../docs/fra/driver-gap.md),
[physical procedure](../../docs/fra/commissioning.md).

## Automated and browser evidence

- **61 unittest tests PASS** (31 pre-existing and 30 new), using Python 3.12.3.
- Estimation: unity, attenuation, positive/negative phase, ±180° crossing, DC offsets,
  deterministic noise, non-bin-centered excitation, different channel time origins,
  complex averaging, sweep generation and unwrap gaps.
- Engine/error tests: low input, clipping, short/missing/nonfinite waveform, invalid
  sampling, timeout, STOP during operation, failed OFF, cleanup, configuration gates,
  actual quantized sampling and manual sampling. No hardware needed.
- Driver fixtures: one stopped record for both channels, voltage/time scaling,
  clipping rails, missing data, timeout/cancel, unsupported model rejection.
- HTTP: CSRF rejection, preset validation, concurrent job rejection, progressive
  updates, STOP, exports and persisted JSON.
- Firefox **147.0.3** headless browser: 18 controls populated, sweep, single point,
  STOP/cancel with cleanup confirmation and plotted result PASS. Simulation only.
  Browser test uses optional existing Firefox, not a runtime dependency.
- CLI zipapp: sweep and single-point simulation plus JSON/CSV/PNG/SVG exports PASS.
- Deterministic build/replay evidence is recorded in `reproduction.json` after clean
  committed-source replay. No pip/npm or undocumented host packages are needed.

`software.json`, `browser-smoke.json`, full structured `synthetic-*.json` and
analytical comparisons preserve the evidence. Full time-domain arrays are not
archived in M1, but each repeat's phasors and actual timing are retained.

## Numerical errors — SIMULATION ONLY

| Fixture | Max gain error | Max phase error | Cutoff |
|---|---:|---:|---|
| Unity loopback, 21 points, 4 averages | 0.000978 dB | 0.00345° | N/A |
| RC, 21 points, 4 averages | 0.000589 dB | 0.00415° | 1000.0723 Hz vs 1000 Hz; +0.007233% |

The RC software fixture uses R=1000 Ω and C=159.154943 nF for fc=1000 Hz.
These values describe the synthetic reference, **not physical components**.
Noise is deterministic and proportional to each signal; sample timing deliberately
uses 1.03× the requested rate. These tiny errors do not predict real bench accuracy.

## Actual hardware

Read-only identity queries succeeded:

- Tektronix AFG1062, serial 1544477, firmware 1.0.1, USBTMC.
- Tektronix MSO4104, serial C020817, firmware 2.68, TCP port 4000.

See `hardware-identification.json`. The user was asked for splitter/channel topology
and RC values/connections. Neither was confirmed during this task. The previous
single AWG→scope connection is not evidence of a two-channel loopback. No source
was enabled and no scope settings were changed for commissioning. Physical gain,
phase, cutoff and error-behavior results are **NOT RUN**, not zero and not PASS.

## OPEN ITEMs

1. Confirm two-channel loopback topology and commission the new MSO4104 acquisition
   methods, actual sampling, clipping/probe scaling, manual Fs and STOP on hardware.
2. Record independent loopback deviations over the chosen amplitude/frequency range.
3. Build/identify a passive RC fixture, record component values/tolerances/loading,
   compare gain, phase and cutoff quantitatively, verify physical error behavior.
4. No LIVE loop yet; SINGLE POINT is implemented. Coherence/SNR, adaptive settling,
   autoranging/input leveling, raw waveform archiving and device deskew remain future work.
5. Scope waveform capability is MSO4104 only. MSO2002B and other Tek series need
   separately verified semantic driver extensions. Raw shared HTTPS gateway source
   control remains rejected by the existing non-atomic-source constraint.
6. Host-local FRA locks do not exclude unrelated SCPI tools or remote hosts. Bench
   must have one owner during measurements. STOP is cooperative, not hard real-time.

No TRUSTED promotion is proposed before both physical comparisons, error tests and
review of reproducibility/fixture limits pass.

## Reproduce GUI browser smoke (optional)

```sh
./dist/labinst.pyz fra gui --simulate --port 8851
# In a second terminal, use a dedicated local profile:
mkdir -p local/firefox-test
printf '%s\n' 'user_pref("marionette.port", 2829);' > local/firefox-test/user.js
firefox --headless --no-remote --marionette --profile "$PWD/local/firefox-test"
# In a third terminal:
python3 scripts/fra-browser-smoke.py
```

The script refuses a hardware-mode GUI, checks browser behavior and saves a local
screenshot before closing that dedicated browser session. Firefox installation is
optional for this smoke; automated unittest and FRA runtime require only Python.

## Follow-up: small-signal amplitude controls

GUI amplitude is displayed in mVpp, with 10/20/50 mVpp and ×2/÷2 buttons; preset/API
values remain SI volts. Measured Vin/Vout are displayed in mVrms, separately from
source setpoint/readback. Changes apply to the next measurement and are locked
while running. `feedback-small-signal.json` starts at 10 mVpp and 5 mV/div.

63 regression tests PASS. Synthetic 100/10/1 mVpp checks recover proportional Vin
and unchanged H; browser conversion, preset round-trip and running-state lock PASS.
See `amplitude-update.json`. No physical small-signal test, automatic leveling or
inventory-limit change was performed. This adds manual convenience, not a new
claim of hardware minimum amplitude or feedback-loop commissioning.
