"""
VOID SLOTS -- session generator for the math-to-emotion visualization
=====================================================================

Sibling to session_sim.py. Same game model, same RNG semantics, same
timing -- but restructured around a *per-spin log* as the primary output
rather than an aggregated SessionResult. The visualization needs the
exact sequence of events, not just the summary, so this file is built
to emit one SpinRecord per spin (paid or free), with every signal the
timeline tracks share an x-axis on.

What this file is NOT:

  - Not a replacement for session_sim.py. That file feeds the
    player-experience report and is kept stable for reproducibility of
    PLAYER_EXPERIENCE_REPORT.md.
  - Not a re-derivation of the math. evaluate(), the reels, the
    paytables, and the timing constants are copied byte-for-byte from
    session_sim.py / mc_simulate.py (which were verified against the
    closed-form math in MATH_VERIFICATION_REPORT.md).

What's new vs session_sim.py:

  - SpinRecord  -- per-spin row capturing bankroll, bar fill, outcome,
                   wall-clock time, near-miss flag, dry-spell length,
                   and a bonus-id for grouping free spins.
  - Session     -- wraps the per-spin log with cheap summary properties
                   used for example selection and the sanity check.
  - Bonus time  -- distributed across the 5 free spins instead of
                   stacked on the triggering paid spin, so the timeline
                   shows the INVERT region as a stretch of time rather
                   than an instant.

The aggregate summary properties (realized_rtp, total_won, etc.) are
computed FROM the log, so they can be cross-checked against the
verified headline numbers as a sanity gate before any visualization.
"""

from __future__ import annotations
import random
import time
import math
from dataclasses import dataclass, field
from collections import Counter
from typing import Optional, List


# -----------------------------------------------------------------------------
# Game spec -- copied byte-for-byte from session_sim.py / mc_simulate.py.
# DO NOT MODIFY without re-running verify_math.py + mc_simulate.py.
# -----------------------------------------------------------------------------
REELS = [
    [1, 2, 2, 3, 3, 4, 3, 3, 2, 1, 0, 1, 2, 1, 0, 1, 2, 1, 3, 1, 0, 1],
    [1, 2, 3, 4, 9, 4, 9, 3, 2, 1, 1, 1, 2, 1, 3, 1, 2, 1, 3, 1, 2, 1],
    [1, 2, 1, 3, 1, 2, 1, 0, 3, 4, 3, 0, 2, 2, 1, 3, 1, 2, 1, 3, 1, 0],
]
WILD = 9
# Symbol id -> human-readable label, for hovers / annotations.
SYMBOL_NAME = {0: "blank", 1: "lemon", 2: "cherry", 3: "diamond", 4: "star", 9: "wild"}
PAY3 = {0: 0.0, 1: 1.5, 2: 2.0, 3: 5.0, 4: 50.0, 9: 0.0}
PAY2 = {0: 0.0, 1: 0.0, 2: 1.5, 3: 2.0, 4: 5.0, 9: 0.0}
WILD_MULTIPLIER = 2.0
BET = 1.0
BONUS_TRIGGER_LOSSES = 12
BONUS_FREE_SPINS = 5


def evaluate(s1, s2, s3):
    """Pay-rule evaluator (priority: 3oak -> wild sub -> 2oak).
    Returns (payout, paying_symbol_id, rule_name). Byte-for-byte identical
    to session_sim.py / mc_simulate.py -- see MATH_VERIFICATION_REPORT.md."""
    if s1 == s2 == s3 and PAY3.get(s1, 0) > 0:
        return PAY3[s1] * BET, s1, "3oak"
    syms = (s1, s2, s3)
    wc = sum(1 for s in syms if s == WILD)
    if wc == 1:
        non_wild = [s for s in syms if s != WILD]
        if non_wild[0] == non_wild[1] and PAY3.get(non_wild[0], 0) > 0:
            return PAY3[non_wild[0]] * WILD_MULTIPLIER * BET, non_wild[0], "wild"
        return 0.0, None, "miss"
    if wc >= 2:
        return 0.0, None, "miss"
    matched = None
    if   s1 == s2 and s1 != s3: matched = s1
    elif s1 == s3 and s1 != s2: matched = s1
    elif s2 == s3 and s2 != s1: matched = s2
    if matched is not None and PAY2.get(matched, 0) > 0:
        return PAY2[matched] * BET, matched, "2oak"
    return 0.0, None, "miss"


