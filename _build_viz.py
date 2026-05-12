"""Builder for math_to_emotion.ipynb. Stacks the visualization layer-by-layer
across cells so the build is legible and re-runnable. Kept around for
iteration: re-run this file to regenerate the notebook from source."""
import nbformat as nbf

nb = nbf.v4.new_notebook()
cells = []

cells.append(nbf.v4.new_markdown_cell("""# VOID SLOTS — math-to-emotion visualization

A multi-track timeline showing how the verified game math creates the player's
emotional ride over a single $20 session. The protagonist is the **INVERT
progress bar** — the mechanic that converts dry spells into anticipation.

We use the per-spin log from `session_generator.py` (math identical to
`session_sim.py` and verified against `MATH_VERIFICATION_REPORT.md`) and
score it with the three-channel emotional model in `emotional_model.py`.

The example is a real simulated session (deterministic seed) chosen for
narrative legibility: 3 INVERT activations and a bust outcome. The point
isn't to claim "this is what every player feels" — it's to make the
math-to-emotion *coupling* visible in a way a histogram cannot.

The notebook builds the figure layer-by-layer so you can see what each
trace, shape, and annotation contributes.

---

## §1. Load the example session and score the emotional channels"""))

cells.append(nbf.v4.new_code_cell('''import random
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from session_generator import simulate_session, BONUS_TRIGGER_LOSSES, BONUS_FREE_SPINS
from emotional_model import score_emotions, EmotionConfig

# Example selection. Rank 4 is the recommended primary (3 INVERTs, bust).
# Rank 1 is the alternate (2 INVERTs, cashout). Swap by uncommenting.
EXAMPLE_SEED = 688409041021946534    # Rank 4 -- bust, 3 INVERTs, full emotional arc
# EXAMPLE_SEED = 13318183712882369139  # Rank 1 -- cashout, 2 INVERTs, lighter arc

START_BANKROLL = 20.00

# Reproducibility: pass the same seed to RNG and store it in the Session.
session = simulate_session(
    starting_bankroll=START_BANKROLL,
    rng=random.Random(EXAMPLE_SEED),
    seed=EXAMPLE_SEED,
)
trajectory = score_emotions(session)

# Quick text summary so we know what we're looking at.
print(f"Session seed: {session.seed_used}")
print(f"  {session.paid_spins} paid + {session.free_spins} free = {session.total_spins} spins")
print(f"  Duration: {session.duration_s:.0f}s ({session.duration_s/60:.1f} min)")
print(f"  Bankroll: ${session.starting_bankroll:.2f} -> peak ${session.peak_bankroll:.2f} "
      f"-> end ${session.ending_bankroll:.2f}")
print(f"  Outcome: {session.outcome}")
print(f"  INVERTs at spin: {session.bonus_spin_indices}")
print(f"  INVERT regions (paid trigger .. last free): {session.invert_regions}")
print(f"  Longest dry spell: {session.longest_dry_spell} spins")
print(f"  Near-misses: {session.near_misses}")
print(f"  Max single payout: ${session.max_single_win:.2f}")'''))

cells.append(nbf.v4.new_markdown_cell("""## §2. Build the figure layer by layer

The final figure has two vertically-stacked subplots sharing one x-axis (spin
index). Each subsequent cell adds one layer. Re-run a cell and re-render `fig`
to see what that layer contributes.

The two rows:

| Row | Track | What it shows |
|---|---|---|
| 1 | **Bankroll** | Money over time, with win markers, near-miss markers, INVERT regions, start/cashout reference lines |
| 2 | **Emotional channels** | Anticipation / Tension / Elation, all on one set of axes so you can see them react to each other |

The bar fill state (0..12) was originally a third row but proved redundant: the INVERT shaded regions on every track already show when each activation fired, and the Anticipation channel is largely a function of bar fill anyway. Dropping it leaves *math* on top (bankroll + events) and *feeling* below.

### §2.1. Layer 1 — bankroll trace, start/cashout reference lines"""))

