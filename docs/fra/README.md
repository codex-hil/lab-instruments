# FRA / Bode capability — Milestone 1

**Trust state: UNTRUSTED.** Numerical, fixture and HTTP tests are independent of
physical commissioning. [Current report](../../reports/fra-2026-09-26/README.md).
Existing project name/CLI is `labinst` (`labinstruments` Python), not a separate
`labtools` installation. Everything builds into the same dependency-free zipapp.

## Existing APIs inspected before implementation

| Existing component | API and finding |
|---|---|
| `Driver` | `identify()`, `apply(params, limits)`, `off()`, `read(operation, channel)` |
| AWG profiles | `afg1062`, `mp750288`; sinus frequency, Vpp, offset, channel, enable; `apply` returns semantic `state` plus raw readback and begins by turning all channels OFF |
| Scope profiles | `mso4104`, `mso2002b`; originally only immediate frequency/Vpp, **no scaled waveform acquisition API** |
| `Transport` | TCP, Linux USBTMC, HTTPS USB gateway; binary blocks already supported |
| Inventory | Existing `devices` JSON, serial identity, transport, limits and commissioning flag |
| Build / results | Python 3.11+ stdlib, deterministic zipapp, unittest; existing HIL JSON evidence but no general experiment schema |

The missing scope capability is documented separately in [driver-gap.md](driver-gap.md).
Added semantic methods on the existing Driver, with instrument commands isolated in
`scope_acquisition.py`. FRA modules have no SCPI and do not use Transport directly
for commands; InstrumentSession opens the existing driver/transport objects.
No existing AWG programming behavior or policy has been weakened.

## Architecture

```text
CLI / Python caller / Web API ← HTML GUI
                   ↓
                FRAEngine
         planner → acquisition policy
                   ↓
      existing Driver.apply / configure_acquisition / acquire_waveforms
                   ↓
        actual time-scaled input/output samples
                   ↓
   complex estimator → result → JSON / CSV / SVG / PNG
```

Modules are small independent files: `fra_math` (planning/estimation), `fra_engine`
(orchestration/config/result), `fra_export`, `fra_validation` (analytical comparison),
`fra_cli`, `fra_web`, `fra_gui`; `fra_simulation` is an explicitly labeled software
fixture. The GUI never addresses a driver. There is no additional device-control
server requirement. FRA uses per-instrument local file locks against other FRA
processes; unrelated direct SCPI clients are not covered. Reserve the bench manually
and run one controller per device. No distributed reservation framework was added.

## Build and run without hardware

```sh
./scripts/bootstrap.sh
./dist/labinst.pyz fra sweep --simulate --preset examples/fra/rc.json \
  --output local/fra-demo.json --csv local/fra-demo.csv \
  --png local/fra-demo.png --svg local/fra-demo.svg
./dist/labinst.pyz fra measure --simulate --frequency 10kHz
./dist/labinst.pyz fra gui --simulate
```

GUI: `http://127.0.0.1:8850`. No pip, npm, CDN, font download or external runtime
assets. stdlib HTTP server matches the existing repository dependency policy;
FastAPI would add dependencies without a requirement here. The GUI is loopback-only;
use an SSH tunnel to the lab host for another computer/tablet. POST requires a
session token and JSON; Host checking rejects rebinding, no CORS allowance.

## Run on instruments

1. Confirm topology: AWG → DUT input; scope input channel measures actual DUT input,
   output channel measures DUT output. Both channels must be on the same MSO4104.
2. Copy `examples/lab.json` to an ignored local file. Keep correct device names,
   addresses, expected serials and source limits. Approve the actual safe fixture,
   then set the AWG's existing `commissioned` and `limits.allow_output` flags true.
   The FRA never silently overrides these flags. No need to commission unrelated
   instruments in that inventory.
3. Confirm scope probe factors, suitable cables, load impedance and voltage range.
   Driver selects DC coupling and 1 MΩ termination, zero offset/position. Volts/div
   is explicit (`--volts-per-div`); M1 has no auto vertical ranging or input leveling.
4. Use CLI or the same preset through GUI:

```sh
./dist/labinst.pyz fra sweep --config local/bench.json \
  --source tek_awg:ch1 --input scope:ch1 --response scope:ch2 \
  --start 100Hz --stop 100kHz --points-per-decade 20 \
  --amplitude 100mV --averages 4 --cycles 16 --settling-cycles 5 \
  --output local/loopback.json --csv local/loopback.csv --png local/loopback.png
./dist/labinst.pyz fra measure --config local/bench.json \
  --frequency 10kHz --amplitude 100mV --output local/point.json
./dist/labinst.pyz fra gui --config local/bench.json --preset examples/fra/loopback.json
```

