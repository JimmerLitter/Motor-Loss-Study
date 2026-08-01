"""
run_study.py -- BLDC motor loss & thermal study driver.

Single entry point. Produces all report figures:
  figures/loss_breakdown.png       (delegated to plot_losses.py -- 2-panel)
  figures/efficiency_map.png       (efficiency over torque x speed, DC-copper)
  figures/thermal_limit.png        (continuous torque limit vs speed)
  figures/core_loss.png            (core/iron loss alone over torque x speed)
  figures/ac_copper_loss.png       (AC-corrected copper loss over torque x speed)
  figures/mech_loss.png            (mechanical loss alone -- flat, see Figure 6)
  figures/dc_copper_loss.png       (DC copper loss alone -- flat, see Figure 7)
  figures/output_power.png         (mechanical output power, T x omega)
  figures/total_loss.png           (P_cu(AC) + P_fe + P_mech)
  figures/input_power.png          (P_in = P_out + P_loss_total)
  figures/efficiency_map_clean.png (P_out / P_in, AC-corrected throughout)
  figures/ac_ratio.png             (R_ac/R_dc alone -- torque-independent, see Figure 5)

Parameters live in config.py -- edit MOTOR there, not here.
"""
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

from losses import (efficiency, iron_loss, copper_loss, mech_loss,
                    output_power, representative_rpm, elec_freq)
from thermal import steady_winding_temp, continuous_torque_limit, peak_hold_time
from config import MOTOR, T_AMB_C
from ac_copper import ac_copper_loss, dowell_ratio
import plot_losses as pl
from plot_losses import SURFACE, INK, INK_2, MUTED, C_COPPER, style

# Sequential ramp: light -> dark. Blue steps 100-700 from the reference
# palette; more-is-darker = more of the plotted quantity.
BLUE_RAMP = ['#cde2fb', '#b7d3f6', '#9ec5f4', '#86b6ef', '#6da7ec', '#5598e7',
             '#3987e5', '#2a78d6', '#256abf', '#1c5cab', '#184f95', '#104281',
             '#0d366b']
CMAP = LinearSegmentedColormap.from_list('viz_blue', BLUE_RAMP, N=256)

# Anchor to the project root (parent of py_scripts/) so 'figures/' always
# resolves to the same folder no matter what directory this is run from.
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
os.makedirs('figures', exist_ok=True)
rpm0 = representative_rpm(MOTOR)
rpm_axis = np.linspace(200, MOTOR.Kv_rpm_per_v * MOTOR.bus_voltage_v, 80)
T_grid = np.linspace(0.02, MOTOR.T_peak_nm, 90)
RR, TT = np.meshgrid(rpm_axis, T_grid)


# =====================================================================
# Shared plotting helpers -- every figure below is a contour over this
# same (RR, TT) torque x speed grid, so the boilerplate (axes styling,
# colorbar, save) is factored out once instead of repeated per figure.
# =====================================================================
"""Evaluate point_fn(T_nm, rpm, T_w_c) at every (RR, TT) grid cell.

Solves the steady winding temperature once per cell and hands it to
point_fn, so callers needing the R(T) feedback don't each re-implement
the loop."""
def compute_over_grid(point_fn):
    Z = np.zeros_like(RR)
    for i in range(RR.shape[0]):
        for j in range(RR.shape[1]):
            T_w_c, _ = steady_winding_temp(TT[i, j], RR[i, j], MOTOR, T_AMB_C)
            Z[i, j] = point_fn(TT[i, j], RR[i, j], T_w_c)
    return Z


"""Contour a quantity over the torque x speed grid and save it.

Shared boilerplate for the plain loss/power maps -- the efficiency maps
(with their extra thermal-limit overlay) are built by hand below."""
def save_torque_speed_map(Z, filename, title, cbar_label, levels=22, title_loc='left'):
    fig, ax = plt.subplots(figsize=(7.6, 5.4))
    fig.patch.set_facecolor(SURFACE)
    cs = ax.contourf(RR, TT, Z, levels=levels, cmap=CMAP, zorder=1)
    ax.set_ylim(0.05, MOTOR.T_peak_nm)
    style(ax)
    ax.grid(False)
    ax.set_xlabel('Speed [rpm]', color=INK_2, fontsize=10)
    ax.set_ylabel('Torque [N·m]', color=INK_2, fontsize=10)
    ax.set_title(title, color=INK, fontsize=11, pad=10, loc=title_loc)
    cb = fig.colorbar(cs, ax=ax, pad=0.02)
    cb.set_label(cbar_label, color=INK_2, fontsize=10)
    cb.ax.tick_params(colors=MUTED, labelsize=9, length=0)
    cb.outline.set_visible(False)
    for lbl in cb.ax.get_yticklabels():
        lbl.set_color(INK_2)
    fig.tight_layout()
    fig.savefig(filename, dpi=200, facecolor=SURFACE, bbox_inches='tight')
    plt.close(fig)
    print(filename)


