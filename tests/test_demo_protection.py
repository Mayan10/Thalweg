"""The protection layer as the live stream runs it."""

from __future__ import annotations

import numpy as np
import pytest

from thalweg.demo import DecisionRecord
from thalweg.demo.protection import LiveProtection, nominal_demand_mbps
from thalweg.eval.protection import run_policy
from thalweg.eval.workload import ARCHETYPES, WorkloadSpec


def _series(n: int, seed: int = 3) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    bound = 136 + 25 * np.sin(np.arange(n) / 7) + rng.normal(0, 10, n)
    return bound, bound + rng.normal(9, 15, n)


def test_sized_against_the_link():
    live = LiveProtection.for_link(146.0, load=1.8)
    demand = nominal_demand_mbps() * live.workload.load_multiplier
    assert demand == pytest.approx(1.8 * 146.0)


def test_the_live_stream_is_the_evaluated_code():
    # The rates the screen shows for our policy are the rates run_policy
    # scores, slot for slot, on the same series and workload.
    bound, realised = _series(150)
    spec = WorkloadSpec(load_multiplier=2.0)
    live = LiveProtection(spec)
    shown = {}
    for t in range(bound.size):
        for row in live.step(t, bound[t], realised[t])["flows"]:
            shown[(t, row["flow_id"])] = row["ours_mbps"]

    records = run_policy("protected", bound, realised, spec).records
    for row in records.itertuples():
        assert shown[(row.slot, row.flow_id)] == pytest.approx(row.granted_mbps, abs=0.006)
    assert len(shown) == len(records)


def test_both_policies_see_the_same_flows_at_the_start():
    bound, realised = _series(1)
    snap = LiveProtection(WorkloadSpec(load_multiplier=2.0)).step(0, bound[0], realised[0])
    assert snap["flows"]
    assert all(row["baseline_state"] == "active" for row in snap["flows"])


def test_protection_beats_shedding_the_largest_under_congestion():
    bound, realised = _series(400)
    live = LiveProtection.for_link(float(realised.mean()), load=1.8)
    for t in range(bound.size):
        snap = live.step(t, bound[t], realised[t])
    assert snap["ours"]["critical_violation"] < snap["baseline"]["critical_violation"]
    assert [a["archetype"] for a in snap["archetypes"]] == [a.name for a in ARCHETYPES]


def test_decision_tables_keep_their_columns_without_it():
    record = DecisionRecord(
        step=0, timestamp="t", regime="global", predicted_mbps=1.0, bound_mbps=1.0,
        actual_mbps=1.0, offset_mbps=0.0, alpha=0.3, admitted=0, oracle=0,
        dropped=0, unused=0, risk_event=False, congested=False, realised_risk_rate=0.0)
    assert "protection" not in record.to_dict()
    record.protection = {"n_flows": 0}
    assert record.to_dict()["protection"] == {"n_flows": 0}