`--response` is the output **scope channel**; `--output` is the result filename.
Amplitude is programmed AWG **Vpp**, not RMS and not necessarily the unloaded DUT
voltage (50 Ω vs high-impedance calibration matters). The transfer function never
uses this nominal amplitude: both input and output phasors come from scope records.
CLI supports SI prefixes and Hz/V/Vpp/Sa/s. JSON presets use numerical SI values.

`--points N` and `--points-per-decade N` are alternative CLI options. In a preset,
`points: null` selects points-per-decade; a number takes precedence. Log is default.
For linear spacing, points-per-decade determines total count from endpoint ratio,
then those points are spaced linearly; specifying `points` is clearer in this case.
SINGLE POINT uses one selected frequency. LIVE is an **OPEN ITEM**; repeated
single-point calls are possible, but no continuous unattended LIVE loop is supplied.

## Defaults, acquisition and estimator

Defaults are in `FRAConfig`, shared by CLI/API/GUI: 10 Hz–100 kHz, log, 20 points per
decade, 0.1 Vpp, 4 averages, 16 cycles/record, 5 settling cycles, minimum settling
50 ms, AUTO sample rate, 50 samples/cycle, minimum Vin 10 µVrms, 50 mV/div, 10 s
acquisition timeout. All are serializable preset fields; advanced options appear
in the GUI. `--sample-rate auto` or a numeric sample rate requests AUTO/manual.

Acquisition planner requests duration = cycles/f and Fs = samples-per-cycle × f.
MSO4104 quantizes records to 1000/10000/100000 samples (larger ones rejected).
AUTO configures record length/timebase, reads back actual length and rate; manual
also requests the sample rate, still using actual waveform preamble timing.
One stopped single-sequence sample acquisition supplies both channels, not two
independently running traces. Actual XINCR/XZERO/PT_OFF and Y scaling are read per
channel/per repeat; no sample timing is inferred from requested settings.

Records require >=32 samples, >=2 cycles and >=8 samples/cycle. AUTO additionally
requires at least 95% of the requested samples/cycle and record cycles. Quantization
outside those bounds is an error; the engine does not silently calculate aliased
points. Automatic retry/retuning is an OPEN ITEM. The bounded record size avoids
unnecessarily huge captures at high frequency. Driver calls have transport timeouts;
STOP latency can include a complete in-flight driver configuration operation and
subsequent OFF checks; it is not a hard real-time emergency stop.

At the source frequency read back by the AWG driver, fit `a*cos(ωt)+b*sin(ωt)+DC`.
The phasor is `a - j*b`. This is synchronous detection with a 3×3 Gram correction
for nonorthogonal finite records; a direct raw DFT sum would have leakage bias for
noninteger cycles. No FFT-bin alignment is needed. `H = Xout/Xin`; each repeat gives
one complex H, and those H values are averaged. Report `20 log10(abs(mean(H)))`,
wrapped phase in **[-180,180)** and fundamental RMS (peak phasor magnitude / √2).
These RMS values are the fitted fundamental, not broadband waveform RMS.

Dispersion is sample standard deviation of per-repeat gain and circular phase
deviations around the mean phase; with one repeat the stored std is 0 (no measured
dispersion). Near-total cancellation of mean H is invalid. Raw phase remains wrapped;
plots/CSV optionally unwrap continuous valid segments, restarting across bad points.

## Result, errors and STOP

`labinst.fra.v1` JSON is authoritative: package version, Python version, digest of
package source (also inside zipapp), UTC timestamps, config, identities, source
settings/readback, requested/actual scope settings, acquisition preambles, each
repeat's complex H and Vin/Vout phasors, dispersion, point statuses and cleanup.
Full time-domain arrays are processed but not retained in M1; phasors and timing
metadata are retained. A raw waveform archive is an OPEN ITEM for deeper diagnosis.

Bad points have null gain/phase, never NaN/Infinity or a plausible substitute.
Statuses include `clipping`, `low_input`, `low_output`, `unstable`,
`acquisition_error`. Any failed repeat invalidates the point. Clipping/low signal
can continue to the next frequency; acquisition/transport errors end the sweep to
avoid continuing a desynchronized instrument session. Signed 8-bit rail values
provide obvious clipping detection, not proof that the DUT itself is undistorted.
Harmonics, coherence/SNR and adaptive rejection are OPEN ITEMs.