# -----------------------------------------------------------------------------
# Spin timing -- copied from session_sim.py.
# -----------------------------------------------------------------------------
BEAT_S = 60.0 / 152.0
BASE_SPIN_ANIM_S = 6 * BEAT_S            # ~ 2.368 s
LOSS_REACTION_S       = 0.5
SMALL_WIN_REACTION_S  = 1.2
MEDIUM_WIN_REACTION_S = 2.5
BIG_WIN_REACTION_S    = 5.0
BONUS_ANIM_S = 42 * BEAT_S               # ~ 16.579 s (entry+5*6+4*2+exit)
BONUS_ACTIVATION_REACTION_S = 1.5


def paid_spin_duration_s(payout: float) -> float:
    """Wall-clock seconds for one paid spin (animation + reaction + any
    win celebration the player sits through)."""
    if payout <= 0:
        return BASE_SPIN_ANIM_S + LOSS_REACTION_S
    ratio = payout / BET
    if ratio <= 5.0:
        return BASE_SPIN_ANIM_S + SMALL_WIN_REACTION_S
    if ratio <= 20.0:
        return BASE_SPIN_ANIM_S + MEDIUM_WIN_REACTION_S
    return BASE_SPIN_ANIM_S + BIG_WIN_REACTION_S


def random_stop_symbol(rng: random.Random, reel_idx: int) -> int:
    r = REELS[reel_idx]
    return r[rng.randrange(len(r))]


# -----------------------------------------------------------------------------
# Per-spin record + session container
# -----------------------------------------------------------------------------

@dataclass
class SpinRecord:
    """One row per spin (paid or free). The viz traces are columns of these."""
    # Indexing
    spin_index: int                   # 1-based, unified across paid+free
    paid_spin_index: Optional[int]    # 1-based paid-only; None for free spins
    is_free: bool
    bonus_id: Optional[int]           # 1-based bonus activation id; None outside bonuses

    # Reel outcome
    s1: int
    s2: int
    s3: int
    payout: float
    rule: str                         # 'miss' | '3oak' | 'wild' | '2oak'
    sym: Optional[int]                # paying symbol id (None for miss)

    # State after this spin
    bankroll_after: float
    bar_fill_after: int               # 0..12; 0 throughout free spins (bar hidden in INVERT)
    dry_spell_length_after: int       # consecutive losses (paid+free), resets on any win

    # Wall-clock time
    wall_time_s: float                # duration of this spin's contribution
    cumulative_time_s: float          # running total at end of this spin

    # Derived flags for the viz
    is_win: bool
    is_near_miss: bool                # 2 stars on payline + no wild present
    bonus_triggered: bool             # True on the paid spin that filled the bar


