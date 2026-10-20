# Live demo runbook

Streams the forecaster, the risk calibration and the decision layer through a
terminal dashboard, one decision per second, on a synthetic trace that carries
the structure the model is supposed to find.

Every decision on the stream comes out of the real pipeline: StarNet forecast,
regime assignment, adaptive safe bound, admission control, congestion. The
`--mode` flag chooses only which trace is replayed. **Synthetic data is for
demonstration and is never reported as a result.**

## Before the room fills

Two terminals, and start terminal 1 at least two minutes early. The forecaster
trains at startup, which takes 20 to 60 seconds, and the dashboard's rolling
figures need about 30 decisions before they mean anything.

Use a wide terminal. The KPI row splits into six tiles and wants 120 columns or
more to stay readable.

### Terminal 1: the ML service

```bash
python -m pip install -e ".[api]"          # once
python -m thalweg.api.server --mode synthetic --port 8010
```

Wait for the log line saying the pipeline is ready, or check it:

```bash
curl -s localhost:8010/api/ml/status
```

`"model_loaded": true` means you are ready to present.

### Terminal 2: the dashboard

```bash
cd services/tui
cargo build --release                      # once, takes a few minutes
./target/release/thalweg
```

Press **`m`** for the ML dashboard and **`p`** for flow protection. Keys: `h`
home, `k` login, `m` dashboard, `p` flows, `/` command bar, `q` quit.

## What to point at, in order

**The three lines.** Grey is the throughput that actually arrived, blue is the
point forecast, the bold line is the calibrated safe bound. The bound tracks
the forecast but sits deliberately below it. That gap is the risk layer doing
its job, and it is not a constant: watch it widen when the link gets harder to
predict.

**The red strip under the chart.** One mark per slot where the bound promised
more than the link delivered. Those are the decisions the risk budget is
counted over. They should be present but sparse.

**RISK RATE against UNCALIBRATED.** The two tiles are measured on identical
decisions. The first is the calibrated bound, the second is what an
uncalibrated allocator committing to the raw forecast would have achieved.
Over a full replay these land near 0.36 and 0.46. The tile is green while the
rate sits inside the budget plus a small tolerance.

**DROPPED.** Sessions admitted that the link could not carry. Over a full
replay the calibrated policy averages 0.26 against 0.37 uncalibrated, a 29%
reduction, at 98.8% utilisation.

**CONGESTION.** Fires when the bound sits below the committed rate for a
sustained window. Not a separate model: it is a decision rule on the same
bound, which is why it costs almost nothing. Roughly 9 episodes per replay at
the default 200 Mbps commitment.

## The flow protection screen (`p`)

The question this screen answers: when the safe bound falls and something has
to give, which flow gets throttled. Each decision's bound is divided across a
set of flows twice, once by the protection layer (`decide/protect.py`) and once
by throttle-largest-first, which is what a rate-based shaper does. Both see the
same flows, generated from one seed, so every row compares two policies on one
flow.

**Say this first: the capacity is real and the flows are a model.** The bound
comes from the live pipeline. The flows come from `eval/workload.py`, because no
public LEO dataset records individual flows. The footer says so on screen. One
decision is one 5 s workload slot, so the flows run about five times faster than
the clock.

What to point at, in order:

1. **A radiology push (PACS) row.** It declares itself `standard`, because the
   uploader does not set DSCP, so DiffServ would not save it. Under ours it is
   `PROTECTED` and held at or above its 15.4 Mbps floor. In the THROTTLE LARGEST
   column the same flow often reads `0.0 under floor` or `GAVE UP`: it is one of
   the biggest flows on the link, so a shaper cuts it first.
2. **The two sparklines.** Critical flows under their floor on each slot, drawn
   on one scale. The right-hand one is the shaper.
3. **CRITICAL < FLOOR tiles, ours against largest.** Running fraction of
   critical flow-slots allocated below floor. `delivered` is the same figure
   after the link has had its say.
4. **Cloud backup and OS update rows.** Squeezed hard and marked `throttled`,
   but never zero. Nothing is halted while capacity remains.
5. **CRITICAL GAVE UP, with the ordinary count under it.** The note shows what
   ordinary flows pay, so the screen cannot be read as protection for free.

Numbers to quote, from a full replay of the real Canada stream at the default
`--flow-load 1.8`: critical floor violation **0.070 against 0.203**, and 48
against 181 critical transfers abandoned, with ordinary abandonment about equal
(506 against 495). The committed result in `results/summary/protection-canada.md`
is 0.065 against 0.218. **The first ten minutes on screen run hotter than this.**
The Canada test split opens on a stretch averaging about 98 Mbps against a 152
Mbps mean, so the link is short by more and the tiles read roughly 0.11 to 0.16
against 0.49 to 0.59, with `BREACHED` showing often. The gap is the point; do
not quote the live tiles as the result.

Expect two questions:

- *Why are video streams protected?* Because the scorer cannot tell an
  entertainment stream from a teleconsultation. They match on every channel it
  has. This is the layer's known failure (README, "The scorer cannot tell a
  video call from Netflix"), and it is on screen.
- *Why is nothing protected sometimes?* When the link is not short, nothing
  needs protecting and the deadline and elasticity channels have nothing to
  read. The layer stays idle until congestion makes it necessary.

`--flow-load` sets unconstrained flow demand as a multiple of the link's mean
throughput. 1.8 is where the committed comparisons are quoted; `0` turns the
layer off.

## Saying the honest thing about the numbers

Expect a panel to ask, so say it first:

- **The rate moves around early on.** A few hundred decisions is a small
  sample. At a budget of 0.35 the standard error over 300 decisions is about
  0.028, so a reading of 0.30 or 0.41 is ordinary. The claim that the layer
  tracks its budget to within a point is about the full test split of 13,530
  decisions, not about one minute of a live stream.
- **This is a replay, not a live terminal.** `ingest/live.py` raises. There is
  no dish.
- **Synthetic mode means the data is generated, not the pipeline.** The trace
  carries the 15 s scheduling period, the handover dip, elevation, distance,
  candidate count and weather; everything downstream of it is the real model.
  Nothing here is a reported result.

## If something goes wrong

| Symptom | Cause | Fix |
|---|---|---|
| Dashboard says CONNECTING | Service still training | Wait, check `curl -s localhost:8010/api/ml/status` |
| CONNECTION shows ERR | Nothing on port 8010 | Confirm terminal 1 is running and on the right port |
| RISK RATE shows a dash | Fewer than 30 decisions buffered | Wait half a minute |
| Tiles look cramped | Terminal too narrow | Widen to 120 columns or more |
| Want a different link | | `--location usa|canada|germany` |
| Want a different budget | | `--epsilon 0.2`, the dashboard reads it from the handshake |
| Want congestion more or less often | | `--commitment 220` or `--commitment 180` |

## Running against the recorded traces instead

If `data/starnet/` is populated, the same demo runs on real measurements:

```bash
python -m thalweg.api.server --mode real --location canada --port 8010
```

Training takes longer. Everything else is identical.
