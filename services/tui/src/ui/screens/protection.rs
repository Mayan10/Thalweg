//! Flow Protection: which flow gets throttled when the safe bound falls.
//!
//! Every decision on the stream divides its calibrated bound across a
//! modelled flow workload twice, once under the protection layer and once
//! under throttle-largest-first, which is what a rate-based shaper does. The
//! two see identical flows. This screen shows both side by side.
//!
//! The capacity comes from the live pipeline. The flows are a model
//! (`thalweg/eval/workload.py`), and the footer says so on screen.

use ratatui::layout::{Constraint, Layout, Rect};
use ratatui::style::Color;
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Cell, Paragraph, Row, Sparkline, Table};
use ratatui::Frame;

use crate::app::App;
use crate::ml_client::{ArchetypeRow, FlowRow, ProtectionSnapshot};
use crate::ui::components::{chrome, widgets};
use crate::ui::theme;

const OURS: Color = theme::GREEN;
const BASELINE: Color = theme::ORANGE;

pub fn render(frame: &mut Frame, app: &App, area: Rect) {
    frame.render_widget(Block::default().style(theme::bg()), area);

    let rows = Layout::vertical([
        Constraint::Length(3),  // chrome
        Constraint::Length(5),  // KPI tiles
        Constraint::Length(11), // archetype table: header and eight kinds
        Constraint::Length(5),  // paired sparklines
        Constraint::Min(4),     // flow table
        Constraint::Length(1),  // provenance footer
    ])
    .split(area);

    chrome::render(frame, app, rows[0]);

    let Some(prot) = app.prot_latest.as_ref() else {
        let block = widgets::padded_panel("FLOW PROTECTION", theme::ACCENT);
        let inner = block.inner(rows[2]);
        frame.render_widget(block, rows[2]);
        widgets::hint(
            frame,
            inner,
            "Waiting for protection data. The ML service runs it unless started with --flow-load 0.",
        );
        return;
    };

    render_kpis(frame, app, prot, rows[1]);
    render_archetypes(frame, prot, rows[2]);
    render_sparklines(frame, app, rows[3]);
    render_flows(frame, prot, rows[4]);

    let footer = Line::from(vec![
        Span::styled(" Capacity ", theme::text_dim()),
        Span::styled("calibrated bound from the live pipeline", theme::text_secondary()),
        Span::styled("   Flows ", theme::text_dim()),
        Span::styled("modelled workload, not measured", theme::fg(theme::AMBER)),
        Span::styled(
            format!("   1 decision = {:.0} s slot", prot.seconds_per_slot),
            theme::text_dim(),
        ),
    ]);
    frame.render_widget(Paragraph::new(footer).style(theme::bg()), rows[5]);
}

// ── KPI Tiles ────────────────────────────────────────────────────────────────

