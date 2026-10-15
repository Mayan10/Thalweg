"""Figures for the SIGMETRICS 2027 submission.

The values are transcribed from the tables in this paper, which are themselves
generated from saved result files (results/summary/starnet-regime-grid.md and
the BG-CFQS sweep). Kept here, not in scripts/, because they are typeset for the
acmsmall column width and nothing else uses them.

Accessibility follows the SIGMETRICS 2027 call: Okabe-Ito colours, and every
series also differs by marker and line style so the figures read in monochrome.
"""

from pathlib import Path

import matplotlib.pyplot as plt

OUT = Path(__file__).parent / "figures"
OUT.mkdir(exist_ok=True)

# Okabe-Ito, the colour-blind-safe palette.
BLUE, ORANGE, GREEN, PURPLE, GREY = "#0072B2", "#E69F00", "#009E73", "#CC79A7", "#555555"

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": "#DDDDDD",
    "grid.linewidth": 0.6,
    "legend.frameon": False,
    "pdf.fonttype": 42,
})

BUDGETS = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35]


def target_line(ax):
    ax.plot([0.04, 0.36], [0.04, 0.36], color=GREY, linestyle=(0, (4, 3)),
            linewidth=1, label="achieved = requested")


def floor():
    # Section 4.2 table: BG-CFQS achieved OverRate across the budget sweep.
    series = [
        ("Chicago", [0.165, 0.165, 0.165, 0.209, 0.267, 0.322, 0.378], BLUE, "o", "-"),
        ("Osnabruck (StarNet)", [0.127, 0.127, 0.127, 0.169, 0.213, 0.251, 0.295], ORANGE, "s", "--"),
        ("Victoria", [0.070, 0.070, 0.070, 0.092, 0.120, 0.159, 0.194], GREEN, "^", "-."),
        ("Osnabruck (WetLinks)", [0.185, 0.185, 0.185, 0.244, 0.297, 0.349, 0.405], PURPLE, "D", ":"),
    ]
    fig, ax = plt.subplots(figsize=(5.4, 2.7))
    ax.axvspan(0.04, 0.155, facecolor="#F2F2F2", hatch="///", edgecolor="#D0D0D0", linewidth=0)
    ax.text(0.097, 0.405, "budget floor\n(one quantile)", ha="center", va="top", fontsize=8)
    target_line(ax)
    for name, ys, colour, marker, style in series:
        ax.plot(BUDGETS, ys, color=colour, marker=marker, linestyle=style,
                linewidth=1.4, markersize=4.5, label=name)
    ax.set_xlim(0.04, 0.36)
    ax.set_ylim(0.04, 0.42)
    ax.set_xlabel("requested risk budget $\\varepsilon$")
    ax.set_ylabel("achieved OverRate")
    ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "bgcfqs-floor.pdf")
    plt.close(fig)


def tracking():
    # Section 5.2 table: budget tracking, mean of the three StarNet locations.
    online = [0.050, 0.100, 0.150, 0.200, 0.250, 0.300, 0.350]
    static = [0.040, 0.080, 0.120, 0.160, 0.204, 0.248, 0.293]
    fig, ax = plt.subplots(figsize=(4.2, 2.6))
    target_line(ax)
    ax.plot(BUDGETS, online, color=BLUE, marker="o", linewidth=1.6, markersize=4.5,
            label="online recalibration")
    ax.plot(BUDGETS, static, color=ORANGE, marker="s", linestyle="--", linewidth=1.6,
            markersize=4.5, label="static split conformal")
    ax.set_xlim(0.04, 0.36)
    ax.set_ylim(0.03, 0.37)
    ax.set_xlabel("requested risk budget $\\varepsilon$")
    ax.set_ylabel("achieved OverRate")
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "budget-tracking.pdf")
    plt.close(fig)


def regimes():
    # Section 5.3: P10 OverRate against regime count, online calibration, budget 0.35.
    points = [(1, 0.6663, "none"), (4, 0.6733, "level"),
              (18, 0.6931, "all geometry"), (51, 0.7085, "all four axes")]
    fig, ax = plt.subplots(figsize=(4.2, 2.4))
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    ax.plot(xs, ys, color=BLUE, marker="o", linewidth=1.4, markersize=5)
    for x, y, name in points:
        ax.annotate(name, (x, y), textcoords="offset points", xytext=(6, -10), fontsize=8)
    ax.set_xscale("log")
    ax.set_xticks(xs)
    ax.set_xticklabels([str(x) for x in xs])
    ax.set_xlim(0.8, 90)
    ax.set_ylim(0.655, 0.72)
    ax.set_xlabel("number of regimes (log scale)")
    ax.set_ylabel("P10 OverRate")
    fig.tight_layout()
    fig.savefig(OUT / "regime-count.pdf")
    plt.close(fig)


if __name__ == "__main__":
    floor()
    tracking()
    regimes()