"""Draw the continuous-torque-limit line + label used on both efficiency maps.

Below ~4800 rpm the continuous rating is ABOVE T_peak_nm, so the line is
clipped flat along the axes' top edge (ylim tops out at T_peak_nm) -- the
winding can sustain more than datasheet peak torque continuously there.
The label must anchor on the one stretch that's actually inside the visible
range (the high-speed dip), or annotate() silently drops it: its default
clip check hides the whole annotation when xy falls outside the axes."""
def draw_thermal_limit_overlay(ax):
    ax.plot(rpm_axis, tlim_curve, color=INK, linewidth=2.0, zorder=4)
    y_top = ax.get_ylim()[1]
    visible = [i for i, t in enumerate(tlim_curve) if t <= y_top]
    i_vis = visible[len(visible) // 2] if visible else len(tlim_curve) - 1
    ax.annotate(
        'continuous thermal limit --\nbelow datasheet peak only above ~4800 rpm\n'
        '(everywhere else, the winding can sustain\nmore than peak torque continuously)',
        xy=(rpm_axis[i_vis], tlim_curve[i_vis]),
        xytext=(-225, -55), textcoords='offset points',
        fontsize=9, color=INK, linespacing=1.4,
        arrowprops=dict(arrowstyle='-', color=INK, linewidth=0.8))


"""Draw the labelled 80/85/88% contour lines used on both efficiency maps."""
def draw_efficiency_pct_contours(ax, EFF):
    cl = ax.contour(RR, TT, EFF, levels=[80, 85, 88],
                    colors=[SURFACE], linewidths=1.0, zorder=2)
    ax.clabel(cl, inline=True, fontsize=8, fmt='%d%%', colors=[SURFACE])


# =====================================================================
# FIGURE 1 -- loss breakdown (2-panel; see plot_losses.py for rationale)
# =====================================================================
fig1 = pl.build()
fig1.savefig('figures/loss_breakdown.png', dpi=200,
             facecolor=SURFACE, bbox_inches='tight')
plt.close(fig1)
print('figures/loss_breakdown.png')


# =====================================================================
# FIGURE 2 -- efficiency map (DC copper only)
# =====================================================================
EFF = compute_over_grid(lambda T_nm, rpm, T_w_c: efficiency(T_nm, rpm, MOTOR, T_w_c) * 100.0)
tlim_curve = [continuous_torque_limit(r, MOTOR, T_AMB_C, T_hi_nm=2.25) for r in rpm_axis]

fig2, ax = plt.subplots(figsize=(7.6, 5.4))
fig2.patch.set_facecolor(SURFACE)
cs = ax.contourf(RR, TT, EFF, levels=np.linspace(50, 92, 22), cmap=CMAP, extend='min', zorder=1)
# Label selectively -- the 70% contour hugs the bottom edge and its label
# clips, so it is drawn without one; the colorbar carries the rest.
draw_efficiency_pct_contours(ax, EFF)
ax.set_ylim(0.05, MOTOR.T_peak_nm)
draw_thermal_limit_overlay(ax)  # ties this figure to Figure 3

style(ax)
ax.grid(False)
ax.set_xlabel('Speed [rpm]', color=INK_2, fontsize=10)
ax.set_ylabel('Torque [N·m]', color=INK_2, fontsize=10)
ax.set_title('Efficiency peaks at low torque / moderate speed; '
             'collapses as I²R takes over',
             color=INK, fontsize=11, pad=10, loc='left')
cb = fig2.colorbar(cs, ax=ax, pad=0.02)
cb.set_label('Efficiency [%]', color=INK_2, fontsize=10)
cb.ax.tick_params(colors=MUTED, labelsize=9, length=0)
cb.outline.set_visible(False)
for lbl in cb.ax.get_yticklabels():
    lbl.set_color(INK_2)
fig2.tight_layout()
fig2.savefig('figures/efficiency_map.png', dpi=200,
             facecolor=SURFACE, bbox_inches='tight')
plt.close(fig2)
print('figures/efficiency_map.png')


# =====================================================================
# FIGURE 3 -- continuous torque (thermal) limit
# =====================================================================
fig3, ax = plt.subplots(figsize=(7.6, 4.8))
fig3.patch.set_facecolor(SURFACE)

# single series -> no legend box; the title names it
ax.plot(rpm_axis, tlim_curve, color=C_COPPER, linewidth=2.0, zorder=3)
ax.fill_between(rpm_axis, 0, tlim_curve, color=C_COPPER, alpha=0.12,
                linewidth=0, zorder=2)

# datasheet peak, for contrast -- this is the finding
ax.axhline(MOTOR.T_peak_nm, color=MUTED, linewidth=1.2, zorder=3)
ax.annotate(f"datasheet peak  {MOTOR.T_peak_nm:.1f} N·m",
            xy=(rpm_axis[3], MOTOR.T_peak_nm), xytext=(0, 7),
            textcoords='offset points', fontsize=9, color=INK_2)

t_mid = tlim_curve[len(tlim_curve) // 2]
ax.annotate(f'continuous  {t_mid:.2f} N·m\n= {100*t_mid/MOTOR.T_peak_nm:.0f}% of peak',
            xy=(rpm_axis[len(rpm_axis)//2], t_mid), xytext=(0, -46),
            textcoords='offset points', fontsize=9, color=C_COPPER,
            linespacing=1.4, fontweight='medium')

style(ax)
ax.set_xlim(rpm_axis[0], rpm_axis[-1])
ax.set_ylim(0, MOTOR.T_peak_nm * 1.18)
ax.set_xlabel('Speed [rpm]', color=INK_2, fontsize=10)
ax.set_ylabel('Torque [N·m]', color=INK_2, fontsize=10)
ax.set_title(f'Continuous torque is {100*t_mid/MOTOR.T_peak_nm:.0f}% of the '
             f'datasheet peak (T_winding ≤ {MOTOR.T_max_c:.0f} °C)',
             color=INK, fontsize=11, pad=10, loc='left')
fig3.tight_layout()
fig3.savefig('figures/thermal_limit.png', dpi=200,
             facecolor=SURFACE, bbox_inches='tight')
plt.close(fig3)
print('figures/thermal_limit.png')


# =====================================================================
# FIGURE 4 -- core (iron) loss alone
#   iron_loss() only depends on speed (rpm, pole_pairs, B_pk, core_mass) --
#   NOT torque -- so this renders as flat vertical bands (constant up the
#   torque axis, changing only with speed). That's the point: torque-
#   dependence only shows up once copper loss (I^2R) enters the picture
#   in Figure 2.
# =====================================================================
P_FE = iron_loss(RR, MOTOR)
save_torque_speed_map(P_FE, 'figures/core_loss.png',
                      'Core loss tracks speed only -- flat vs. torque until '
                      'copper loss enters (see Figure 2)',
                      'Core loss [W]')


# =====================================================================
# FIGURE 5 -- actual AC-corrected copper loss
#   ac_copper_loss() (from ac_copper.py) applies the Dowell R_ac/R_dc ratio
#   at this design's R_ph-reconciled wire gauge (AWG 18, confirmed via
#   ac_copper.py's winding reconciliation table -- NOT the unreconciled
#   "12 AWG" figure found online, see config.py) and confirmed 8-turn/
#   8-layer winding.
# =====================================================================
P_CU_AC = compute_over_grid(lambda T_nm, rpm, T_w_c: ac_copper_loss(T_nm, rpm, MOTOR, T_w_c))
save_torque_speed_map(P_CU_AC, 'figures/ac_copper_loss.png',
                      f'Copper loss, AC-corrected (AWG 18, '
                      f'{MOTOR.winding_layers}-layer confirmed)',
                      'Copper loss, AC-corrected [W]', title_loc='center')


# =====================================================================
# FIGURE 6 -- mechanical loss alone
#   mech_loss() only depends on rpm (windage ~ omega^2 plus a constant
#   bearing-friction floor) -- NOT torque -- so like Figure 4 this renders
#   as flat vertical bands. Unlike iron loss, the magnitude barely moves
#   end to end: the friction floor dominates and windage only adds a small
#   tail at top speed -- plotted in mW because the full-watt range is too
#   narrow to show any gradient at all.
# =====================================================================
P_MECH_MW = mech_loss(RR, MOTOR) * 1000.0
floor_mw = MOTOR.friction_floor_w * 1000.0
windage_tail_mw = P_MECH_MW.max() - floor_mw
save_torque_speed_map(P_MECH_MW, 'figures/mech_loss.png',
                      f'Mechanical loss: a {floor_mw:.0f} mW friction floor -- '
                      f'windage adds only {windage_tail_mw:.1f} mW at top speed',
                      'Mechanical loss [mW]')


# =====================================================================
# FIGURE 7 -- DC copper loss alone
#   copper_loss() at a fixed reference temperature depends only on torque
#   (I_ph = T/Kt, P = 3*I^2*R) -- NOT speed -- so unlike iron/mech loss
#   (vertical bands, rpm-only) this renders as flat horizontal bands.
#   Evaluated at R_ref_temp_c (cold resistance) rather than through
#   steady_winding_temp, so speed truly drops out -- no rpm-dependent
#   thermal feedback sneaking in.
# =====================================================================
P_CU_DC = copper_loss(TT, MOTOR, MOTOR.R_ref_temp_c)
save_torque_speed_map(P_CU_DC, 'figures/dc_copper_loss.png',
                      f'DC copper loss (I²R at {MOTOR.R_ref_temp_c:.0f} °C) '
                      '-- torque-only, flat with speed',
                      'Copper loss, DC [W]')


# =====================================================================
# FIGURE 8 -- mechanical output power
#   output_power() = T * omega_mech, so this is a pure T*rpm product --
#   diagonal contours rising toward the top-right corner (high torque AND
#   high speed together), unlike the loss maps which are each dominated
#   by only one axis.
# =====================================================================
P_OUT = output_power(TT, RR)
save_torque_speed_map(P_OUT, 'figures/output_power.png',
                      'Output power (T x omega) -- scales with both torque and speed',
                      'Output power [W]')


# =====================================================================
# FIGURE 9 -- total loss (P_in = P_out + P_loss, the number behind Figure 2)
#   Sum of AC-corrected copper (Figure 5), core (Figure 4), and mechanical
#   (Figure 6) loss -- reuses arrays already computed on this grid.
#
#   CAVEAT: Figure 2's efficiency map runs efficiency() from losses.py,
#   which is DC-copper only (no Dowell correction). This total-loss map
#   uses the AC-corrected copper term instead, so it is NOT numerically
#   consistent with Figure 2 -- Figure 2 is a shade optimistic at high
#   speed, where the AC penalty is largest. Figures 9-11 are the mutually
#   consistent, AC-corrected picture.
# =====================================================================
P_LOSS_TOTAL = P_CU_AC + P_FE + P_MECH_MW / 1000.0
save_torque_speed_map(P_LOSS_TOTAL, 'figures/total_loss.png',
                      'Total loss: copper-dominated at high torque, iron-dominated '
                      'at high speed (AC-corrected)',
                      'Total loss [W]')


# =====================================================================
# FIGURE 10 -- total input power: P_in = P_out + P_loss_total
#   P_out from Figure 8, P_loss_total from Figure 9 -- both already on
#   this grid, so this is a straight sum, no new solve. Bridges output
#   power and loss into the efficiency map:
#   Fig 8 (P_out) + Fig 9 (P_loss) -> Fig 10 (P_in) -> Fig 11 (P_out/P_in).
# =====================================================================
P_IN = P_OUT + P_LOSS_TOTAL
save_torque_speed_map(P_IN, 'figures/input_power.png',
                      'Total input power: P_in = P_out + P_loss (AC-corrected)',
                      'Input power [W]')


# =====================================================================
# FIGURE 11 -- efficiency, done cleanly: eta = P_out / P_in
#   P_out from Figure 8, P_in from Figure 10 -- both already on this grid,
#   so no new solve. Unlike Figure 2 (DC-copper only), this divides
#   straight through the SAME AC-corrected total loss used in Figures 9-10
#   -- the three are guaranteed to agree because they share P_LOSS_TOTAL /
#   P_IN. This is the version to cite for "P_in = P_out + P_loss, therefore
#   efficiency" -- Figure 2 is not numerically consistent with it.
# =====================================================================
EFF_CLEAN = 100.0 * P_OUT / P_IN

fig11, ax = plt.subplots(figsize=(7.6, 5.4))
fig11.patch.set_facecolor(SURFACE)
cs11 = ax.contourf(RR, TT, EFF_CLEAN, levels=np.linspace(50, 92, 22),
                   cmap=CMAP, extend='min', zorder=1)
draw_efficiency_pct_contours(ax, EFF_CLEAN)
ax.set_ylim(0.05, MOTOR.T_peak_nm)
draw_thermal_limit_overlay(ax)

style(ax)
ax.grid(False)
ax.set_xlabel('Speed [rpm]', color=INK_2, fontsize=10)
ax.set_ylabel('Torque [N·m]', color=INK_2, fontsize=10)
ax.set_title('Efficiency = P_out / P_in, AC-corrected (consistent with Figures 9-10)',
             color=INK, fontsize=11, pad=10, loc='left')
cb11 = fig11.colorbar(cs11, ax=ax, pad=0.02)
cb11.set_label('Efficiency [%]', color=INK_2, fontsize=10)
cb11.ax.tick_params(colors=MUTED, labelsize=9, length=0)
cb11.outline.set_visible(False)
for lbl in cb11.ax.get_yticklabels():
    lbl.set_color(INK_2)
fig11.tight_layout()
fig11.savefig('figures/efficiency_map_clean.png', dpi=200,
             facecolor=SURFACE, bbox_inches='tight')
plt.close(fig11)
print('figures/efficiency_map_clean.png')


# =====================================================================
# FIGURE 12 -- AC resistance penalty (Dowell ratio) alone
#   dowell_ratio() takes wire diameter, electrical frequency, and layer
#   count -- NOT torque or current -- so unlike Figure 5 (which multiplies
#   this same ratio onto the torque-dependent DC copper loss, and so
#   renders mostly-horizontal with a slight speed-driven tilt), this
#   renders as pure vertical bands: the AC penalty isolated from load
#   entirely, driven by speed alone. Evaluated at 100 degC, matching the
#   convention already used in ac_copper.py's Dowell table and sweep figure.
# =====================================================================
F_ELEC = elec_freq(RR, MOTOR.pole_pairs)
RATIO = np.vectorize(dowell_ratio)(MOTOR.wire_diameter_mm, F_ELEC, MOTOR.winding_layers, 100.0)
save_torque_speed_map(RATIO, 'figures/ac_ratio.png',
                      'AC resistance penalty (R_ac/R_dc) rises with speed alone -- '
                      'independent of torque',
                      'R_ac / R_dc')


# =====================================================================
# Numbers for the report
# =====================================================================
t_hold_s = peak_hold_time(MOTOR.T_peak_nm, rpm0, MOTOR, T_AMB_C)
print('\n--- report numbers ---')
print(f"representative speed      : {rpm0:.0f} rpm "
      f"({MOTOR.pole_pairs*rpm0/60:.0f} Hz electrical)")
print(f"continuous torque @ rep   : "
      f"{continuous_torque_limit(rpm0, MOTOR, T_AMB_C, T_hi_nm=2.25):.4f} N*m")
print(f"continuous @ {rpm_axis[0]:.0f} rpm      : {tlim_curve[0]:.4f} N*m")
print(f"continuous @ {rpm_axis[-1]:.0f} rpm     : {tlim_curve[-1]:.4f} N*m")
print(f"droop across speed range  : {100*(1-tlim_curve[-1]/tlim_curve[0]):.1f}%")
print(f"peak-hold time @ {MOTOR.T_peak_nm} N*m : {t_hold_s:.1f} s")
print(f"peak efficiency           : {EFF.max():.1f}%")
i0 = P_LOSS_TOTAL.shape[0] // 2
j0 = list(rpm_axis).index(min(rpm_axis, key=lambda r: abs(r - rpm0)))
print(f"@ rep. speed/mid torque   : P_out {P_OUT[i0, j0]:.1f} W, "
      f"P_loss {P_LOSS_TOTAL[i0, j0]:.1f} W, "
      f"P_in {P_IN[i0, j0]:.1f} W, "
      f"eff {100*P_OUT[i0, j0]/P_IN[i0, j0]:.1f}% (AC-corrected)")
print(f"peak efficiency (clean)   : {EFF_CLEAN.max():.1f}%  "
      f"(vs. {EFF.max():.1f}% from Figure 2's DC-only calc)")