@dataclass
class Session:
    """A single simulated session, primarily its per-spin log.

    The summary properties are derived from `log` so they can be
    cross-checked against the verified math headline numbers.
    """
    starting_bankroll: float
    cashout_target: float
    outcome: str                      # 'cashout' | 'bust' | 'time_cap'
    log: List[SpinRecord]
    seed_used: int

    # ---- light-weight derived summaries (computed lazily, not stored) ----
    @property
    def ending_bankroll(self) -> float:
        return self.log[-1].bankroll_after if self.log else self.starting_bankroll

    @property
    def paid_spins(self) -> int:
        return sum(1 for r in self.log if not r.is_free)

    @property
    def free_spins(self) -> int:
        return sum(1 for r in self.log if r.is_free)

    @property
    def total_spins(self) -> int:
        return len(self.log)

    @property
    def duration_s(self) -> float:
        return self.log[-1].cumulative_time_s if self.log else 0.0

    @property
    def peak_bankroll(self) -> float:
        return max((r.bankroll_after for r in self.log),
                   default=self.starting_bankroll)

    @property
    def bottom_bankroll(self) -> float:
        return min((r.bankroll_after for r in self.log),
                   default=self.starting_bankroll)

    @property
    def features_triggered(self) -> int:
        return sum(1 for r in self.log if r.bonus_triggered)

    @property
    def longest_dry_spell(self) -> int:
        return max((r.dry_spell_length_after for r in self.log), default=0)

    @property
    def max_single_win(self) -> float:
        return max((r.payout for r in self.log), default=0.0)

    @property
    def total_won(self) -> float:
        return sum(r.payout for r in self.log)

    @property
    def total_bet(self) -> float:
        return self.paid_spins * BET

    @property
    def near_misses(self) -> int:
        return sum(1 for r in self.log if r.is_near_miss)

    @property
    def realized_rtp(self) -> float:
        """Total won / total bet. Should converge to ~0.9037 over many sessions."""
        tb = self.total_bet
        return self.total_won / tb if tb > 0 else 0.0

    @property
    def first_bonus_spin_index(self) -> Optional[int]:
        for r in self.log:
            if r.bonus_triggered:
                return r.spin_index
        return None

    @property
    def bonus_spin_indices(self) -> List[int]:
        """spin_index of every paid spin that triggered a bonus."""
        return [r.spin_index for r in self.log if r.bonus_triggered]

    @property
    def invert_regions(self) -> List[tuple]:
        """List of (start_spin_index, end_spin_index) for each INVERT
        region. The region spans from the triggering paid spin to the
        last free spin of that bonus. Used for shaded `shapes` on the viz."""
        regions: List[tuple] = []
        bonus_starts: dict = {}   # bonus_id -> start spin index
        bonus_ends:   dict = {}   # bonus_id -> end spin index
        for r in self.log:
            if r.bonus_triggered and r.bonus_id is not None:
                bonus_starts[r.bonus_id] = r.spin_index
                bonus_ends[r.bonus_id]   = r.spin_index
            elif r.is_free and r.bonus_id is not None:
                bonus_ends[r.bonus_id] = r.spin_index
        for bid in sorted(bonus_starts):
            regions.append((bonus_starts[bid], bonus_ends[bid]))
        return regions


# -----------------------------------------------------------------------------
# Simulation
# -----------------------------------------------------------------------------