cells.append(nbf.v4.new_code_cell('''# Plotly auto-parses $...$ pairs as MathJax (LaTeX math-mode). With currency
# strings like "$20 session ... $0.00" the dollars get matched as a math
# delimiter pair and the text between them is re-typeset (spaces stripped).
# Workaround: HTML entity &#36; renders as $ but does not trigger the parser.
# We use it everywhere a literal $ appears in user-visible text.
DOLLAR = "&#36;"

# Pull arrays out of the session log -- one entry per spin.
spin_x         = [r.spin_index     for r in session.log]
bankroll_y     = [r.bankroll_after for r in session.log]

# Two-row scaffold: bankroll on top, emotional channels on bottom.
fig = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    row_heights=[0.55, 0.45],
    vertical_spacing=0.06,
    subplot_titles=(
        "Bankroll over time",
        "Emotional channels",
    ),
)

# Bankroll: a line filled to zero so the descent reads as a draining vessel.
fig.add_trace(
    go.Scatter(
        x=spin_x, y=bankroll_y,
        mode="lines",
        line=dict(color="#1f77b4", width=2.5),
        fill="tozeroy", fillcolor="rgba(31,119,180,0.10)",
        name="Bankroll",
        hovertemplate="Spin %{x}<br>Bankroll: &#36;%{y:.2f}<extra></extra>",
    ),
    row=1, col=1,
)

# Reference lines: starting bankroll and cashout target.
# add_hline draws a horizontal line on a specific subplot.
fig.add_hline(y=session.starting_bankroll, row=1, col=1,
              line=dict(color="#888", width=1, dash="dot"),
              annotation_text=f"start {DOLLAR}{session.starting_bankroll:.0f}",
              annotation_position="right",
              annotation=dict(font_size=10, font_color="#666"))
fig.add_hline(y=session.cashout_target, row=1, col=1,
              line=dict(color="#2ca02c", width=1, dash="dash"),
              annotation_text=f"cashout target {DOLLAR}{session.cashout_target:.0f}",
              annotation_position="right",
              annotation=dict(font_size=10, font_color="#2ca02c"))

# Per-row axis configuration.
fig.update_yaxes(title_text="&#36;", row=1, col=1)
fig.update_xaxes(title_text="Spin index (paid + free)", row=2, col=1)

fig.update_layout(
    template="plotly_white",
    height=720,
    title=dict(
        text=(f"VOID SLOTS — {DOLLAR}{session.starting_bankroll:.0f} session, "
              f"{session.total_spins} spins, {session.outcome}, "
              f"ended {DOLLAR}{session.ending_bankroll:.2f}"),
        font=dict(size=16),
    ),
    showlegend=True,
    legend=dict(orientation="h", y=-0.10, x=0.5, xanchor="center"),
    margin=dict(l=60, r=130, t=80, b=80),  # extra right margin for label tails
)

fig'''))

cells.append(nbf.v4.new_markdown_cell("""**What just happened:** Set up the 2-row scaffold with `make_subplots`. Added the bankroll line on row 1 with a translucent fill to make the bankroll read as a draining vessel. The two `add_hline` calls drop in reference lines for the starting bankroll and the 1.5× cashout target. Empty row 2 is sitting there waiting for the emotional channels.

### §2.2. Layer 2 — INVERT shaded regions

Each INVERT activation spans a stretch of spins (the triggering paid spin plus the 5 free spins that follow). Drawing a shaded rectangle behind those spans turns INVERT into a *region* the eye can locate at a glance — and the same regions repeat on every track because we use `xref="x"` with `yref="paper"`.

> **Plotly footgun:** `fig.update_layout(shapes=[...])` does an *index-merge* with existing shapes — it doesn't replace. So if your subplot already has shapes (like ones added by `add_hline`), passing a new shapes list silently corrupts the first N entries. Use `fig.add_shape(...)` in a loop instead — it appends cleanly. (Same caveat applies to `annotations` and `images`.)"""))

cells.append(nbf.v4.new_code_cell('''# One purple rectangle per INVERT region, spanning full plot height.
# yref="paper" means "0..1 of the figure's height", so the rectangle
# spans every subplot. layer="below" puts it behind the traces.
# Using add_shape (NOT update_layout(shapes=...)) so existing add_hline
# shapes don't get corrupted by Plotly's index-merge behavior.
for start_x, end_x in session.invert_regions:
    fig.add_shape(
        type="rect",
        xref="x", yref="paper",
        x0=start_x - 0.5, x1=end_x + 0.5,    # half-spin overhang for visual breathing room
        y0=0, y1=1,
        fillcolor="rgba(160, 80, 200, 0.13)",  # the "void" purple, low alpha
        line=dict(width=0),
        layer="below",
    )

fig'''))

cells.append(nbf.v4.new_markdown_cell("""**What just happened:** Three purple rectangles, one per INVERT activation. They're drawn with `layer="below"` so the bankroll line stays visually dominant; the regions are atmospheric, not the focus.

Notice the rectangles span both rows even though we only have content on row 1 right now — that's `yref="paper"` doing its job. When we add the emotional channels to row 2, the same regions will continue to span them.

### §2.3. Layer 3 — win markers and near-miss markers

The bankroll line shows *what happened to the money*, but not *what individual spins did to get there*. Markers fix that:

- **Win markers** are circles on the bankroll line, sized by payout — small for $1.50, large for the rare $50.
- **Near-miss markers** are gold star symbols, on the bankroll line at the spin where they happened. Star-shaped because the near-miss in this game is "two stars + a non-star" — the symbol matches the lever."""))

