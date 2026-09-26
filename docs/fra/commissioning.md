# FRA commissioning procedure

Start UNTRUSTED. During a documented physical test campaign use VALIDATING in the
commissioning record; individual software results conservatively stay UNTRUSTED.
TRUSTED is a proposed reviewed state, never a flag set by the GUI or comparison CLI.

## Software prerequisite

Run bootstrap (all regression tests) from a clean clone/commit. Replay the build
and retain commit, Python version and zipapp hash. Run the RC simulation, export
JSON/CSV/PNG/SVG and compare against its known analytical transfer. Exercise invalid
settings, low Vin, clipping, missing samples, timeout, STOP and failed OFF using
fixtures before deliberate physical fault tests. Record these separately from HIL.

## Loopback

Confirm two-channel wiring: AWG selected output through suitable splitter/tee to
both scope channels, proper common grounds, matched cables and correct probe
attenuation. Use 1 MΩ scope termination as selected by M1; account for AWG load
calibration. No unknown DUT remains connected. Record cable/splitter identities,
channels, instrument serials/firmware and amplitude before enabling the local source
inventory flags. Do not infer loopback from two similar-looking noise traces.

Start at 1 kHz / 100 mV programmed Vpp, appropriate vertical scale. Verify Vin/Vout,
absence of clipping and physical output OFF after the single point. Then sweep
100 Hz–100 kHz (or another documented hardware-compatible range). Save structured
result and run `fra compare --kind loopback`. Default provisional acceptance is
max |gain error| <=0.5 dB, max |wrapped phase error| <=5°. Record actual max/RMS
errors, frequency dependence and dispersion. Choose the required error budget
before testing; thresholds are fixture requirements, not instrument specifications.

Also physically verify STOP mid-sweep and low-input/clipping reporting using a
safe low-voltage fixture. Communication interruption needs an independent check
of actual source state; reported cleanup failure must not be counted as OFF.

## Passive RC

Record measured/nominal R in ohms, C in farads, tolerances, wiring, probe/cable
capacitance and scope loading. Example: R=1 kΩ, C=100 nF, expected fc≈1591.55 Hz.
These are proposed fixture values, **not installed hardware evidence**.
AWG drives resistor input, scope CH1 measures that actual input; capacitor and CH2
are at resistor output to ground. Ideal H=1/(1+jωRC) assumes negligible scope load
relative to R and capacitance small relative to C; quantify corrections otherwise.

Sweep at least 0.1 fc–10 fc with enough points around fc, export JSON, run
`fra compare --kind rc --resistance R --capacitance C`. Comparison reports magnitude
and circular phase residuals at each frequency, max/RMS residuals and log-frequency
interpolation of the -3.0103 dB crossing. Require coverage on both sides; do not
extrapolate a missing cutoff. The default cutoff error bound is 5%; adjust `--cutoff-tolerance-percent`,
`--gain-tolerance-db` and `--phase-tolerance-deg` to a predeclared budget accounting
for component uncertainty. Never relax acceptance solely to turn a failure into PASS.

## Acceptance record

Store software evidence, physical loopback JSON + comparison, physical RC JSON +
comparison + component values, independent OFF/error evidence, topology and exact
code/environment identity. No physical result may be substituted by simulation.
Only after synthetic tests, both physical comparisons, error behavior and clean
reproduction pass can review propose TRUSTED. Calibration/accuracy scope must be
limited to actually tested devices, firmware, amplitudes, frequency range and
fixture. Coherence, harmonics, source impedance and DUT nonlinearity need further
validation before more demanding PSRR/impedance/loop-gain applications.