def simulate_session(
    starting_bankroll: float,
    cashout_multiplier: float = 1.5,
    time_cap_s: Optional[float] = None,
    rng: Optional[random.Random] = None,
    seed: Optional[int] = None,
    starting_loss_count: int = 0,
) -> Session:
    """Simulate one session. Stops on bust, cashout, or time cap.

    Bonus policy: the moment the bar fills (BONUS_TRIGGER_LOSSES paid
    losses, default 12), the player activates it -- mirrors game.js's
    immediate-activation assumption and matches session_sim.py.

    Bonus wall-clock distribution (differs from session_sim.py):
      - BONUS_ACTIVATION_REACTION_S is appended to the triggering paid
        spin's wall_time_s (the "I see the bar full, I click" pause).
      - BONUS_ANIM_S is distributed evenly across the 5 free spins.
        Total session duration is identical to session_sim.py; the
        difference is only in how that duration is allocated across
        records so the viz can show INVERT as a stretch of time.

    Returns a Session whose `log` attribute is the per-spin sequence.
    """
    if rng is None:
        seed_used = seed if seed is not None else random.SystemRandom().randrange(2**63)
        rng = random.Random(seed_used)
    else:
        seed_used = seed if seed is not None else -1

    bankroll = starting_bankroll
    cashout = starting_bankroll * cashout_multiplier
    cumulative_time = 0.0
    loss_count = starting_loss_count
    dry_spell = 0
    spin_index = 0
    paid_spin_index = 0
    bonus_id = 0
    free_spin_anim_per_spin = BONUS_ANIM_S / BONUS_FREE_SPINS

    log: List[SpinRecord] = []
    outcome = "time_cap"

    while True:
        # Stop checks (before each PAID spin).
        if bankroll < BET:
            outcome = "bust"
            break
        if bankroll >= cashout:
            outcome = "cashout"
            break
        if time_cap_s is not None and cumulative_time >= time_cap_s:
            outcome = "time_cap"
            break

        # --- paid spin ---
        bankroll -= BET
        s1 = random_stop_symbol(rng, 0)
        s2 = random_stop_symbol(rng, 1)
        s3 = random_stop_symbol(rng, 2)
        payout, sym, rule = evaluate(s1, s2, s3)
        bankroll += payout
        is_win = payout > 0
        # Near-miss: exactly 2 stars on payline AND no wild present.
        # (Wild + 2 stars actually scores a win, so it's not a near miss.)
        near_miss = ((s1, s2, s3).count(4) == 2 and WILD not in (s1, s2, s3))

        # Update counters BEFORE writing the record.
        if is_win:
            dry_spell = 0
        else:
            dry_spell += 1
            loss_count += 1

        # Bonus trigger check (BEFORE adding wall time, so we can roll
        # the activation-reaction into the triggering paid spin).
        bonus_triggered = (not is_win) and (loss_count >= BONUS_TRIGGER_LOSSES)

        # Wall-time for this paid spin.
        paid_dur = paid_spin_duration_s(payout)
        if bonus_triggered:
            paid_dur += BONUS_ACTIVATION_REACTION_S
        cumulative_time += paid_dur
        spin_index += 1
        paid_spin_index += 1

        log.append(SpinRecord(
            spin_index=spin_index,
            paid_spin_index=paid_spin_index,
            is_free=False,
            bonus_id=(bonus_id + 1) if bonus_triggered else None,
            s1=s1, s2=s2, s3=s3,
            payout=payout, rule=rule, sym=sym,
            bankroll_after=bankroll,
            bar_fill_after=(loss_count if not bonus_triggered else BONUS_TRIGGER_LOSSES),
            dry_spell_length_after=dry_spell,
            wall_time_s=paid_dur,
            cumulative_time_s=cumulative_time,
            is_win=is_win,
            is_near_miss=near_miss,
            bonus_triggered=bonus_triggered,
        ))

        # --- free spins inside the INVERT bonus ---
        if bonus_triggered:
            bonus_id += 1
            loss_count = 0
            for _ in range(BONUS_FREE_SPINS):
                f1 = random_stop_symbol(rng, 0)
                f2 = random_stop_symbol(rng, 1)
                f3 = random_stop_symbol(rng, 2)
                fp, fsym, frule = evaluate(f1, f2, f3)
                bankroll += fp
                fwin = fp > 0
                fnear = ((f1, f2, f3).count(4) == 2 and WILD not in (f1, f2, f3))

                if fwin:
                    dry_spell = 0
                else:
                    dry_spell += 1
                # Free-spin losses do NOT advance loss_count (no re-trigger).

                cumulative_time += free_spin_anim_per_spin
                spin_index += 1
                log.append(SpinRecord(
                    spin_index=spin_index,
                    paid_spin_index=None,
                    is_free=True,
                    bonus_id=bonus_id,
                    s1=f1, s2=f2, s3=f3,
                    payout=fp, rule=frule, sym=fsym,
                    bankroll_after=bankroll,
                    bar_fill_after=0,  # bar hidden during INVERT
                    dry_spell_length_after=dry_spell,
                    wall_time_s=free_spin_anim_per_spin,
                    cumulative_time_s=cumulative_time,
                    is_win=fwin,
                    is_near_miss=fnear,
                    bonus_triggered=False,
                ))

    return Session(
        starting_bankroll=starting_bankroll,
        cashout_target=cashout,
        outcome=outcome,
        log=log,
        seed_used=seed_used,
    )