cells.append(nbf.v4.new_code_cell('''import math

# Pull win and near-miss subsets out of the log.
win_records = [r for r in session.log if r.is_win]
nm_records  = [r for r in session.log if r.is_near_miss]

# Win marker size scales with log(payout) for legibility -- otherwise the
# $50 hit dwarfs every other marker. Range roughly 8..22 px.
def win_marker_size(payout: float) -> float:
    return 6 + 4 * math.log2(1 + payout)

# Color wins by tier so the eye groups them.
def win_color(payout: float) -> str:
    if payout >= 50: return "#ffd700"   # gold
    if payout >= 5:  return "#2ca02c"   # green
    if payout >= 2:  return "#7fbf3f"   # light green
    return "#a8d5a0"                    # very light green for $1.50

fig.add_trace(
    go.Scatter(
        x=[r.spin_index     for r in win_records],
        y=[r.bankroll_after for r in win_records],
        mode="markers",
        marker=dict(
            size=[win_marker_size(r.payout) for r in win_records],
            color=[win_color(r.payout) for r in win_records],
            line=dict(color="#1a5e1a", width=1),
            symbol="circle",
        ),
        name="Win",
        hovertemplate=(
            "Spin %{x}<br>"
            "Won &#36;%{customdata[0]:.2f} (%{customdata[1]})<br>"
            "Bankroll: &#36;%{y:.2f}<extra></extra>"
        ),
        customdata=[[r.payout, r.rule] for r in win_records],
    ),
    row=1, col=1,
)

fig.add_trace(
    go.Scatter(
        x=[r.spin_index     for r in nm_records],
        y=[r.bankroll_after for r in nm_records],
        mode="markers",
        marker=dict(
            size=14,
            color="#ffaa00",
            line=dict(color="#7a4f00", width=1),
            symbol="star",
        ),
        name="Near-miss (2 stars)",
        hovertemplate="Spin %{x}<br>Near-miss<br>Bankroll: &#36;%{y:.2f}<extra></extra>",
    ),
    row=1, col=1,
)

fig'''))

cells.append(nbf.v4.new_markdown_cell("""**What just happened:** Two new traces, both `mode="markers"` on row 1. Win markers are circles sized by log(payout) — tied to the same log scaling the elation channel uses, so a $5 win is visibly twice the marker of a $1.50 win, not 3.3×. Near-miss markers are gold stars, matching the star symbol that creates the near-miss.

The `customdata` on the win trace + `%{customdata[0]}` in `hovertemplate` is how you pass extra info into a hover. Hover over a marker and you'll see the payout amount and the rule that produced it.

### §2.4. Layer 4 — the three emotional channels (row 2)

This is the deliverable's namesake. All three channels go on the same subplot — same axes, same y-scale (0..1) — so you can see them *react to each other*. When a win lands, **elation** spikes and **tension** drops at the same time. When a dry spell stretches, **tension** climbs while **anticipation** climbs too (because the INVERT bar is filling underneath the math). At INVERT activation, **anticipation** crashes to zero and **elation** spikes hard.

Filled area under each channel with low alpha — the dominant channel reads clearly, the overlap regions are visibly "mixed feelings"."""))

cells.append(nbf.v4.new_code_cell('''# Each channel: a colored line with a translucent fill to zero.
# Order matters for visual layering (later = on top).

fig.add_trace(
    go.Scatter(
        x=trajectory.spin_index, y=trajectory.tension,
        mode="lines",
        line=dict(color="#d62728", width=2),
        fill="tozeroy", fillcolor="rgba(214,39,40,0.18)",
        name="Tension",
        hovertemplate="Spin %{x}<br>Tension: %{y:.2f}<extra></extra>",
    ),
    row=2, col=1,
)

fig.add_trace(
    go.Scatter(
        x=trajectory.spin_index, y=trajectory.anticipation,
        mode="lines",
        line=dict(color="#17becf", width=2),
        fill="tozeroy", fillcolor="rgba(23,190,207,0.18)",
        name="Anticipation",
        hovertemplate="Spin %{x}<br>Anticipation: %{y:.2f}<extra></extra>",
    ),
    row=2, col=1,
)

fig.add_trace(
    go.Scatter(
        x=trajectory.spin_index, y=trajectory.elation,
        mode="lines",
        line=dict(color="#daa520", width=2.5),
        fill="tozeroy", fillcolor="rgba(218,165,32,0.20)",
        name="Elation",
        hovertemplate="Spin %{x}<br>Elation: %{y:.2f}<extra></extra>",
    ),
    row=2, col=1,
)

fig.update_yaxes(title_text="0 .. 1", row=2, col=1, range=[0, 1.05])

fig'''))