fn render_kpis(frame: &mut Frame, app: &App, prot: &ProtectionSnapshot, area: Rect) {
    let bound = app.ml_latest.as_ref().map(|r| r.bound_mbps).unwrap_or(0.0);
    let rate = |r: Option<f64>| r.map(|v| format!("{:.1}%", v * 100.0)).unwrap_or_else(|| "—".into());

    let tiles = vec![
        widgets::Kpi {
            label: "SAFE BOUND",
            value: format!("{bound:.1} Mbps"),
            note: format!("flows ask {:.0} Mbps", prot.offered_mbps),
            color: theme::CYAN,
        },
        widgets::Kpi {
            label: "FLOWS",
            value: format!("{}", prot.n_flows),
            note: format!("{} protected", prot.n_protected),
            color: theme::FG_PRIMARY,
        },
        widgets::Kpi {
            label: "OURS < FLOOR",
            value: rate(prot.ours.critical_violation),
            // Critical flow-slots allocated below floor, since the stream began.
            note: format!("delivered {}", rate(prot.ours.critical_violation_delivered)),
            color: OURS,
        },
        widgets::Kpi {
            label: "LARGEST < FLOOR",
            value: rate(prot.baseline.critical_violation),
            note: format!("delivered {}", rate(prot.baseline.critical_violation_delivered)),
            color: BASELINE,
        },
        widgets::Kpi {
            label: "CRITICAL GAVE UP",
            value: format!("{}  vs  {}", prot.ours.critical_gave_up, prot.baseline.critical_gave_up),
            // The cost side, so the tile cannot be read as protection for free.
            note: format!(
                "ordinary {} vs {}",
                prot.ours.ordinary_gave_up, prot.baseline.ordinary_gave_up
            ),
            color: if prot.ours.critical_gave_up < prot.baseline.critical_gave_up {
                OURS
            } else {
                theme::FG_SECONDARY
            },
        },
        widgets::Kpi {
            label: "FLOORS",
            // Breached means the protected floors did not jointly fit in the
            // bound this slot, so some critical flow is under its floor no
            // matter how the allocator divides it.
            value: if prot.breached { "BREACHED".into() } else { "ALL FIT".into() },
            note: "floors vs bound".into(),
            color: if prot.breached { theme::RED } else { OURS },
        },
    ];
    widgets::kpi_row(frame, area, &tiles);
}

// ── Archetype Table ──────────────────────────────────────────────────────────

fn render_archetypes(frame: &mut Frame, prot: &ProtectionSnapshot, area: Rect) {
    let block = widgets::padded_panel("BY KIND OF FLOW · THIS SLOT", theme::ACCENT);
    let inner = block.inner(area);
    frame.render_widget(block, area);

    let header = Row::new(vec![
        Cell::from("FLOW KIND"),
        Cell::from("MUST KEEP"),
        Cell::from("DECLARES"),
        Cell::from("N"),
        Cell::from("PROTECTED"),
        Cell::from("CRITICALITY"),
        Cell::from("ASKS"),
        Cell::from(Span::styled("OURS", theme::fg_bold(OURS))),
        Cell::from(Span::styled("LARGEST", theme::fg_bold(BASELINE))),
        Cell::from("UNDER FLOOR"),
    ])
    .style(theme::table_header());

    let rows: Vec<Row> = prot.archetypes.iter().map(archetype_row).collect();
    let widths = [
        Constraint::Length(22),
        Constraint::Length(9),
        Constraint::Length(11),
        Constraint::Length(3),
        Constraint::Length(9),
        Constraint::Length(17),
        Constraint::Length(9),
        Constraint::Length(9),
        Constraint::Length(9),
        Constraint::Min(11),
    ];
    frame.render_widget(
        Table::new(rows, widths).header(header).column_spacing(1).style(theme::bg()),
        inner,
    );
}

fn archetype_row(a: &ArchetypeRow) -> Row<'static> {
    let dim = a.n_ours == 0 && a.n_baseline == 0;
    let text = if dim { theme::text_dim() } else { theme::text_primary() };
    let under = |n: u64, color: Color| {
        if n > 0 { Span::styled(format!("{n}"), theme::fg_bold(color)) } else { Span::styled("0", theme::text_dim()) }
    };
    Row::new(vec![
        Cell::from(Span::styled(kind_label(&a.archetype), text)),
        Cell::from(must_keep(a.must_keep)),
        Cell::from(Span::styled(a.declared.clone(), theme::text_secondary())),
        Cell::from(Span::styled(format!("{}", a.n_ours), text)),
        Cell::from(Span::styled(
            format!("{}/{}", a.n_protected, a.n_ours),
            if a.n_protected > 0 { theme::fg(theme::CYAN) } else { theme::text_dim() },
        )),
        Cell::from(match a.mean_criticality {
            Some(c) => criticality_bar(c),
            None => Line::from(Span::styled("—", theme::text_dim())),
        }),
        Cell::from(Span::styled(format!("{:>6.1}", a.demand_mbps), theme::text_secondary())),
        Cell::from(Span::styled(format!("{:>6.1}", a.ours_mbps), theme::fg(OURS))),
        Cell::from(Span::styled(format!("{:>6.1}", a.baseline_mbps), theme::fg(BASELINE))),
        Cell::from(Line::from(vec![
            under(a.ours_below_floor, theme::RED),
            Span::styled(" / ", theme::text_ghost()),
            under(a.baseline_below_floor, theme::RED),
        ])),
    ])
}

