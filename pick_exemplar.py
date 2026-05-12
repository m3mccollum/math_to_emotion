"""One-shot example finder. Generates many $20 sessions, filters by
structural readability, and prints the top candidates with enough
detail to pick by hand. Not part of the deliverable; just a tool.
(Filename kept as pick_exemplar.py to avoid a rename; the prose was
updated to match the rest of the deliverable.)"""

import random
from session_generator import simulate_session
from emotional_model import score_emotions


def candidate_score(session, traj) -> float:
    """Composite readability score. Higher is better. Designed to surface
    sessions with visible tension, visible elation, and at least one
    near-miss -- so all three emotional channels do something legible.
    """
    s = 0.0
    s += min(1.0, max(traj.tension))                   # tension peak height
    s += min(1.0, max(traj.elation))                   # elation peak height
    s += 0.3 * sum(1 for r in session.log if r.is_near_miss)   # near-miss reward
    # Penalize very short and very long sessions.
    n = session.paid_spins
    if n < 40 or n > 120:
        s -= 1.0
    # Prefer 1-2 INVERTs (cleanest narrative)
    if session.features_triggered == 1:
        s += 0.5
    elif session.features_triggered == 2:
        s += 0.3
    return s


def main():
    n_to_sample = 500
    master = random.Random(2026)
    candidates = []
    for i in range(n_to_sample):
        seed = master.getrandbits(64)
        sess = simulate_session(20.0, rng=random.Random(seed), seed=seed)
        traj = score_emotions(sess)
        # Hard filters
        if sess.features_triggered < 1 or sess.features_triggered > 3:
            continue
        if sess.paid_spins < 40 or sess.paid_spins > 120:
            continue
        score = candidate_score(sess, traj)
        candidates.append((score, seed, sess, traj))

    candidates.sort(key=lambda x: -x[0])

    print(f"Sampled {n_to_sample}; {len(candidates)} passed hard filters")
    print()
    print(f"{'rank':>4}  {'seed':>20}  {'spins':>5}  {'outcome':<8}  "
          f"{'end$':>6}  {'INV':>3}  {'NM':>3}  "
          f"{'maxT':>5}  {'maxE':>5}  {'maxA':>5}  {'score':>6}")
    print("-" * 90)
    for rank, (score, seed, sess, traj) in enumerate(candidates[:12], 1):
        nm = sum(1 for r in sess.log if r.is_near_miss)
        print(f"{rank:>4}  {seed:>20}  {sess.paid_spins:>5}  {sess.outcome:<8}  "
              f"${sess.ending_bankroll:>5.2f}  {sess.features_triggered:>3}  {nm:>3}  "
              f"{max(traj.tension):>5.3f}  {max(traj.elation):>5.3f}  "
              f"{max(traj.anticipation):>5.3f}  {score:>6.3f}")

    print()
    print("Drilling into rank 1...")
    score, seed, sess, traj = candidates[0]
    print(f"  seed: {seed}")
    print(f"  spins (paid+free): {sess.paid_spins} + {sess.free_spins} = {sess.total_spins}")
    print(f"  duration: {sess.duration_s:.1f}s ({sess.duration_s/60:.1f} min)")
    print(f"  bankroll: ${sess.starting_bankroll:.2f} -> peak ${sess.peak_bankroll:.2f} "
          f"-> end ${sess.ending_bankroll:.2f}")
    print(f"  outcome: {sess.outcome}")
    print(f"  INVERTs at spin indices: {sess.bonus_spin_indices}")
    print(f"  INVERT regions (start..end spin_index): {sess.invert_regions}")
    print(f"  longest dry spell: {sess.longest_dry_spell}")
    print(f"  near-misses: {sum(1 for r in sess.log if r.is_near_miss)}")
    print(f"  max single payout: ${sess.max_single_win:.2f}")
    print()
    print(f"  peak anticipation: {traj.anticipation[traj.peak_anticipation_idx]:.3f} "
          f"at spin {traj.spin_index[traj.peak_anticipation_idx]}")
    print(f"  peak tension:      {traj.tension[traj.peak_tension_idx]:.3f} "
          f"at spin {traj.spin_index[traj.peak_tension_idx]}")
    print(f"  peak elation:      {traj.elation[traj.peak_elation_idx]:.3f} "
          f"at spin {traj.spin_index[traj.peak_elation_idx]}")


if __name__ == "__main__":
    main()