def simulate_many(
    starting_bankroll: float,
    n_sessions: int,
    cashout_multiplier: float = 1.5,
    seed: int = 42,
    starting_loss_count: int = 0,
) -> List[Session]:
    """Run n independent sessions with deterministic per-session seeds."""
    master = random.Random(seed)
    sessions = []
    for _ in range(n_sessions):
        sub_seed = master.getrandbits(64)
        sessions.append(simulate_session(
            starting_bankroll=starting_bankroll,
            cashout_multiplier=cashout_multiplier,
            rng=random.Random(sub_seed),
            seed=sub_seed,
            starting_loss_count=starting_loss_count,
        ))
    return sessions


# -----------------------------------------------------------------------------
# Sanity check -- aggregate the per-spin log over N sessions and confirm
# the headline numbers from MATH_VERIFICATION_REPORT.md fall within MC noise.
# -----------------------------------------------------------------------------

# Targets from MATH_VERIFICATION_REPORT.md.
TARGETS = dict(
    hit_freq      = 0.323065,
    base_rtp      = 0.704874,
    free_per_spin = 0.282056,
    feature_rtp   = 0.198814,
    total_rtp     = 0.903688,
)


def _aggregate(sessions: List[Session]) -> dict:
    """Walk every SpinRecord across all sessions and collect the raw
    sums needed for the sanity computations below."""
    paid_spins = 0
    free_spins = 0
    paid_payout = 0.0
    free_payout = 0.0
    paid_wins   = 0
    free_wins   = 0
    paid_payout_sq_sum = 0.0
    free_payout_sq_sum = 0.0
    for s in sessions:
        for r in s.log:
            if r.is_free:
                free_spins += 1
                free_payout += r.payout
                free_payout_sq_sum += r.payout * r.payout
                if r.is_win:
                    free_wins += 1
            else:
                paid_spins += 1
                paid_payout += r.payout
                paid_payout_sq_sum += r.payout * r.payout
                if r.is_win:
                    paid_wins += 1
    return dict(
        paid_spins=paid_spins, free_spins=free_spins,
        paid_payout=paid_payout, free_payout=free_payout,
        paid_wins=paid_wins, free_wins=free_wins,
        paid_payout_sq_sum=paid_payout_sq_sum,
        free_payout_sq_sum=free_payout_sq_sum,
    )


def per_spin_check(sessions: List[Session]) -> dict:
    """Verify per-spin rule correctness. These statistics are properties
    of an individual spin's outcome distribution and do NOT depend on
    session stops, so they must match the verified math within MC noise
    for the per-spin log to be trustworthy.

    Checked: hit_freq (paid), base_rtp (paid), hit_freq (free), base_rtp
    (free). Free-spin rules are identical to paid (same reels, same
    paytable), so both should converge to the same targets.
    """
    a = _aggregate(sessions)
    p, f = a["paid_spins"], a["free_spins"]
    if p == 0:
        return {"error": "no paid spins"}

    obs = {
        "hit_freq (paid)": (a["paid_wins"] / p,            TARGETS["hit_freq"]),
        "base_rtp (paid)": (a["paid_payout"] / p,          TARGETS["base_rtp"]),
        "hit_freq (free)": (a["free_wins"] / f if f else 0, TARGETS["hit_freq"]),
        "base_rtp (free)": (a["free_payout"] / f if f else 0, TARGETS["base_rtp"]),
    }

    # 1-sigma SE for the paid base_rtp (the headline per-spin number).
    var_paid = a["paid_payout_sq_sum"] / p - (a["paid_payout"] / p) ** 2
    se_paid = math.sqrt(max(var_paid, 0) / p)
    var_free = a["free_payout_sq_sum"] / f - (a["free_payout"] / f) ** 2 if f else 0
    se_free = math.sqrt(max(var_free, 0) / f) if f else 0

    rows = [(k, obs[k][0], obs[k][1], obs[k][0] - obs[k][1]) for k in obs]
    return {
        "rows": rows,
        "paid_spins": p, "free_spins": f,
        "se_paid_rtp": se_paid,
        "se_free_rtp": se_free,
        "paid_rtp_within_3sigma":
            abs(obs["base_rtp (paid)"][0] - TARGETS["base_rtp"]) < 3 * se_paid,
        "free_rtp_within_3sigma":
            f == 0 or abs(obs["base_rtp (free)"][0] - TARGETS["base_rtp"]) < 3 * se_free,
    }