cells.append(nbf.v4.new_markdown_cell("""**What just happened:** Three traces on row 2 — Tension (red), Anticipation (cyan), Elation (gold). Each filled to zero with low alpha so overlap regions show as muddy mid-tones, which is honestly accurate to mixed feelings.

The channels really do react to each other: scrub along the timeline and watch tension drop the moment elation spikes, or anticipation crash to zero the moment INVERT fires.

### §2.5. Layer 5 — named-event annotations

A few hand-picked callouts to anchor the eye. Restraint matters here: too many annotations and the figure becomes a wall of text. We label only the moments the companion text will reference.

> **Same Plotly footgun as shapes:** `update_layout(annotations=[...])` index-merges. We use `fig.add_annotation(...)` to append cleanly."""))

cells.append(nbf.v4.new_code_cell('''# Helper: pull the bankroll value at a given spin_index.
bankroll_at = {r.spin_index: r.bankroll_after for r in session.log}

# An arrow + label for each INVERT activation.
for n, sx in enumerate(session.bonus_spin_indices, 1):
    fig.add_annotation(
        x=sx, y=bankroll_at[sx],
        xref="x", yref="y",
        text=f"<b>Bonus #{n}</b>",
        showarrow=True, arrowhead=2, arrowcolor="#a050c8",
        ax=0, ay=-30,
        bgcolor="rgba(255,255,255,0.9)",
        bordercolor="#a050c8", borderwidth=1,
        font=dict(size=11, color="#5a2078"),
    )

# Peak tension callout (bottom subplot). Note: with shared_xaxes=True the
# x-axis is shared as "x" across all subplots; only y axes are independent
# (y, y2). So we pin x to "x" and y to "y2".
pt_i = trajectory.peak_tension_idx
pt_x = trajectory.spin_index[pt_i]
pt_y = trajectory.tension[pt_i]
fig.add_annotation(
    x=pt_x, y=pt_y,
    xref="x", yref="y2",
    text=f"<b>peak tension</b><br>{pt_y:.2f}",
    showarrow=True, arrowhead=2, arrowcolor="#d62728",
    ax=-50, ay=-35,
    bgcolor="rgba(255,255,255,0.92)",
    bordercolor="#d62728", borderwidth=1,
    font=dict(size=10, color="#7a1f1f"),
)

# Peak elation callout (bottom subplot).
pe_i = trajectory.peak_elation_idx
pe_x = trajectory.spin_index[pe_i]
pe_y = trajectory.elation[pe_i]
fig.add_annotation(
    x=pe_x, y=pe_y,
    xref="x", yref="y2",
    text=f"<b>peak elation</b><br>{pe_y:.2f}",
    showarrow=True, arrowhead=2, arrowcolor="#daa520",
    ax=45, ay=-35,
    bgcolor="rgba(255,255,255,0.92)",
    bordercolor="#daa520", borderwidth=1,
    font=dict(size=10, color="#6e5310"),
)

# End-of-session callout on the bankroll panel.
last = session.log[-1]
end_label = "BUST" if session.outcome == "bust" else "CASHOUT"
end_color = "#cc3333" if session.outcome == "bust" else "#2ca02c"
fig.add_annotation(
    x=last.spin_index, y=last.bankroll_after,
    xref="x", yref="y",
    text=f"<b>{end_label}</b>",
    showarrow=True, arrowhead=2, arrowcolor=end_color,
    ax=-30, ay=20,
    bgcolor="rgba(255,255,255,0.9)",
    bordercolor=end_color, borderwidth=1,
    font=dict(size=11),
)

fig'''))

cells.append(nbf.v4.new_markdown_cell("""**What just happened:** Named-event annotations for the three INVERT activations, the peak tension moment, the peak elation moment, and the session's terminal event (BUST or CASHOUT).

Note `xref="x"` / `yref="y2"` on the bottom-row peak callouts — with `shared_xaxes=True`, the x-axis is shared across all subplots (named `x`), but each subplot has its own y-axis (`y`, `y2`). Use `xref="x"` for the shared axis and `yref="y<row>"` for the per-subplot y. Using `xref="x2"` here would silently fail (the axis doesn't exist when x is shared) and the annotation would not appear.

---

## §3. The completed BUST example

That's the timeline for the BUST example. Two tracks, five layers, one shared x-axis. Try:

- Hovering over win markers to see the payout and rule.
- Hovering over the emotional channels to read individual values.
- Drag-selecting a region to zoom; double-click to reset.
- Clicking a legend entry to toggle that trace.

The interactive feel is the whole reason for picking Plotly over a static matplotlib figure — the static PNG goes in the PDF, but the HTML version preserves the interactivity for anyone exploring the math themselves.

---

## §4. Same builder, second example — the CASHOUT case

Same math, different seed, very different felt experience. To produce the second example without copy-pasting five cells, we package the layers from §2 into a single `build_full_figure(session, trajectory)` function and call it on the cashout session.

The function below is line-for-line what §2's cells did, just consolidated. If you tweak a layer (change a color, move an annotation), update both the function and the §2 cell so they stay in sync. Reading-wise, §2 is the *explanation*; this is the *apparatus*."""))

