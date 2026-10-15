#!/usr/bin/env python3
"""
bake_gravity_bust_motion.py
Replaces the symmetric zero-gravity sine waves on `boob_r_ctl` and `boob_l_ctl` in `<ch>/out/rig/motion.json`
with the steady-state periodic solution of a physically-based Gravity + Non-linear J-Curve Elastic Tension ODE:

  m * y'' + c * y' + F_tension(y - y_sag) = F_chest_inertia(t) - m * g

Features:
1. Downward Gravity Acceleration (-g): Slow lift during inhalation, followed by a rapid parabolic free-fall drop
   when the chest peaks and exhales.
2. Non-linear J-Curve Bottom Tension (Cooper's ligament / bra support): Soft linear stiffness above equilibrium,
   transitioning into a steep cubic hyperelastic tension wall (`-k_down * dy - k3 * dy^3`) at the bottom of the drop,
   producing a crisp elastic snap rebound instead of a weightless sine turnaround.
3. Underdamped Elastic Ring-out: 2.5 to 3.5 lively secondary bounces per breathing cycle at each character's
   mass-dependent natural frequency.
4. Volume-Preserving 3D Squash & Stretch (`scalex`, `scaley`): Bottom tension impact squashes vertical height and
   plumps horizontal volume (`scalex > 1, scaley < 1`), while downward free-fall slightly stretches `scaley`.
5. 5-Tier Bust Size Variation across the 5 characters (`roa` -> `naru` -> `luna` -> `nova` -> `jinni`).
"""
import json
import os
import sys
import numpy as np

FAMILY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 5-tier bust physics presets matched to each character's bust mesh radius & silhouette:
# luna (r=22, band=36) -> nova (r=23, band=36) -> naru (r=24, band=38) -> jinni (r=25, band=39) -> roa (r=28, band=44)
BUST_PRESETS = {
    "luna": {
        "tier": "Tier 1 — Light-Perky (Crisp High-Tension Bounce, r=22)",
        "mass": 0.82,
        "amp_drop": 3.0,
        "sag": 0.75,
        "n_harm": 3.50,
        "zeta": 0.138,
        "k3": 0.22,
        "squash": 0.020,
        "x_ratio": -0.24,
        "phase_r": 0.045,
        "phase_l": 0.068,
        "l_scale": 0.90,
    },
    "nova": {
        "tier": "Tier 2 — Medium-Firm (Tailored Vest Support + Snappy Rebound, r=23)",
        "mass": 1.00,
        "amp_drop": 3.8,
        "sag": 1.05,
        "n_harm": 3.25,
        "zeta": 0.122,
        "k3": 0.19,
        "squash": 0.026,
        "x_ratio": -0.26,
        "phase_r": 0.052,
        "phase_l": 0.078,
        "l_scale": 0.90,
    },
    "naru": {
        "tier": "Tier 3 — Medium-Full (Soft Knit Sweater Gravity Drop + Lively Bounce, r=24)",
        "mass": 1.18,
        "amp_drop": 4.2,
        "sag": 1.20,
        "n_harm": 3.05,
        "zeta": 0.110,
        "k3": 0.16,
        "squash": 0.030,
        "x_ratio": -0.26,
        "phase_r": 0.060,
        "phase_l": 0.088,
        "l_scale": 0.91,
    },
    "jinni": {
        "tier": "Tier 4 — Heavy-Glamour (Off-Shoulder Corset Gravity Fall + Plump Whip, r=25)",
        "mass": 1.35,
        "amp_drop": 4.5,
        "sag": 1.30,
        "n_harm": 2.85,
        "zeta": 0.100,
        "k3": 0.14,
        "squash": 0.034,
        "x_ratio": -0.26,
        "phase_r": 0.068,
        "phase_l": 0.098,
        "l_scale": 0.92,
    },
    "roa": {
        "tier": "Tier 5 — Max-Volume Glamour (Deepest Gravity Sag + Rich J-Curve Ring-out, r=28)",
        "mass": 1.52,
        "amp_drop": 4.9,
        "sag": 1.45,
        "n_harm": 2.65,
        "zeta": 0.092,
        "k3": 0.125,
        "squash": 0.038,
        "x_ratio": -0.27,
        "phase_r": 0.075,
        "phase_l": 0.110,
        "l_scale": 0.93,
    },
}


def solve_periodic_ode(T, amp_drop, sag, n_harm, zeta, k3, phase_shift, n_keys=40):
    """
    Integrates the non-linear gravity + J-curve tension ODE over 10 periods to converge
    to the exact periodic steady-state trajectory, then samples `n_keys + 1` points
    with exact derivatives for Cubic Hermite Bezier curve encoding.
    """
    steps = n_keys * 80  # 3200 substeps per period
    dt = T / steps
    w0 = 2.0 * np.pi / T
    wn = n_harm * w0
    c = 2.0 * zeta * wn
    k_up = (0.72 * wn) ** 2
    k_down = (1.28 * wn) ** 2

    y = -sag
    v = 0.0

    for p in range(10):
        ys = np.zeros(steps, dtype=np.float64)
        vs = np.zeros(steps, dtype=np.float64)
        accs = np.zeros(steps, dtype=np.float64)
        for i in range(steps):
            t = i * dt
            u = ((t / T - phase_shift) % 1.0 + 1.0) % 1.0
            theta = 2.0 * np.pi * u
            # Breathing chest lift + sharp downward gravity release when chest drops from inhalation crest
            grav_pulse = (
                -1.85 * np.exp(-0.5 * ((u - 0.40) / 0.072) ** 2)
                - 0.55 * np.exp(-0.5 * ((u - 0.78) / 0.095) ** 2)
                + 0.70 * np.sin(theta)
            )
            drive = amp_drop * (wn ** 2) * grav_pulse
            dy = y - (-sag)
            if dy >= 0.0:
                f_restore = -k_up * dy
            else:
                f_restore = -k_down * dy - k3 * (wn ** 2) * (dy ** 3)
            acc = f_restore - c * v + drive
            ys[i] = y
            vs[i] = v
            accs[i] = acc
            v += acc * dt
            y += v * dt

    # Normalize so dynamic excursion matches target amp_drop and settles around -sag
    y_mean = np.mean(ys)
    y_centered = ys - y_mean
    scale = (amp_drop * 1.95) / (np.max(y_centered) - np.min(y_centered) + 1e-8)
    ys = -sag + y_centered * scale
    vs = vs * scale
    accs = accs * scale

    return ys, vs, accs, steps