def session_aggregate_report(sessions: List[Session]) -> dict:
    """Informational only -- aggregates over session-stopping samples.

    These statistics WILL be biased downward vs the asymptotic targets,
    because sessions that bust or cash out with paid losses 'stranded'
    on the bar produce no bonus from those losses. The bias is real,
    expected, and is part of what the visualization is meant to surface
    (sessions are finite; the bar doesn't always finish filling)."""
    a = _aggregate(sessions)
    p = a["paid_spins"]
    if p == 0:
        return {"error": "no paid spins"}
    obs = dict(
        free_per_spin = a["free_spins"] / p,
        feature_rtp   = a["free_payout"] / p,
        total_rtp     = (a["paid_payout"] + a["free_payout"]) / p,
    )
    rows = []
    for k in obs:
        rows.append((k, obs[k], TARGETS[k], obs[k] - TARGETS[k]))
    return {"rows": rows, "paid_spins": p, "free_spins": a["free_spins"]}


def long_run_check(n_paid_spins: int = 200_000, seed: int = 42) -> dict:
    """Verify the asymptotic math (free_per_spin, feature_rtp, total_rtp)
    by running a single 'session' with bankroll so large the stop rules
    never fire. Equivalent in spirit to mc_simulate.py's headline test.

    Should pass the 3-sigma gate on total_rtp."""
    # Big enough bankroll to never bust; cashout at 1.5x means we'd cash
    # out if we got to 1.5x. Disable both: huge bankroll + huge cashout
    # multiplier ensures we run the full n_paid_spins.
    huge_bankroll = float(n_paid_spins) * 10
    huge_cashout  = 1e12  # effectively no cashout
    s = simulate_session(
        starting_bankroll=huge_bankroll,
        cashout_multiplier=huge_cashout / huge_bankroll,
        rng=random.Random(seed),
        seed=seed,
    )
    # Slice to exactly n_paid_spins worth of paid-spin records (plus their
    # associated free spins).
    paid_seen = 0
    cutoff = len(s.log)
    for i, r in enumerate(s.log):
        if not r.is_free:
            paid_seen += 1
            if paid_seen > n_paid_spins:
                cutoff = i
                break
    s_log = s.log[:cutoff]

    paid = sum(1 for r in s_log if not r.is_free)
    free = sum(1 for r in s_log if r.is_free)
    p_pay = sum(r.payout for r in s_log if not r.is_free)
    f_pay = sum(r.payout for r in s_log if r.is_free)
    p_sq  = sum(r.payout * r.payout for r in s_log if not r.is_free)
    f_sq  = sum(r.payout * r.payout for r in s_log if r.is_free)
    obs = dict(
        free_per_spin = free / paid,
        feature_rtp   = f_pay / paid,
        total_rtp     = (p_pay + f_pay) / paid,
    )
    # SE approximation: paid-variance + free-variance contribution.
    var_paid = p_sq / paid - (p_pay / paid) ** 2
    var_free = f_sq / paid   # E[Y^2] where Y is free-spin payout per paid spin
    se = math.sqrt(max(var_paid + var_free, 0) / paid)
    rows = []
    for k in obs:
        rows.append((k, obs[k], TARGETS[k], obs[k] - TARGETS[k]))
    return {
        "rows": rows,
        "paid_spins": paid, "free_spins": free,
        "total_rtp_se_approx": se,
        "total_rtp_3sigma_lo": obs["total_rtp"] - 3 * se,
        "total_rtp_3sigma_hi": obs["total_rtp"] + 3 * se,
        "rtp_within_3sigma":
            abs(obs["total_rtp"] - TARGETS["total_rtp"]) < 3 * se,
    }