cells.append(nbf.v4.new_code_cell('''def build_full_figure(session, trajectory):
    """Construct the complete multi-track timeline figure for a session.
    Equivalent to running every cell in §2 in order. Returns a Plotly Figure."""
    DOLLAR = "&#36;"
    spin_x      = [r.spin_index     for r in session.log]
    bankroll_y  = [r.bankroll_after for r in session.log]

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.55, 0.45], vertical_spacing=0.06,
        subplot_titles=("Bankroll over time",
                        "Emotional channels"),
    )

    # --- Layer 1: bankroll line + reference lines ---
    fig.add_trace(go.Scatter(
        x=spin_x, y=bankroll_y, mode="lines",
        line=dict(color="#1f77b4", width=2.5),
        fill="tozeroy", fillcolor="rgba(31,119,180,0.10)",
        name="Bankroll",
        hovertemplate=f"Spin %{{x}}<br>Bankroll: {DOLLAR}%{{y:.2f}}<extra></extra>",
    ), row=1, col=1)

    fig.add_hline(y=session.starting_bankroll, row=1, col=1,
                  line=dict(color="#888", width=1, dash="dot"),
                  annotation_text=f"start {DOLLAR}{session.starting_bankroll:.0f}",
                  annotation_position="right",
                  annotation=dict(font_size=10, font_color="#666"))
    fig.add_hline(y=session.cashout_target, row=1, col=1,
                  line=dict(color="#2ca02c", width=1, dash="dash"),
                  annotation_text=f"cashout target {DOLLAR}{session.cashout_target:.0f}",
                  annotation_position="right",
                  annotation=dict(font_size=10, font_color="#2ca02c"))

    fig.update_yaxes(title_text=DOLLAR, row=1, col=1)
    fig.update_xaxes(title_text="Spin index (paid + free)", row=2, col=1)

    fig.update_layout(
        template="plotly_white", height=720,
        title=dict(
            text=(f"VOID SLOTS — {DOLLAR}{session.starting_bankroll:.0f} session, "
                  f"{session.total_spins} spins, {session.outcome}, "
                  f"ended {DOLLAR}{session.ending_bankroll:.2f}"),
            font=dict(size=16),
        ),
        showlegend=True,
        legend=dict(orientation="h", y=-0.10, x=0.5, xanchor="center"),
        margin=dict(l=60, r=130, t=80, b=80),
    )

    # --- Layer 2: INVERT shaded regions (use add_shape, not update_layout, to avoid index-merge) ---
    for start_x, end_x in session.invert_regions:
        fig.add_shape(
            type="rect", xref="x", yref="paper",
            x0=start_x - 0.5, x1=end_x + 0.5, y0=0, y1=1,
            fillcolor="rgba(160, 80, 200, 0.13)",
            line=dict(width=0), layer="below",
        )

    # --- Layer 3: win + near-miss markers ---
    win_records = [r for r in session.log if r.is_win]
    nm_records  = [r for r in session.log if r.is_near_miss]

    def win_marker_size(p): return 6 + 4 * math.log2(1 + p)
    def win_color(p):
        if p >= 50: return "#ffd700"
        if p >= 5:  return "#2ca02c"
        if p >= 2:  return "#7fbf3f"
        return "#a8d5a0"

    fig.add_trace(go.Scatter(
        x=[r.spin_index for r in win_records],
        y=[r.bankroll_after for r in win_records],
        mode="markers",
        marker=dict(size=[win_marker_size(r.payout) for r in win_records],
                    color=[win_color(r.payout) for r in win_records],
                    line=dict(color="#1a5e1a", width=1), symbol="circle"),
        name="Win",
        hovertemplate=(f"Spin %{{x}}<br>Won {DOLLAR}%{{customdata[0]:.2f}} "
                       f"(%{{customdata[1]}})<br>Bankroll: {DOLLAR}%{{y:.2f}}<extra></extra>"),
        customdata=[[r.payout, r.rule] for r in win_records],
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=[r.spin_index for r in nm_records],
        y=[r.bankroll_after for r in nm_records],
        mode="markers",
        marker=dict(size=14, color="#ffaa00",
                    line=dict(color="#7a4f00", width=1), symbol="star"),
        name="Near-miss (2 stars)",
        hovertemplate=f"Spin %{{x}}<br>Near-miss<br>Bankroll: {DOLLAR}%{{y:.2f}}<extra></extra>",
    ), row=1, col=1)

    # --- Layer 4: emotional channels ---
    fig.add_trace(go.Scatter(
        x=trajectory.spin_index, y=trajectory.tension, mode="lines",
        line=dict(color="#d62728", width=2),
        fill="tozeroy", fillcolor="rgba(214,39,40,0.18)", name="Tension",
        hovertemplate="Spin %{x}<br>Tension: %{y:.2f}<extra></extra>",
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=trajectory.spin_index, y=trajectory.anticipation, mode="lines",
        line=dict(color="#17becf", width=2),
        fill="tozeroy", fillcolor="rgba(23,190,207,0.18)", name="Anticipation",
        hovertemplate="Spin %{x}<br>Anticipation: %{y:.2f}<extra></extra>",
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=trajectory.spin_index, y=trajectory.elation, mode="lines",
        line=dict(color="#daa520", width=2.5),
        fill="tozeroy", fillcolor="rgba(218,165,32,0.20)", name="Elation",
        hovertemplate="Spin %{x}<br>Elation: %{y:.2f}<extra></extra>",
    ), row=2, col=1)
    fig.update_yaxes(title_text="0 .. 1", row=2, col=1, range=[0, 1.05])

    # --- Layer 5: annotations ---
    bankroll_at = {r.spin_index: r.bankroll_after for r in session.log}
    for n, sx in enumerate(session.bonus_spin_indices, 1):
        fig.add_annotation(
            x=sx, y=bankroll_at[sx], xref="x", yref="y",
            text=f"<b>Bonus #{n}</b>",
            showarrow=True, arrowhead=2, arrowcolor="#a050c8",
            ax=0, ay=-30,
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#a050c8", borderwidth=1,
            font=dict(size=11, color="#5a2078"),
        )

    pt_i = trajectory.peak_tension_idx
    fig.add_annotation(
        x=trajectory.spin_index[pt_i], y=trajectory.tension[pt_i],
        xref="x", yref="y2",
        text=f"<b>peak tension</b><br>{trajectory.tension[pt_i]:.2f}",
        showarrow=True, arrowhead=2, arrowcolor="#d62728",
        ax=-50, ay=-35,
        bgcolor="rgba(255,255,255,0.92)",
        bordercolor="#d62728", borderwidth=1,
        font=dict(size=10, color="#7a1f1f"),
    )

    pe_i = trajectory.peak_elation_idx
    fig.add_annotation(
        x=trajectory.spin_index[pe_i], y=trajectory.elation[pe_i],
        xref="x", yref="y2",
        text=f"<b>peak elation</b><br>{trajectory.elation[pe_i]:.2f}",
        showarrow=True, arrowhead=2, arrowcolor="#daa520",
        ax=45, ay=-35,
        bgcolor="rgba(255,255,255,0.92)",
        bordercolor="#daa520", borderwidth=1,
        font=dict(size=10, color="#6e5310"),
    )

    last = session.log[-1]
    end_label = "BUST" if session.outcome == "bust" else "CASHOUT"
    end_color = "#cc3333" if session.outcome == "bust" else "#2ca02c"
    fig.add_annotation(
        x=last.spin_index, y=last.bankroll_after, xref="x", yref="y",
        text=f"<b>{end_label}</b>",
        showarrow=True, arrowhead=2, arrowcolor=end_color,
        ax=-30, ay=20,
        bgcolor="rgba(255,255,255,0.9)",
        bordercolor=end_color, borderwidth=1,
        font=dict(size=11),
    )

    return fig


# ---- Build the cashout example ----
CASHOUT_SEED = 13318183712882369139
session_cashout = simulate_session(
    starting_bankroll=START_BANKROLL,
    rng=random.Random(CASHOUT_SEED),
    seed=CASHOUT_SEED,
)
trajectory_cashout = score_emotions(session_cashout)

print(f"Cashout example: seed={session_cashout.seed_used}")
print(f"  {session_cashout.paid_spins} paid + {session_cashout.free_spins} free "
      f"= {session_cashout.total_spins} spins")
print(f"  Duration: {session_cashout.duration_s:.0f}s "
      f"({session_cashout.duration_s/60:.1f} min)")
print(f"  Bankroll: ${session_cashout.starting_bankroll:.2f} -> "
      f"peak ${session_cashout.peak_bankroll:.2f} -> "
      f"end ${session_cashout.ending_bankroll:.2f}")
print(f"  INVERTs at: {session_cashout.bonus_spin_indices}")
print(f"  Near-misses: {session_cashout.near_misses}")
print(f"  Peak emotional channels: T={max(trajectory_cashout.tension):.2f}  "
      f"E={max(trajectory_cashout.elation):.2f}  "
      f"A={max(trajectory_cashout.anticipation):.2f}")

fig_cashout = build_full_figure(session_cashout, trajectory_cashout)
fig_cashout'''))

