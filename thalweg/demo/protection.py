"""The protection layer on the live stream, beside the policy it argues against.

Every decision the demo engine emits carries a calibrated bound and, once the
horizon has elapsed, the throughput the link actually carried. This module
hands both to two copies of the protection harness, one per policy, and reports
what each did with the same bound on the same slot:

  ours       criticality-weighted max-min fairness with protected floors
  baseline   throttle the largest flow first, what a rate-based shaper does

Both are `eval.protection.PolicyStepper`, the code `run_policy` evaluates, not
a copy of it. Built from the same workload seed they see identical arrivals, so
a flow that gave up under one policy and finished under the other is the same
flow treated two ways.

**The capacity is the pipeline's and the flows are a model**, exactly as in
`scripts/run_protection.py`. No public LEO dataset carries a flow table, so the
flows contending for the bound come from `eval/workload.py`. Each decision is
one workload slot of `WorkloadSpec.seconds_per_slot` seconds, so at the demo's
one decision per second the flows run several times faster than wall clock.

The `must_keep` field on each flow is the workload's stipulated label. The
scorer never sees it; it is sent so the screen can show whether the scorer's
protection decision agrees with it, and it is what the violation rates count.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from thalweg.eval.protection import PolicyStepper, SlotStep
from thalweg.eval.workload import ARCHETYPES, WorkloadSpec

OURS = "protected"
BASELINE = "shed_largest"


def nominal_demand_mbps() -> float:
    """Unconstrained demand of the workload at a load multiplier of 1."""
    return sum(a.concurrency * a.nominal_mbps for a in ARCHETYPES)


@dataclass
class _Tally:
    """Running counts for one policy since the stream started."""

    critical_slots: int = 0
    critical_below_allocated: int = 0
    critical_below_delivered: int = 0
    critical_gave_up: int = 0
    ordinary_gave_up: int = 0
    seen_completed: int = 0
    #: Flows that have left this policy's workload, and how.
    fate: dict[str, str] = field(default_factory=dict)

    def update(self, stepper: PolicyStepper, slot: SlotStep) -> None:
        for flow in slot.flows:
            spec, _ = slot.observations[flow.flow_id]
            if not spec.truly_critical or flow.floor_mbps <= 0:
                continue
            self.critical_slots += 1
            if slot.result.rates.get(flow.flow_id, 0.0) < flow.floor_mbps - 1e-9:
                self.critical_below_allocated += 1
            if slot.delivered.get(flow.flow_id, 0.0) < flow.floor_mbps - 1e-9:
                self.critical_below_delivered += 1

        # Only the flows that finished since the last slot, so the cost does not
        # grow with the length of the stream.
        completed = stepper.workload.completed
        for done in completed[self.seen_completed:]:
            self.fate[done.spec.flow_id] = "gave_up" if done.abandoned else "done"
            if done.abandoned:
                if done.spec.truly_critical:
                    self.critical_gave_up += 1
                else:
                    self.ordinary_gave_up += 1
        self.seen_completed = len(completed)

    def to_dict(self) -> dict:
        def rate(k: int) -> float | None:
            return round(k / self.critical_slots, 4) if self.critical_slots else None

        return {
            "critical_violation": rate(self.critical_below_allocated),
            "critical_violation_delivered": rate(self.critical_below_delivered),
            "critical_slots": self.critical_slots,
            "critical_gave_up": self.critical_gave_up,
            "ordinary_gave_up": self.ordinary_gave_up,
        }


@dataclass
class LiveProtection:
    """Two policies dividing the same bound, one decision at a time."""

    workload: WorkloadSpec = field(default_factory=WorkloadSpec)

    def __post_init__(self) -> None:
        self.ours = PolicyStepper(OURS, self.workload)
        self.baseline = PolicyStepper(BASELINE, self.workload)
        self._tally = {OURS: _Tally(), BASELINE: _Tally()}

    @classmethod
    def for_link(cls, mean_delivered_mbps: float, load: float = 1.8,
                 seed: int = 1337) -> LiveProtection:
        """Size the workload so unconstrained demand is `load` times what the
        link delivers on average.

        The links differ by half again in capacity, so a fixed multiplier
        leaves one comfortably under capacity and another far over it (the
        README's Phase 9b note). 1.8 is the point every committed comparison
        is quoted at.
        """
        multiplier = load * mean_delivered_mbps / nominal_demand_mbps()
        return cls(WorkloadSpec(seed=seed, load_multiplier=multiplier))

    def step(self, t: int, bound_mbps: float, realised_mbps: float) -> dict:
        ours = self.ours.step(t, bound_mbps, realised_mbps)
        baseline = self.baseline.step(t, bound_mbps, realised_mbps)
        if ours is not None:
            self._tally[OURS].update(self.ours, ours)
        if baseline is not None:
            self._tally[BASELINE].update(self.baseline, baseline)

        baseline_rates = baseline.result.rates if baseline is not None else {}
        baseline_fate = self._tally[BASELINE].fate
        rows = []
        if ours is not None:
            for flow in ours.flows:
                spec, obs = ours.observations[flow.flow_id]
                if flow.flow_id in baseline_rates:
                    other, other_state = baseline_rates[flow.flow_id], "active"
                else:
                    other, other_state = None, baseline_fate.get(flow.flow_id, "absent")
                deadline = obs.deadline_remaining_s
                rows.append({
                    "nominal_mbps": spec.demand_mbps,
                    "flow_id": flow.flow_id,
                    "archetype": flow.flow_id.split("#")[0],
                    "declared": spec.declared.value,
                    "must_keep": bool(spec.truly_critical),
                    "criticality": round(flow.criticality, 3),
                    "protected": bool(flow.protected),
                    "demand_mbps": round(flow.demand_mbps, 2),
                    "floor_mbps": round(flow.floor_mbps, 2),
                    "ours_mbps": round(ours.result.rates.get(flow.flow_id, 0.0), 2),
                    "baseline_mbps": None if other is None else round(other, 2),
                    "baseline_state": other_state,
                    "deadline_s": round(deadline, 0) if math.isfinite(deadline) else None,
                })
        # Largest first, by the flow's nominal rate rather than its current
        # demand: the big flows are where the two policies disagree, and an
        # elastic flow's demand moves every slot, which would reshuffle the
        # table under the audience.
        rows.sort(key=lambda r: (-r["nominal_mbps"], r["flow_id"]))

        return {
            "n_flows": len(rows),
            "n_protected": sum(r["protected"] for r in rows),
            "breached": bool(ours.result.breached) if ours is not None else False,
            "offered_mbps": round(sum(r["demand_mbps"] for r in rows), 2),
            "seconds_per_slot": self.workload.seconds_per_slot,
            "ours": self._tally[OURS].to_dict(),
            "baseline": self._tally[BASELINE].to_dict(),
            "archetypes": _by_archetype(ours, baseline),
            "flows": rows,
        }


def _by_archetype(ours: SlotStep | None, baseline: SlotStep | None) -> list[dict]:
    """One row per archetype, in the workload's own order, critical ones first.

    The two policies' active sets differ once flows start giving up, so each
    side is summed over its own flows rather than matched flow by flow.
    """
    def side(slot: SlotStep | None, name: str) -> tuple[int, float, int]:
        if slot is None:
            return 0, 0.0, 0
        flows = [f for f in slot.flows if f.flow_id.split("#")[0] == name]
        rate = sum(slot.result.rates.get(f.flow_id, 0.0) for f in flows)
        below = sum(slot.result.rates.get(f.flow_id, 0.0) < f.floor_mbps - 1e-9
                    for f in flows if f.floor_mbps > 0)
        return len(flows), rate, below

    out = []
    for archetype in ARCHETYPES:
        mine = ([f for f in ours.flows if f.flow_id.split("#")[0] == archetype.name]
                if ours is not None else [])
        n_ours, ours_mbps, ours_below = side(ours, archetype.name)
        n_base, base_mbps, base_below = side(baseline, archetype.name)
        out.append({
            "archetype": archetype.name,
            "must_keep": archetype.truly_critical,
            "declared": archetype.declared.value,
            "n_ours": n_ours,
            "n_baseline": n_base,
            "n_protected": sum(f.protected for f in mine),
            "mean_criticality": (round(sum(f.criticality for f in mine) / len(mine), 3)
                                 if mine else None),
            "demand_mbps": round(sum(f.demand_mbps for f in mine), 2),
            "ours_mbps": round(ours_mbps, 2),
            "baseline_mbps": round(base_mbps, 2),
            "ours_below_floor": ours_below,
            "baseline_below_floor": base_below,
        })
    return out
