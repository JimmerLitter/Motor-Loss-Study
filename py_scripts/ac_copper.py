"""
ac_copper.py -- AC copper loss mechanisms + winding geometry reconciliation.

Covers what 3*I^2*R does NOT: skin effect, proximity effect (Dowell), and the
slot-geometry/fill-factor relationships that actually govern copper loss.

Run:  python ac_copper.py
"""
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from config import MOTOR, ALPHA_CU_PER_C
from plot_losses import SURFACE, INK, INK_2, MUTED, C_COPPER, style
from losses import elec_freq, copper_loss

RHO_20_OHM_M = 1.724e-8    # copper resistivity @ 20 C
MU0 = 4e-7 * np.pi


# ---------------------------------------------------------------- skin effect
"""Copper resistivity [ohm*m] at temperature T_C."""
def resistivity(T_C=20.0):
    return RHO_20_OHM_M * (1.0 + ALPHA_CU_PER_C * (T_C - 20.0))


"""Skin depth [m]. delta = sqrt(rho / (pi f mu0))."""
def skin_depth(f_Hz, T_C=20.0):
    return np.sqrt(resistivity(T_C) / (np.pi * f_Hz * MU0))


# ----------------------------------------------------------- proximity effect
"""Dowell R_ac/R_dc for an n-layer winding.

Round wire is mapped to the equivalent-area square foil that Dowell's 1D
derivation assumes: h = d * sqrt(pi)/2.

The (m^2 - 1) term is the proximity contribution -- it grows with the
SQUARE of layer count, which is why deep slots and thick conductors are
the dangerous combination, and why litz/transposition exist."""
def dowell_ratio(d_bare_mm, f_Hz, n_layers, T_C=100.0):
    delta = skin_depth(f_Hz, T_C)
    h = (d_bare_mm * 1e-3) * np.sqrt(np.pi) / 2.0
    x = h / delta
    if x < 1e-6:
        return 1.0
    skin = (np.sinh(2 * x) + np.sin(2 * x)) / (np.cosh(2 * x) - np.cos(2 * x))
    prox = (np.sinh(x) - np.sin(x)) / (np.cosh(x) + np.cos(x))
    return x * (skin + (2.0 / 3.0) * (n_layers ** 2 - 1) * prox)


"""AC-corrected copper loss [W]: DC copper loss * Dowell R_ac/R_dc,
at this motor's confirmed wire gauge and winding layer count."""
def ac_copper_loss(T_nm, rpm, m, temp_c):
    P_cu_dc_w = copper_loss(T_nm, m, temp_c)
    f_hz = elec_freq(rpm, m.pole_pairs)
    ratio = dowell_ratio(m.wire_diameter_mm, f_hz, m.winding_layers, temp_c)
    return P_cu_dc_w * ratio


# ------------------------------------------------------- winding / fill factor
"""Invert R_ph = rho*N_ph*L_mean/A_cond  ->  A_cond [m^2]."""
def conductor_area_from_R(R_ph_ohm, N_ph, L_mean_m, T_C=20.0):
    return resistivity(T_C) * N_ph * L_mean_m / R_ph_ohm


"""Net (bare-copper) fill factor. NOT gross/wire fill -- use net for R."""
def fill_factor(A_cond_m2, turns_per_slot, A_slot_m2):
    return turns_per_slot * A_cond_m2 / A_slot_m2


"""Reconcile datasheet R_ph against measured slot geometry.

Concentrated winding (one coil per tooth): each slot holds two coil-sides,
while each phase carries (slots/phases) coils in series. Confusing those
two counts is the classic factor-of-2 error."""
def solve_winding(R_ph_ohm, A_slot_m2, L_mean_m, n_per_coil, slots, phases,
                  coil_sides_per_slot=2):
    N_ph = (slots / phases) * n_per_coil
    A_cond_m2 = conductor_area_from_R(R_ph_ohm, N_ph, L_mean_m)
    k_f = fill_factor(A_cond_m2, coil_sides_per_slot * n_per_coil, A_slot_m2)
    return N_ph, A_cond_m2, k_f


"""Nearest AWG size for a given bare-conductor cross-sectional area."""
def awg_from_area(area_mm2):
    d_mm = 2 * np.sqrt(area_mm2 / np.pi)
    return -39 * np.log(d_mm / 0.127) / np.log(92) + 36


"""P_cu at fixed torque as a function of fill factor.
Shows fill/slot-area as the real lever -- turn count cancels out (see
print_turn_count_independence())."""
def copper_loss_vs_fill(torque_nm, Kt_nm_per_a, A_slot_m2, L_mean_m, N_ph, k_f,
                        slots, phases):
    A_cond_m2 = k_f * A_slot_m2 / (2 * N_ph / (slots / phases))  # per-conductor area
    R_ohm = resistivity(20.0) * N_ph * L_mean_m / A_cond_m2
    I_a = torque_nm / Kt_nm_per_a
    return 3 * I_a ** 2 * R_ohm