cells.append(nbf.v4.new_markdown_cell("""## §5. Side-by-side: same math, different luck

Both examples run on the same verified math (same RTP, same hit frequency, same bonus rate). The only difference is the random seed — i.e., luck. The contrast is the deliverable's whole argument.

| | **BUST example** | **CASHOUT example** |
|---|---|---|
| Outcome | Bust at $0 | Cashout at $30.50 (1.5×) |
| Duration | ~3.6 min, 69 spins | ~2.8 min, 52 spins |
| INVERTs | 3 | 2 |
| Longest dry spell | 15 spins | 11 spins |
| Near-misses | 2 | 4 |
| Peak tension | **0.83** | 0.39 |
| Peak elation | 0.71 | **0.80** |
| Peak anticipation | 0.70 | **0.79** (NM residual on top of full bar) |

**What changes between them:**

- **Tension does most of the work in the bust case** (peak 0.83 vs 0.39). The cashout case never has a long enough dry spell or deep enough bankroll dip to push tension past ~0.4. The bust example's mid-session 8-spin dry spell with bankroll under $5 produces the dominant emotional event.
- **Anticipation gets boosted by near-misses in the cashout case**, where 4 near-misses (vs 2) produce visible bumps on top of the bar-fill base. Look for the cyan spikes that exceed 0.7 — those are bar+near-miss combined.
- **Elation is roughly comparable** (0.71 vs 0.80) but the cashout version's elation is more *sustained* — wins come closer together in the second half, so the channel doesn't fully decay between spikes.
- **The INVERTs themselves play out differently.** In the bust case, Bonus #2 pays $0 (five free spins, no wins) — the elation spike is purely the "+0.3 visual transformation" bump. In the cashout case, both bonuses deliver paying free spins.

**The pair makes the math-to-emotion coupling visible.** A histogram tells you 60% of $20 sessions bust. A timeline tells you which 60% felt cheated and which 60% had a good ride before busting — and shows the math creating each ride directly.

---

## §6. Export — static PNGs (for PDF) and interactive HTMLs (for hosting)"""))