def build_hermite_track(bone, prop, T, ts_sub, vals_sub, derivs_sub, n_keys=40):
    steps = len(vals_sub)
    stride = steps // n_keys
    keys = []
    for k in range(n_keys + 1):
        idx = (k * stride) % steps
        t = T if k == n_keys else round((T * k) / n_keys, 6)
        v = round(float(vals_sub[idx]), 4)
        key = {"t": t, "v": [v]}
        if k < n_keys:
            idx1 = ((k + 1) * stride) % steps
            t1 = T if (k + 1) == n_keys else round((T * (k + 1)) / n_keys, 6)
            v1 = round(float(vals_sub[idx1]), 4)
            m0 = float(derivs_sub[idx])
            m1 = float(derivs_sub[idx1])
            dt = t1 - t
            c1x = round(t + dt / 3.0, 6)
            c1y = round(v + (m0 * dt) / 3.0, 4)
            c2x = round(t1 - dt / 3.0, 6)
            c2y = round(v1 - (m1 * dt) / 3.0, 4)
            key["curve"] = [c1x, c1y, c2x, c2y]
        keys.append(key)
    return {"bone": bone, "property": prop, "keys": keys}


def bake_character(ch):
    preset = BUST_PRESETS[ch]
    motion_path = os.path.join(FAMILY_DIR, ch, "out", "rig", "motion.json")
    if not os.path.exists(motion_path):
        print(f"Skipping {ch}: {motion_path} not found")
        return

    with open(motion_path, "r") as f:
        motion = json.load(f)

    idle = motion["animations"]["idle"]
    T = float(idle["duration"])
    n_keys = 40  # Exactly 1 key per 12fps frame (40 frames in 3.3333s)

    # Remove old symmetric sine tracks on boob_r_ctl and boob_l_ctl
    kept_tracks = [
        tr for tr in idle["tracks"]
        if tr.get("bone") not in ("boob_r_ctl", "boob_l_ctl", "boob_r", "boob_l")
    ]

    for side, bone_name, ph, side_scale in [
        ("r", "boob_r_ctl", preset["phase_r"], 1.0),
        ("l", "boob_l_ctl", preset["phase_l"], preset["l_scale"]),
    ]:
        amp = preset["amp_drop"] * side_scale
        sag = preset["sag"] * side_scale
        ys, vs, accs, steps = solve_periodic_ode(
            T=T,
            amp_drop=amp,
            sag=sag,
            n_harm=preset["n_harm"],
            zeta=preset["zeta"],
            k3=preset["k3"],
            phase_shift=ph,
            n_keys=n_keys,
        )
        dt = T / steps

        # Horizontal sway coupled to vertical gravity drop & rebound
        xs = preset["x_ratio"] * (ys - (-sag))
        vxs = preset["x_ratio"] * vs

        # Volume-preserving 3D Squash & Stretch (`scalex`, `scaley`):
        # When y drops below -sag (bottom tension impact), breast squashes vertically (scaley < 1)
        # and plumps horizontally/outward (scalex > 1). During rapid downward fall (v < 0), slightly stretches vertically.
        dy_norm = (ys - (-sag)) / (amp + 1e-6)
        v_norm = vs / (np.max(np.abs(vs)) + 1e-6)
        squash_amp = preset["squash"] * side_scale
        sx = 1.0 - squash_amp * (0.85 * dy_norm - 0.25 * v_norm)
        sy = 1.0 + squash_amp * (0.95 * dy_norm - 0.30 * v_norm)
        # Time derivatives of sx, sy via central differences on periodic array
        dsx = (np.roll(sx, -1) - np.roll(sx, 1)) / (2.0 * dt)
        dsy = (np.roll(sy, -1) - np.roll(sy, 1)) / (2.0 * dt)

        kept_tracks.append(build_hermite_track(bone_name, "translatey", T, None, ys, vs, n_keys))
        kept_tracks.append(build_hermite_track(bone_name, "translatex", T, None, xs, vxs, n_keys))
        kept_tracks.append(build_hermite_track(bone_name, "scalex", T, None, sx, dsx, n_keys))
        kept_tracks.append(build_hermite_track(bone_name, "scaley", T, None, sy, dsy, n_keys))

    idle["tracks"] = kept_tracks
    with open(motion_path, "w") as f:
        json.dump(motion, f, indent=1)
        f.write("\n")

    print(f"[{ch}] Baked Gravity + J-Curve Tension bust tracks ({preset['tier']}): drop={preset['amp_drop']}px, sag=-{preset['sag']}px, squash={preset['squash']*100:.1f}%")


if __name__ == "__main__":
    targets = sys.argv[1:] if len(sys.argv) > 1 else ["roa", "naru", "luna", "nova", "jinni"]
    for ch in targets:
        bake_character(ch)