// ── Paired Sparklines ────────────────────────────────────────────────────────

fn render_sparklines(frame: &mut Frame, app: &App, area: Rect) {
    let cols = Layout::horizontal([Constraint::Ratio(1, 2), Constraint::Ratio(1, 2)]).split(area);
    // One scale for both, so a taller bar on the right really is more flows.
    let peak = app
        .prot_ours_below
        .iter()
        .chain(app.prot_baseline_below.iter())
        .copied()
        .max()
        .unwrap_or(1)
        .max(1);
    spark(frame, cols[0], "CRITICAL FLOWS UNDER FLOOR · OURS", &app.prot_ours_below, peak, OURS);
    spark(frame, cols[1], "CRITICAL FLOWS UNDER FLOOR · THROTTLE LARGEST", &app.prot_baseline_below, peak, BASELINE);
}

fn spark(
    frame: &mut Frame,
    area: Rect,
    title: &'static str,
    data: &std::collections::VecDeque<u64>,
    peak: u64,
    color: Color,
) {
    let block = widgets::padded_panel(title, color);
    let inner = block.inner(area);
    frame.render_widget(block, area);
    if inner.height < 1 {
        return;
    }
    let width = inner.width.max(4) as usize;
    let slice: Vec<u64> = data.iter().rev().take(width).rev().copied().collect();
    let now = slice.last().copied().unwrap_or(0);
    let rows = Layout::vertical([Constraint::Min(1), Constraint::Length(1)]).split(inner);
    frame.render_widget(
        Sparkline::default().data(&slice).max(peak).style(theme::fg(color)),
        rows[0],
    );
    frame.render_widget(
        Paragraph::new(Line::from(vec![
            Span::styled(format!("{now}"), theme::fg_bold(color)),
            Span::styled(" now", theme::text_dim()),
        ]))
        .style(theme::bg()),
        rows[1],
    );
}

// ── Flow Table ───────────────────────────────────────────────────────────────

fn render_flows(frame: &mut Frame, prot: &ProtectionSnapshot, area: Rect) {
    let block = widgets::padded_panel("FLOWS · LARGEST FIRST · SAME FLOW UNDER BOTH POLICIES", theme::ACCENT);
    let inner = block.inner(area);
    frame.render_widget(block, area);

    let header = Row::new(vec![
        Cell::from("FLOW"),
        Cell::from("MUST KEEP"),
        Cell::from("CRITICALITY"),
        Cell::from("STATE"),
        Cell::from("DEADLINE"),
        Cell::from("FLOOR"),
        Cell::from("ASKS NOW"),
        Cell::from(Span::styled("OURS", theme::fg_bold(OURS))),
        Cell::from(Span::styled("THROTTLE LARGEST", theme::fg_bold(BASELINE))),
    ])
    .style(theme::table_header());

    let visible = inner.height.saturating_sub(1) as usize;
    let rows: Vec<Row> = prot.flows.iter().take(visible).map(flow_row).collect();
    let widths = [
        Constraint::Length(26),
        Constraint::Length(9),
        Constraint::Length(17),
        Constraint::Length(11),
        Constraint::Length(9),
        Constraint::Length(7),
        Constraint::Length(8),
        Constraint::Length(8),
        Constraint::Min(16),
    ];
    frame.render_widget(
        Table::new(rows, widths).header(header).column_spacing(1).style(theme::bg()),
        inner,
    );
}

