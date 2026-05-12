"""
VOID SLOTS -- emotional-state model for the math-to-emotion visualization
=========================================================================

A stated, opinionated, three-channel heuristic. NOT a measurement.
NOT a prediction of any individual player's affect. The companion text
for the visualization makes this disclaimer explicit.

Channels
--------

  Anticipation (0..1)
    The build-up signal. Tracks the INVERT progress bar, since the bar
    IS the anticipation mechanic in VOID SLOTS. Near-misses produce a
    brief bump (Clark et al. 2009 on near-miss reward-circuit activation).
    INVERT activation 'consumes' accumulated anticipation: bar resets to
    zero and any near-miss residual is cleared.

  Tension (0..1)
    The bad-stretch signal. Two drivers:
      - dry-spell length (saturating at the Schilling-expected longest)
      - bankroll drift below the session start
    Pure function of current state -- no history-dependent decay --
    because both drivers already drop on a win, giving automatic relief.

  Elation (0..1)
    The win-spike signal. Each spin: decay-then-add.
      - log-scaled spike on any winning payout (so $50 isn't 10x the
        felt joy of $5)
      - flat +0.3 bump on INVERT activation, regardless of the bonus
        outcome -- the visual transformation itself has affect
      - exponential decay (halflife ~1.4 spins at decay=0.6)

What this model does NOT claim
-------------------------------

  - This is one engaged player, not a population.
  - No cross-session memory (no 'I'm down on the day' baseline).
  - No auto-spin compression (manual play only).
  - No cognitive biases (illusion of control, gambler's fallacy).
  - VOID SLOTS doesn't have sub-bet wins, so 'losses disguised as wins'
    is not a lever here.

All coefficients live on EmotionConfig and can be tuned without touching
the scoring loop. Defaults were hand-picked to produce a readable
trajectory at the $20 baseline; they are not derived from any dataset.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import List, Optional, Dict

from session_generator import Session, SpinRecord, BONUS_TRIGGER_LOSSES, BET


# -----------------------------------------------------------------------------
# Tunable coefficients. Adjust here, not in the loop.
# -----------------------------------------------------------------------------

@dataclass
class EmotionConfig:
    # --- Anticipation ---
    bar_fill_weight:     float = 0.7    # bar at 12/12 gives 0.7 anticipation
    near_miss_bump:      float = 0.15   # added on each near-miss
    near_miss_decay:     float = 0.7    # multiplied per subsequent spin

    # --- Tension ---
    dry_spell_saturation: int   = 15    # dry-spell-driven tension caps at this length
    dry_spell_weight:     float = 0.5   # max contribution from dry spells
    bankroll_dip_weight:  float = 0.4   # max contribution from bankroll-below-start

    # --- Elation ---
    elation_log_coeff:    float = 0.2   # spike = log_coeff * log2(1 + payout/bet)
    elation_invert_bump:  float = 0.3   # additive on INVERT activation
    elation_decay:        float = 0.6   # per-spin multiplicative decay


# -----------------------------------------------------------------------------
# Scoring
# -----------------------------------------------------------------------------

@dataclass
class EmotionTrajectory:
    """The three emotional channels and a few moments-of-interest.

    Each channel is a list of floats aligned to session.log -- one
    value per SpinRecord. Components (the named drivers behind each
    channel) are also exposed for debugging and for annotation
    callouts like 'tension here is mostly bankroll-driven'.
    """
    spin_index:   List[int]
    anticipation: List[float]
    tension:      List[float]
    elation:      List[float]

    # Decomposed drivers (same length, useful for tuning + annotations)
    anticipation_bar:        List[float]
    anticipation_near_miss:  List[float]
    tension_dry:             List[float]
    tension_bankroll:        List[float]

    # Moments of interest -- indices into the spin_index list
    peak_anticipation_idx: int
    peak_tension_idx:      int
    peak_elation_idx:      int


def score_emotions(session: Session, config: Optional[EmotionConfig] = None) -> EmotionTrajectory:
    """Compute the three-channel emotional trajectory for a session.

    The trajectory is aligned to session.log -- one value per spin
    (paid + free). The viz can plot it directly against spin_index or
    cumulative_time_s.
    """
    cfg = config if config is not None else EmotionConfig()
    n = len(session.log)

    anticipation     = [0.0] * n
    tension          = [0.0] * n
    elation          = [0.0] * n
    ant_bar          = [0.0] * n
    ant_nm           = [0.0] * n
    ten_dry          = [0.0] * n
    ten_bank         = [0.0] * n

    near_miss_residual = 0.0
    prev_elation = 0.0

    for i, r in enumerate(session.log):
        # --- TENSION: pure state function ---
        dry_term = cfg.dry_spell_weight * min(
            r.dry_spell_length_after / cfg.dry_spell_saturation, 1.0
        )
        bankroll_dip = max(0.0, 1.0 - r.bankroll_after / session.starting_bankroll)
        bankroll_term = cfg.bankroll_dip_weight * bankroll_dip
        ten_dry[i]  = dry_term
        ten_bank[i] = bankroll_term
        tension[i] = min(1.0, dry_term + bankroll_term)

        # --- ANTICIPATION: bar fill + near-miss residual ---
        # Decay residual BEFORE adding this spin's contribution -- a
        # near-miss spin should have its full bump on the same spin.
        near_miss_residual *= cfg.near_miss_decay
        if r.is_near_miss:
            near_miss_residual += cfg.near_miss_bump
        # INVERT consumes prior anticipation, including near-miss residual.
        if r.bonus_triggered:
            near_miss_residual = 0.0
        # Bar fill is already 0 during free spins and immediately after
        # INVERT, so the 'hard reset' is automatic for the bar term.
        bar_term = cfg.bar_fill_weight * (r.bar_fill_after / BONUS_TRIGGER_LOSSES)
        ant_bar[i] = bar_term
        ant_nm[i]  = near_miss_residual
        anticipation[i] = min(1.0, bar_term + near_miss_residual)

        # --- ELATION: decay + win spike + INVERT bump ---
        e = prev_elation * cfg.elation_decay
        if r.is_win:
            # log2(1+ratio): $1.50 -> 1.32, $5 -> 2.58, $50 -> 5.67, $100 -> 6.66
            # Scaled by 0.2 and capped at 1.0:    0.26, 0.52, 1.0, 1.0
            ratio = r.payout / BET
            e += min(1.0, cfg.elation_log_coeff * math.log2(1.0 + ratio))
        if r.bonus_triggered:
            e += cfg.elation_invert_bump
        e = min(1.0, e)
        elation[i] = e
        prev_elation = e

    # Moments of interest.
    peak_ant = max(range(n), key=lambda i: anticipation[i]) if n else 0
    peak_ten = max(range(n), key=lambda i: tension[i])      if n else 0
    peak_ela = max(range(n), key=lambda i: elation[i])      if n else 0

    return EmotionTrajectory(
        spin_index   = [r.spin_index for r in session.log],
        anticipation = anticipation,
        tension      = tension,
        elation      = elation,
        anticipation_bar       = ant_bar,
        anticipation_near_miss = ant_nm,
        tension_dry            = ten_dry,
        tension_bankroll       = ten_bank,
        peak_anticipation_idx  = peak_ant,
        peak_tension_idx       = peak_ten,
        peak_elation_idx       = peak_ela,
    )


# -----------------------------------------------------------------------------
# Self-test: score a quick synthetic session and print a summary.
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    from session_generator import simulate_session
    import random
    sess = simulate_session(20.0, rng=random.Random(42), seed=42)
    traj = score_emotions(sess)
    print(f"Session: {len(sess.log)} spins, outcome={sess.outcome}, "
          f"bankroll ${sess.starting_bankroll:.0f} -> ${sess.ending_bankroll:.2f}")
    print(f"  Features triggered: {sess.features_triggered}")
    print(f"  Peak anticipation:  {traj.anticipation[traj.peak_anticipation_idx]:.3f} "
          f"at spin {traj.spin_index[traj.peak_anticipation_idx]}")
    print(f"  Peak tension:       {traj.tension[traj.peak_tension_idx]:.3f} "
          f"at spin {traj.spin_index[traj.peak_tension_idx]}")
    print(f"  Peak elation:       {traj.elation[traj.peak_elation_idx]:.3f} "
          f"at spin {traj.spin_index[traj.peak_elation_idx]}")