# --------------------------------------------------------- report tables
def print_skin_depth_table(m):
    print("=" * 66)
    print("SKIN DEPTH vs SPEED  (winding at 100 C)")
    print("=" * 66)
    print(f"{'rpm':>8} {'f_elec[Hz]':>12} {'delta[mm]':>12}")
    for rpm in (1000, 3240, 5000, 6480):
        f_hz = elec_freq(rpm, m.pole_pairs)
        print(f"{rpm:8.0f} {f_hz:12.1f} {skin_depth(f_hz, 100.0)*1e3:12.2f}")


def print_dowell_table(m):
    print("\n" + "=" * 66)
    print("DOWELL R_ac/R_dc @ 756 Hz (max speed), 100 C")
    print("=" * 66)
    print(f"{'AWG':>5} {'d[mm]':>8} " + "".join(f"{n:>8}L" for n in (2, 4, 6, 8, 10)))
    for g, d_mm in ((18, m.wire_diameter_mm), (20, 0.812), (22, 0.644),
                    (24, 0.511), (26, 0.405)):
        row = "".join(f"{dowell_ratio(d_mm, 756, n):9.3f}" for n in (2, 4, 6, 8, 10))
        note = "  <- this design (R_ph-reconciled)" if g == 18 else ""
        print(f"{g:5d} {d_mm:8.3f} " + row + note)


def print_winding_reconciliation(m):
    print("\n" + "=" * 66)
    print("WINDING RECONCILIATION  (R_ph + FEMM slot area -> fill factor)")
    print("=" * 66)
    print(f"A_slot = {m.slot_area_m2*1e6:.2f} mm^2   R_ph = {m.R_ph_ohm} ohm   "
          f"{m.slots}N{2*m.pole_pairs}P assumed\n")
    print(f"n/coil = {m.winding_layers} is CONFIRMED for this winding. Solving conductor size")
    print("from measured R_ph at that turn count (not the unreconciled '12 AWG'")
    print("figure found online -- see note in config.py) gives the design gauge:\n")
    print(f"{'n/coil':>7} {'N_ph':>6} {'L_mean':>8} {'A_cond[mm2]':>13} {'AWG':>5} {'k_f':>7}  verdict")
    for n in (4, 5, 6, 7, 8, 9, 10):
        for L_m in (0.060, 0.080):
            N_ph, A_c_m2, k_f = solve_winding(m.R_ph_ohm, m.slot_area_m2, L_m, n,
                                              m.slots, m.phases)
            ok = "plausible" if 0.25 <= k_f <= 0.65 else ("TOO LOW" if k_f < 0.25 else "TOO HIGH")
            note = "  <- confirmed n/coil" if n == m.winding_layers else ""
            print(f"{n:7d} {N_ph:6.0f} {L_m*1e3:7.0f}mm {A_c_m2*1e6:13.3f} "
                  f"{awg_from_area(A_c_m2*1e6):5.0f} {k_f:7.3f}  {ok}{note}")


def print_turn_count_independence(m):
    print("\n" + "=" * 66)
    print("TURN-COUNT INDEPENDENCE of DC copper loss at fixed torque")
    print("=" * 66)
    k_f, L_m = 0.40, 0.080
    print(f"(k_f={k_f}, A_slot={m.slot_area_m2*1e6:.1f} mm^2, T=0.3 Nm, Kt scaled with N)")
    print(f"{'n/coil':>7} {'A_cond[mm2]':>13} {'R_ph[ohm]':>11} {'Kt':>8} {'I[A]':>8} {'P_cu[W]':>9}")
    n_ref, Kt_ref = m.winding_layers, m.Kt_nm_per_a
    for n in (4, 6, 7, 10, 14):
        N_ph = (m.slots / m.phases) * n
        A_c_m2 = k_f * m.slot_area_m2 / (2 * n)
        R_ohm = resistivity(20.0) * N_ph * L_m / A_c_m2
        Kt_n = Kt_ref * n / n_ref
        I_a = 0.3 / Kt_n
        print(f"{n:7d} {A_c_m2*1e6:13.3f} {R_ohm:11.4f} {Kt_n:8.4f} {I_a:8.2f} "
              f"{3*I_a**2*R_ohm:9.2f}")
    print("  -> P_cu constant: R ~ N^2 but I ~ 1/N, so I^2*R cancels.")
    print("     Turn count sets Kv, NOT efficiency.")


def print_fill_factor_lever(m):
    print("\n" + "=" * 66)
    print(f"FILL FACTOR is the real lever (fixed torque, n={m.winding_layers})")
    print("=" * 66)
    n, L_m = m.winding_layers, 0.080
    N_ph = (m.slots / m.phases) * n
    base_w = None
    for k_f in (0.30, 0.35, 0.40, 0.45, 0.50, 0.60):
        A_c_m2 = k_f * m.slot_area_m2 / (2 * n)
        R_ohm = resistivity(20.0) * N_ph * L_m / A_c_m2
        I_a = 0.3 / m.Kt_nm_per_a
        P_w = 3 * I_a ** 2 * R_ohm
        if base_w is None:
            base_w = P_w
        print(f"  k_f={k_f:.2f} -> R_ph={R_ohm:.4f} ohm, P_cu={P_w:6.2f} W  "
              f"({100*(P_w-base_w)/base_w:+6.1f}%)")