fn flow_row(f: &FlowRow) -> Row<'static> {
    let has_floor = f.floor_mbps > 0.0;
    let below = |rate: f64| has_floor && rate < f.floor_mbps - 1e-6;

    let state = if f.protected {
        Span::styled(" PROTECTED ", theme::chip(theme::CYAN))
    } else if f.ours_mbps < f.nominal_mbps.max(f.demand_mbps) * 0.95 {
        Span::styled(" throttled", theme::text_secondary())
    } else {
        Span::styled(" full rate", theme::text_dim())
    };
    let deadline = match f.deadline_s {
        Some(d) if d <= 0.0 => Span::styled("missed", theme::fg(theme::RED)),
        Some(d) => Span::styled(format!("{d:>5.0} s"), theme::fg(if d < 120.0 { theme::AMBER } else { theme::FG_SECONDARY })),
        None => Span::styled("    —", theme::text_ghost()),
    };
    let ours = Span::styled(
        format!("{:>6.1}", f.ours_mbps),
        if below(f.ours_mbps) { theme::fg_bold(theme::RED) } else { theme::fg(OURS) },
    );
    let baseline = match (f.baseline_state.as_str(), f.baseline_mbps) {
        (_, Some(rate)) if below(rate) => Line::from(vec![
            Span::styled(format!("{rate:>6.1}"), theme::fg_bold(theme::RED)),
            Span::styled("  under floor", theme::fg(theme::RED)),
        ]),
        (_, Some(rate)) => Line::from(Span::styled(format!("{rate:>6.1}"), theme::fg(BASELINE))),
        ("gave_up", None) => Line::from(Span::styled(" GAVE UP ", theme::chip(theme::RED))),
        ("done", None) => Line::from(Span::styled("  finished", theme::text_dim())),
        _ => Line::from(Span::styled("     —", theme::text_ghost())),
    };

    Row::new(vec![
        Cell::from(Span::styled(flow_label(&f.flow_id, &f.archetype), theme::text_primary())),
        Cell::from(must_keep(f.must_keep)),
        Cell::from(criticality_bar(f.criticality)),
        Cell::from(state),
        Cell::from(deadline),
        Cell::from(Span::styled(
            if has_floor { format!("{:>5.1}", f.floor_mbps) } else { "    —".into() },
            theme::text_secondary(),
        )),
        Cell::from(Span::styled(format!("{:>5.1}", f.demand_mbps), theme::text_secondary())),
        Cell::from(ours),
        Cell::from(baseline),
    ])
}

// ── Helpers ──────────────────────────────────────────────────────────────────

/// A ten-cell bar and the score, coloured against the 0.60 protection
/// threshold in `decide/flows.py`.
fn criticality_bar(c: f64) -> Line<'static> {
    let c = c.clamp(0.0, 1.0);
    let filled = (c * 10.0).round() as usize;
    let color = if c >= 0.60 { theme::CYAN } else if c >= 0.45 { theme::AMBER } else { theme::FG_DIM };
    Line::from(vec![
        Span::styled("█".repeat(filled), theme::fg(color)),
        Span::styled("░".repeat(10 - filled), theme::fg(theme::TRACK)),
        Span::styled(format!(" {c:.2}"), theme::fg_bold(color)),
    ])
}

fn must_keep(yes: bool) -> Span<'static> {
    if yes { Span::styled("yes", theme::fg_bold(theme::FG_PRIMARY)) } else { Span::styled("no", theme::text_dim()) }
}

fn kind_label(archetype: &str) -> String {
    match archetype {
        "patient_monitor" => "patient monitor",
        "pacs_image_push" => "radiology push (PACS)",
        "teleconsult_video" => "teleconsult video",
        "research_upload" => "research upload",
        "video_stream" => "video stream",
        "greedy_downloader" => "downloader",
        "os_update" => "OS update",
        "cloud_backup" => "cloud backup",
        other => other,
    }
    .to_string()
}

fn flow_label(flow_id: &str, archetype: &str) -> String {
    let number = flow_id.rsplit('#').next().unwrap_or("");
    format!("{} #{}", kind_label(archetype), number)
}