On completion, error or STOP: attempt AWG OFF (all channels) and scope STOP
independently, record confirmation/errors. No restoration of old active outputs.
Configured scope settings remain in place; source parameters remain at last setting
with output OFF. Failure to confirm shutdown is **cleanup_error**, visibly reported.
A software process cannot guarantee de-energizing equipment if its cable is removed
or the host loses power. A transport failure is not proof of output OFF.

GUI saves every finished/cancelled job JSON to `local/fra/<uuid>.json` by default
(`--results-dir` override), with download links for all exports. It uses progressive
status polling, displays current frequency, latest point, progress, actual rate and
record length. Preset import/export uses the same `FRAConfig` JSON as CLI `--preset`
and `--save-preset`. PNG/SVG are derived views, never the source of measurement data.

## Structured API

Python: `FRAEngine(session_factory).run(FRAConfig.from_dict(preset), cancel_event,
notify_callback)`; `InstrumentSession(inventory, config)` opens existing instruments.
Events: started, identified, progress, point, finished. Inject a semantic fixture for
tests without hardware. Normal CLI exit code 0 requires completed valid sweep;
invalid/cancelled/cleanup-error results exit 2, retaining JSON evidence.

Local HTTP:

| Endpoint | Meaning |
|---|---|
| `GET /api/config` | Default shared preset |
| `GET /api/mode` | Explicit hardware/simulation selection, without touching hardware |
| `POST /api/validate` | Validate preset, no hardware |
| `POST /api/start` | Start one sweep or single point; reject another concurrent job |
| `POST /api/stop` | Request cancellation; poll until cleanup result |
| `GET /api/status` | Job status, progress, progressive result |
| `GET /api/export/{json,csv,png,svg}` | Current result/export |

POST body is preset JSON (STOP uses `{}`), header `X-FRA-Token` is the local server
session token embedded in the served page (`server.api_token` for in-process tests).
External autonomous tools should normally use CLI/Python. API does not accept paths,
host addresses or raw commands: inventory is fixed when the GUI service starts.

## Tests and commissioning

```sh
python3 -m unittest discover -s tests -v
./scripts/bootstrap.sh
./scripts/replay.sh HEAD
./dist/labinst.pyz fra export local/loopback.json --output local/loopback.svg
./dist/labinst.pyz fra compare local/loopback.json --kind loopback
./dist/labinst.pyz fra compare local/rc.json --kind rc \
  --resistance 1000 --capacitance 1e-7 --output local/rc-comparison.json
```

[Commissioning procedure](commissioning.md) records fixture identity, error budgets,
component values, loading assumptions, failures and reproduction. `compare` produces
numerical errors and an interpolated -3.0103 dB cutoff for RC. Its PASS is only a
comparison result, never automatic TRUSTED promotion. Simulations remain labeled.

## Small-signal amplitude adjustment

The GUI displays AWG amplitude in **mVpp**, vertical scale in **mV/div**, and minimum
input threshold / measured Vin/Vout in **mVrms**. Quick amplitude buttons provide
10/20/50 mVpp and ×2/÷2. These edit the next measurement's preset only; all controls
are locked while running. STOP, adjust, then SINGLE POINT or START to apply the new
value. The GUI shows programmed amplitude and driver readback separately from
measured Vin; neither source value substitutes for acquired Vin in H.

The shared API/preset stays in SI units: `amplitude: 0.01` means 10 mVpp, not 10 Vpp.
CLI already accepts `--amplitude 10mV` or `10mVpp`. The same inventory limits and
strict readback validation apply; no automatic clamp, lower-limit override or
silent change of amplitude is introduced. Bench example inventories currently have
`vpp_min: 0.01`; this is policy, not a claim about hardware minimum or resolution.
Readback mismatch due to hardware rounding is still a rejected measurement.

```sh
./dist/labinst.pyz fra measure --simulate --frequency 1kHz \
  --amplitude 10mV --volts-per-div 2mV --output local/small-signal.json
./dist/labinst.pyz fra gui --simulate --preset examples/fra/feedback-small-signal.json
```

`feedback-small-signal.json` is a 10 mVpp / 5 mV-per-division starting preset, not a
validated feedback-loop fixture. Required injected amplitude depends on the DUT,
injection network and loading; confirm actual Vin. Smaller amplitudes may require
an appropriate attenuator/injection network and sufficient measurement sensitivity.
Automatic Vin leveling is not implemented; it would need an explicit upper bound
and separate validation, particularly if the measured input disappears.