cells.append(nbf.v4.new_code_cell('''import os

# Build/cache the bust figure too -- the §2 walkthrough already constructed
# `fig`, but rebuilding via the same function guarantees parity with the
# cashout export.
fig_bust = build_full_figure(session, trajectory)

OUT_DIR = os.path.dirname(os.path.abspath("session_generator.py"))
exports = [
    ("math_to_emotion_bust",    fig_bust,    session,         trajectory),
    ("math_to_emotion_cashout", fig_cashout, session_cashout, trajectory_cashout),
]

written = []
for stem, f, s, t in exports:
    png_path  = os.path.join(OUT_DIR, f"{stem}.png")
    html_path = os.path.join(OUT_DIR, f"{stem}.html")
    f.write_image(png_path, width=1400, height=720, scale=2)   # scale=2 for crisp PDF print
    f.write_html(html_path, include_plotlyjs="cdn", full_html=True,
                 config={"displayModeBar": True, "responsive": True})
    written.append((stem, png_path, html_path))
    print(f"  {stem}:")
    print(f"    PNG  -> {png_path}")
    print(f"    HTML -> {html_path}")
print()
print("Done. Both deliverables ready for PDF embedding (PNGs) and "
      "hosted exploration (HTMLs).")'''))

cells.append(nbf.v4.new_markdown_cell("""## §7. Companion text (200–300 words)

The text below is the proposed companion blurb for the PDF submission. It addresses both examples as a contrasting pair and explicitly states what the visualization claims, what it omits, and what value it adds over a histogram.

---

> **What this visualization shows.** Two single VOID SLOTS sessions on a $20 starting bankroll, simulated with the verified game math, displayed as two-track timelines. The protagonist of each is the INVERT progress bar — the mechanic that converts dry spells into anticipation, surfaced visually as the shaded purple regions on every track when the bar fills and INVERT activates. Two tracks share a common spin-index axis: **bankroll over time** (with win and near-miss markers) and **three emotional channels** (Anticipation, Tension, Elation) computed from the per-spin log via a stated psychological model with disclosed coefficients. The two examples are a bust (3 INVERTs, peak tension 0.83) and a cashout (2 INVERTs, peak elation 0.80). Same math; only the random seed differs.
>
> **What it omits.** Population-level statistics (each is one session, not a distribution), cross-session memory, auto-spin compression, and any individual player's actual affect. The emotional model is a stated heuristic — not a measurement and not a prediction — grounded in published behavioural-economics levers (peak-end rule, near-miss reward-circuit activation, log-scaled win valuation) but its coefficients are hand-picked for legibility. Sub-bet wins ("losses disguised as wins") aren't a lever in VOID SLOTS, so they aren't shown.
>
> **What it makes visible that a histogram cannot.** A histogram tells you 60% of $20 sessions bust. It cannot tell you which 60% felt cheated and which 60% had a good ride before busting. The bust example shows three INVERT activations that still ended in $0 — peak-end pain a histogram averages away. The cashout example shows the alternative path: same probabilities, different luck, completely different felt experience. The pair makes the math-to-emotion coupling legible.

---

A standalone copy of this text is also written to `MATH_TO_EMOTION_COMPANION.md` for easy embedding in the PDF."""))

