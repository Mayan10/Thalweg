#!/usr/bin/env python3
"""A live, one-screen demonstration of the protection layer.

Two flows share a link whose calibrated bound is 20 Mbps: a radiology study
pushed against a reporting deadline, which does not declare itself as critical,
and a nightly cloud backup. Each row is one decision. Nothing about either flow
changes between rows except the deadline slack, so whatever moves is the
scorer reading that evidence.

Two policies divide the same bound on the same slot:

  ours      criticality-weighted max-min fairness with protected floors
  largest   throttle the heaviest flow first, what a rate-based shaper does

The flows are a model, as everywhere in the protection evaluation. This script
shows the mechanism; the measured result is `scripts/run_protection.py`.

    python scripts/demo_protection.py
    python scripts/demo_protection.py --bound 12   # floors no longer all fit
"""

from __future__ import annotations

import argparse

from thalweg.decide.flows import FlowClass, FlowObservation, FlowSpec
from thalweg.decide.protect import FlowDemand, ProtectionController, allocate_shed_largest

IMAGING = FlowSpec("pacs-7", declared=FlowClass.STANDARD,
                   floor_mbps=15.0, demand_mbps=28.0, bytes_total_mbit=4200.0,
                   deadline_s=900.0, resumable=False)
BACKUP = FlowSpec("backup-2", declared=FlowClass.BACKGROUND,
                  demand_mbps=22.0, recurrence=0.95)

# Starts well clear of the deadline so the first rows show the imaging study
# unprotected, then closes in until it crosses the threshold.
SLACKS_S = (900.0, 750.0, 600.0, 450.0, 300.0, 200.0, 120.0, 60.0)


def observe(slack_s: float) -> dict:
    remaining = 2_600.0
    return {
        # Inelastic: still asking for its peak after being throttled.
        "pacs-7": (IMAGING, FlowObservation(
            demand_mbps=28.0, demand_peak_mbps=28.0, throttled_last=True,
            granted_last_mbps=9.0, mbit_up=45.0, packets_up=4_000,
            remaining_mbit=remaining, deadline_remaining_s=slack_s,
            progress=1.0 - remaining / IMAGING.bytes_total_mbit)),
        # Elastic: its offered load has fallen to what it was given.
        "backup-2": (BACKUP, FlowObservation(
            demand_mbps=6.0, demand_peak_mbps=22.0, throttled_last=True,
            granted_last_mbps=6.0, mbit_up=30.0, packets_up=2_600)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bound", type=float, default=20.0,
                        help="calibrated bound in Mbps, what the link is trusted to carry")
    args = parser.parse_args()

    controller = ProtectionController.build()
    scorer = controller.scorer
    print(f"calibrated bound {args.bound:.0f} Mbps, imaging floor "
          f"{IMAGING.floor_mbps:.0f} Mbps, protection threshold "
          f"{scorer.config.protect_threshold:.2f}\n")
    print(f"{'slack':>6}  {'imaging crit':>12}  {'protected':>9}  "
          f"{'ours: imaging / backup':>23}  {'largest: imaging / backup':>26}")

    for slack in SLACKS_S:
        allocation = controller.step(bound_mbps=args.bound, observations=observe(slack))
        # The baseline sees the same demands on the same slot.
        demands = [FlowDemand(fid, demand_mbps=obs.demand_mbps)
                   for fid, (_, obs) in observe(slack).items()]
        largest = allocate_shed_largest(args.bound, demands).rates

        ours = allocation.rates
        flag = "yes" if scorer.is_protected("pacs-7") else "no"
        print(f"{slack:5.0f}s  {scorer.criticality('pacs-7'):12.3f}  {flag:>9}  "
              f"{ours['pacs-7']:10.2f} / {ours['backup-2']:<10.2f}  "
              f"{largest['pacs-7']:12.2f} / {largest['backup-2']:<10.2f}")

    print(f"\nfloor breached under ours: {allocation.protection_breached}")
    print("The backup is throttled, never stopped: every weight is strictly positive.")


if __name__ == "__main__":
    main()