# --------------------------------------------------------- sweep figure
"""Conclusive figure: where does R_ac/R_dc actually move?

Two panels -- vs. frequency (several gauges, this design's layer count)
and vs. wire thickness (several layer counts, this design's worst-case
frequency) -- to show R_ac/R_dc stays ~1.0x inside this design's envelope
and only moves once frequency or wire gauge moves outside it."""
def save_ac_copper_sweep_figure(m):
    F_OP_LO_HZ, F_OP_HI_HZ = 378.0, 756.0    # this design's electrical frequency range

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(11.6, 4.6))
    fig.patch.set_facecolor(SURFACE)

    f_sweep_hz = np.logspace(np.log10(50), np.log10(5000), 200)   # well past 756
    for label, d_mm, color in (('AWG 18 (this design)', m.wire_diameter_mm, C_COPPER),
                               ('AWG 14 (thick ref.)', 1.628, INK),
                               ('AWG 10 (very thick ref.)', 2.588, MUTED)):
        ratio = [dowell_ratio(d_mm, f_hz, m.winding_layers, 100.0) for f_hz in f_sweep_hz]
        axL.plot(f_sweep_hz, ratio, color=color, linewidth=2.0, label=label)
    axL.axvspan(F_OP_LO_HZ, F_OP_HI_HZ, color=C_COPPER, alpha=0.10, zorder=0)
    axL.annotate("this design's\noperating range\n(378-756 Hz)",
                xy=(np.sqrt(F_OP_LO_HZ * F_OP_HI_HZ), 1.0),
                xycoords=('data', 'axes fraction'),
                xytext=(0, -6), textcoords='offset points',
                fontsize=8, color=C_COPPER, linespacing=1.3, ha='center', va='top')
    axL.set_xscale('log')
    axL.set_xlabel('Electrical frequency [Hz]', color=INK_2, fontsize=10)
    axL.set_ylabel('R_ac / R_dc', color=INK_2, fontsize=10)
    axL.set_title(f'vs. frequency  ({m.winding_layers}-layer slot)',
                  color=INK, fontsize=10, loc='left')
    style(axL)
    axL.legend(fontsize=8, frameon=False, labelcolor=INK_2)

    d_sweep_mm = np.linspace(0.2, 3.0, 200)
    for n, color in ((4, MUTED), (m.winding_layers, C_COPPER), (10, INK)):
        ratio = [dowell_ratio(d_mm, F_OP_HI_HZ, n, 100.0) for d_mm in d_sweep_mm]
        axR.plot(d_sweep_mm, ratio, color=color, linewidth=2.0, label=f'{n} layers')
    axR.axvline(m.wire_diameter_mm, color=INK, linewidth=1.0, linestyle='--', zorder=1)
    axR.annotate('AWG 18 (this design)', xy=(m.wire_diameter_mm, axR.get_ylim()[1]),
                xytext=(4, -4), textcoords='offset points',
                fontsize=8, color=INK_2, ha='left', va='top')
    axR.set_xlabel('Bare conductor diameter [mm]', color=INK_2, fontsize=10)
    axR.set_ylabel('R_ac / R_dc', color=INK_2, fontsize=10)
    axR.set_title(f'vs. wire thickness  (at {F_OP_HI_HZ:.0f} Hz, max speed)',
                  color=INK, fontsize=10, loc='left')
    style(axR)
    axR.legend(fontsize=8, frameon=False, labelcolor=INK_2)

    fig.suptitle("AC copper loss (Dowell) stays ~1.0x inside this design's envelope -- "
                "it only moves if frequency or wire gauge moves outside it",
                color=INK, fontsize=11, y=1.03)
    fig.tight_layout()
    fig.savefig('figures/ac_copper_sweep.png', dpi=200,
               facecolor=SURFACE, bbox_inches='tight')
    plt.close(fig)
    print('figures/ac_copper_sweep.png')


if __name__ == '__main__':
    print_skin_depth_table(MOTOR)
    print_dowell_table(MOTOR)
    print_winding_reconciliation(MOTOR)
    print_turn_count_independence(MOTOR)
    print_fill_factor_lever(MOTOR)

    print("\n" + "=" * 66)
    print("SAVING AC COPPER SWEEP FIGURE (conclusive: where does R_ac/R_dc move?)")
    print("=" * 66)
    # Anchor to the project root so 'figures/' always resolves to the same
    # folder no matter what directory this is run from.
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    os.makedirs('figures', exist_ok=True)
    save_ac_copper_sweep_figure(MOTOR)