def _print_rows(title: str, rows, extras: str = "") -> None:
    print(title)
    print(f"{'metric':<22}{'observed':>14}{'target':>14}{'err':>12}")
    print("-" * 62)
    for k, obs, tgt, err in rows:
        print(f"{k:<22}{obs:>14.6f}{tgt:>14.6f}{err:>+12.6f}")
    if extras:
        print(extras)
    print()


def run_sanity_suite(sessions: List[Session], n_long_run: int = 200_000) -> bool:
    """Full sanity suite. Returns True iff all hard gates pass."""
    print("=== 1. PER-SPIN RULE CHECK (must pass within 3sigma) ===")
    print("    These verify each spin's outcome distribution. Independent of session stops.")
    print()
    psc = per_spin_check(sessions)
    if "error" in psc:
        print("  ", psc["error"]); return False
    _print_rows(
        f"  Over {psc['paid_spins']:,} paid + {psc['free_spins']:,} free spins:",
        psc["rows"],
        f"  paid base_rtp SE: {psc['se_paid_rtp']:.6f}   "
        f"free base_rtp SE: {psc['se_free_rtp']:.6f}",
    )
    gate1 = psc["paid_rtp_within_3sigma"] and psc["free_rtp_within_3sigma"]
    print(f"  Per-spin rule gate: {'PASS' if gate1 else 'FAIL'}")
    print()

    print("=== 2. LONG-RUN CHECK (must pass within 3sigma) ===")
    print("    Single no-stop session, equivalent to mc_simulate.py's headline test.")
    print(f"    n = {n_long_run:,} paid spins")
    print()
    lrc = long_run_check(n_paid_spins=n_long_run)
    _print_rows(
        f"  Over {lrc['paid_spins']:,} paid + {lrc['free_spins']:,} free spins:",
        lrc["rows"],
        f"  Total-RTP approx SE: {lrc['total_rtp_se_approx']:.6f}   "
        f"3-sigma window: [{lrc['total_rtp_3sigma_lo']:.6f}, "
        f"{lrc['total_rtp_3sigma_hi']:.6f}]",
    )
    gate2 = lrc["rtp_within_3sigma"]
    print(f"  Long-run gate: {'PASS' if gate2 else 'FAIL'}")
    print()

    print("=== 3. SESSION-AGGREGATED (informational; truncation-biased low) ===")
    print("    Sessions that bust/cash out leave paid losses 'stranded' on the bar.")
    print("    free_per_spin, feature_rtp, total_rtp will read LOW vs targets here.")
    print("    This is real session behavior, not a bug.")
    print()
    sar = session_aggregate_report(sessions)
    _print_rows(
        f"  Over {sar['paid_spins']:,} paid + {sar['free_spins']:,} free spins:",
        sar["rows"],
    )

    overall = gate1 and gate2
    print(f"OVERALL: {'PASS -- per-spin log is consistent with verified math' if overall else 'FAIL -- investigate before building viz'}")
    return overall


# -----------------------------------------------------------------------------
# CLI: run a quick sanity check on a chunk of $20 sessions.
# -----------------------------------------------------------------------------

def main():
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42
    bankroll = float(sys.argv[3]) if len(sys.argv) > 3 else 20.0

    print(f"VOID SLOTS -- session generator")
    print(f"  starting bankroll: ${bankroll:.2f}")
    print(f"  sessions: {n:,}; seed: {seed}")
    print()
    t0 = time.time()
    sessions = simulate_many(bankroll, n_sessions=n, seed=seed)
    elapsed = time.time() - t0
    total_paid = sum(s.paid_spins for s in sessions)
    total_free = sum(s.free_spins for s in sessions)
    print(f"Simulated in {elapsed:.1f}s "
          f"({total_paid:,} paid + {total_free:,} free spins)")
    print()
    run_sanity_suite(sessions, n_long_run=200_000)


if __name__ == "__main__":
    main()