cells.append(nbf.v4.new_code_cell('''COMPANION_TEXT = """\\
# VOID SLOTS — math-to-emotion visualization, companion text

**What this visualization shows.** Two single VOID SLOTS sessions on a $20 starting bankroll, simulated with the verified game math, displayed as two-track timelines. The protagonist of each is the INVERT progress bar — the mechanic that converts dry spells into anticipation, surfaced visually as the shaded purple regions on every track when the bar fills and INVERT activates. Two tracks share a common spin-index axis: **bankroll over time** (with win and near-miss markers) and **three emotional channels** (Anticipation, Tension, Elation) computed from the per-spin log via a stated psychological model with disclosed coefficients. The two examples are a bust (3 INVERTs, peak tension 0.83) and a cashout (2 INVERTs, peak elation 0.80). Same math; only the random seed differs.

**What it omits.** Population-level statistics (each is one session, not a distribution), cross-session memory, auto-spin compression, and any individual player\\'s actual affect. The emotional model is a stated heuristic — not a measurement and not a prediction — grounded in published behavioural-economics levers (peak-end rule, near-miss reward-circuit activation, log-scaled win valuation) but its coefficients are hand-picked for legibility. Sub-bet wins ("losses disguised as wins") aren\\'t a lever in VOID SLOTS, so they aren\\'t shown.

**What it makes visible that a histogram cannot.** A histogram tells you 60% of $20 sessions bust. It cannot tell you which 60% felt cheated and which 60% had a good ride before busting. The bust example shows three INVERT activations that still ended in $0 — peak-end pain a histogram averages away. The cashout example shows the alternative path: same probabilities, different luck, completely different felt experience. The pair makes the math-to-emotion coupling legible.
"""

with open("MATH_TO_EMOTION_COMPANION.md", "w", encoding="utf-8") as f:
    f.write(COMPANION_TEXT)
print(f"Wrote MATH_TO_EMOTION_COMPANION.md ({len(COMPANION_TEXT.split())} words)")'''))

nb["cells"] = cells
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3.14"},
}

# Write relative to the script's own directory so the builder works
# regardless of which cwd it's invoked from.
import os
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NB_PATH = os.path.join(SCRIPT_DIR, "math_to_emotion.ipynb")

with open(NB_PATH, "w", encoding="utf-8") as f:
    nbf.write(nb, f)

print(f"Wrote {NB_PATH}")

# ---------------------------------------------------------------------------
# Run the notebook in-process to verify everything works AND to produce
# both diagnostic PNGs (bust + cashout) in one shot. This catches errors
# before the user opens the notebook.
# ---------------------------------------------------------------------------
print("Running notebook code in-process for verification...")
import sys

code_blocks = [c["source"] for c in nb["cells"] if c["cell_type"] == "code"]
combined = "\n\n".join(code_blocks)
ns: dict = {}
exec(combined, ns)

for var_name, label in [("fig_bust", "BUST"), ("fig_cashout", "CASHOUT")]:
    f = ns.get(var_name)
    if f is None:
        print(f"  ERROR: no `{var_name}` variable after exec")
        sys.exit(1)
    print(f"  {label}: {len(f.layout.shapes)} shapes, "
          f"{len(f.layout.annotations)} annotations -- OK")

print()
print("Both figures built and exported. Open math_to_emotion.ipynb to view "
      "interactively, or look at math_to_emotion_bust.png / "
      "math_to_emotion_cashout.png for the static versions.")
