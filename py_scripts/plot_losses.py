"""
plot_losses.py -- Loss breakdown figure, redesigned.

WHY NOT A STACKPLOT
-------------------
Copper spans 1.3 -> 148 W while mechanical is a flat 0.20 W. On a linear
stacked area the 0.20 W band is ~0.1% of the plot height -- physically
invisible. Stacking is a part-to-whole form; it cannot also carry magnitude
across three decades.

Two panels, two jobs, one x-axis each (never a dual axis):
  (a) log-y lines  -> absolute magnitude across decades; the copper/iron
                      crossover becomes a real visual intersection
  (b) 100% area    -> composition, independent of magnitude, so mechanical
                      is legible exactly where it matters (low torque)

Run:
  python plot_losses.py                # writes figures/loss_breakdown.png
  python plot_losses.py --interactive  # clickable legend to toggle series
"""
import os
import sys
import numpy as np
import matplotlib
if '--interactive' not in sys.argv:
    matplotlib.use('Agg')
import matplotlib.pyplot as plt

from losses import total_loss, representative_rpm
from thermal import steady_winding_temp, continuous_torque_limit
from config import MOTOR, T_AMB_C, T_PLOT_MAX_NM as T_HI_NM

# ---- design tokens (dataviz reference palette, light mode) ----------------
# Validated with scripts/validate_palette.js:
#   light --pairs all : CVD dE 9.2, normal-vision dE 24.0, ALL PASS
#     (one WARN: aqua 2.74:1 vs surface -> relief rule satisfied by the
#      direct label on the mechanical series; do not remove it)
#   dark  --pairs all : ALL PASS. Dark steps: #3987e5 / #d95926 / #199e70
SURFACE   = '#fcfcfb'
INK       = '#0b0b0b'
INK_2     = '#52514e'
MUTED     = '#898781'
GRID      = '#e1e0d9'
BASELINE  = '#c3c2b7'
# categorical slots 1-3, fixed order, never cycled
C_COPPER, C_IRON, C_MECH = '#2a78d6', '#eb6834', '#1baf7a'
SERIES = (('Copper (I²R)', C_COPPER), ('Iron (Steinmetz)', C_IRON),
          ('Mechanical', C_MECH))


"""Loss components vs torque at the representative speed."""
def compute(n=240):
    rpm0 = representative_rpm(MOTOR)
    T_nm = np.linspace(0.05, T_HI_NM, n)
    cu_w, fe_w, me_w = [], [], []
    for t_nm in T_nm:
        T_w_c, _ = steady_winding_temp(t_nm, rpm0, MOTOR, T_AMB_C)
        a, b, c = total_loss(t_nm, rpm0, MOTOR, T_w_c)
        cu_w.append(a); fe_w.append(b); me_w.append(c)
    return rpm0, T_nm, np.array(cu_w), np.array(fe_w), np.array(me_w)


"""Torque where copper loss overtakes iron loss."""
def crossover(T_nm, cu_w, fe_w):
    d = cu_w - fe_w
    i = np.where(np.diff(np.sign(d)))[0]
    if not len(i):
        return None
    k = i[0]
    frac = -d[k] / (d[k + 1] - d[k])
    return T_nm[k] + frac * (T_nm[k + 1] - T_nm[k])


def style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.8, linestyle='-', zorder=0)
    ax.set_axisbelow(True)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    for s in ('left', 'bottom'):
        ax.spines[s].set_color(BASELINE)
        ax.spines[s].set_linewidth(0.8)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_color(INK_2)


def build(interactive=False):
    rpm0, T_nm, cu_w, fe_w, me_w = compute()
    xo_nm = crossover(T_nm, cu_w, fe_w)
    tlim_nm = continuous_torque_limit(rpm0, MOTOR, T_AMB_C, T_hi_nm=2.25)

    # hspace must clear BOTH the upper panel's x-label and the lower panel's
    # title -- they occupy the same band between the axes.
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(7.2, 8.6), sharex=True,
        gridspec_kw={'height_ratios': [1.35, 1], 'hspace': 0.34})
    fig.patch.set_facecolor(SURFACE)

    # ---------- panel A: absolute magnitude, log scale ----------
    lines = []
    for (label, color), y in zip(SERIES, (cu_w, fe_w, me_w)):
        ln, = ax1.plot(T_nm, y, color=color, linewidth=2.0, label=label,
                       solid_capstyle='round', zorder=3)
        lines.append(ln)
    style(ax1)
    ax1.set_yscale('log')
    ax1.set_ylabel('Loss [W]', color=INK_2, fontsize=10)
    ax1.set_ylim(0.08, 400)
    # sharex hides these by default -- but a reader who crops or reads only the
    # top panel then has an unlabelled x-axis. Each panel stands alone.
    ax1.tick_params(labelbottom=True)
    ax1.set_xlabel('Torque [N·m]', color=INK_2, fontsize=10, labelpad=2)

    # thermally unsustainable region -- label at the top, clear of the marks
    ax1.axvspan(tlim_nm, T_HI_NM, color=BASELINE, alpha=0.18, zorder=1, linewidth=0)
    ax1.text(tlim_nm + 0.015, 260, f'beyond continuous\nthermal limit ({tlim_nm:.2f} N·m)',
             fontsize=8, color=MUTED, va='top', ha='left', linespacing=1.4)

    # the crossover -- this is the finding
    if xo_nm:
        ax1.axvline(xo_nm, color=MUTED, linewidth=0.8, zorder=2)
        yx = np.interp(xo_nm, T_nm, fe_w)
        ax1.plot([xo_nm], [yx], 'o', markersize=8, color=INK,
                 markeredgecolor=SURFACE, markeredgewidth=2, zorder=5)
        ax1.annotate(f'copper overtakes iron\n{xo_nm:.3f} N·m',
                     xy=(xo_nm, yx), xytext=(xo_nm + 0.075, 0.55),
                     fontsize=9, color=INK, linespacing=1.4,
                     arrowprops=dict(arrowstyle='-', color=MUTED, linewidth=0.8))

    # selective direct labels at the right endpoint
    for (label, color), y in zip(SERIES, (cu_w, fe_w, me_w)):
        ax1.annotate(f'{y[-1]:.1f} W', xy=(T_nm[-1], y[-1]),
                     xytext=(6, 0), textcoords='offset points',
                     color=color, fontsize=9, va='center', fontweight='medium')

    ax1.set_title(f'Loss magnitude at {rpm0:.0f} rpm  '
                  f'({MOTOR.pole_pairs*rpm0/60:.0f} Hz electrical)',
                  color=INK, fontsize=11, pad=10, loc='left')

    leg = ax1.legend(frameon=False, loc='upper left', fontsize=9,
                     labelcolor=INK_2, handlelength=1.6)

    # ---------- panel B: composition, 100% stacked ----------
    tot_w = cu_w + fe_w + me_w
    ax2.stackplot(T_nm, 100 * cu_w / tot_w, 100 * fe_w / tot_w, 100 * me_w / tot_w,
                  colors=(C_COPPER, C_IRON, C_MECH),
                  edgecolor=SURFACE, linewidth=1.5, zorder=2)
    style(ax2)
    ax2.set_ylim(0, 100)
    ax2.set_xlim(T_nm[0], T_nm[-1])
    ax2.set_ylabel('Share of total loss [%]', color=INK_2, fontsize=10)
    ax2.set_xlabel('Torque [N·m]', color=INK_2, fontsize=10)
    if xo_nm:
        ax2.axvline(xo_nm, color=SURFACE, linewidth=1.2, zorder=3)
    ax2.set_title('Composition: iron-dominated below the crossover, '
                  'copper-dominated above',
                  color=INK, fontsize=11, pad=14, loc='left')

    # Label each band only where it is thick enough to hold text with padding.
    # Iron peaks at the left edge, copper at the right. Mechanical never
    # exceeds ~4% and so is deliberately left unlabelled here -- it is direct-
    # labelled (0.2 W) in panel A and tabulated in the report. A label forced
    # into a 4% band would be clipped, which is worse than no label.
    def share(i, arr):
        return 100 * arr[i] / tot_w[i]

    iL = 2                      # left edge: iron dominates
    ax2.text(T_nm[iL] + 0.008, share(iL, cu_w) + share(iL, fe_w) / 2,
             f'iron {share(iL, fe_w):.0f}%', fontsize=9, color=SURFACE,
             va='center', ha='left', fontweight='bold')

    iR = len(T_nm) - 3          # right edge: copper dominates
    ax2.text(T_nm[iR] - 0.008, share(iR, cu_w) / 2,
             f'copper {share(iR, cu_w):.0f}%', fontsize=9, color=SURFACE,
             va='center', ha='right', fontweight='bold')

    if interactive:
        _wire_toggles(fig, leg, lines)

    return fig


"""Clickable legend -- exploration only, not for the report figure."""
def _wire_toggles(fig, leg, lines):
    mapping = {}
    for txt, ln in zip(leg.get_texts(), lines):
        txt.set_picker(8)
        mapping[txt] = ln
    for hl, ln in zip(leg.legend_handles, lines):
        hl.set_picker(8)
        mapping[hl] = ln

    def on_pick(event):
        ln = mapping.get(event.artist)
        if ln is None:
            return
        vis = not ln.get_visible()
        ln.set_visible(vis)
        event.artist.set_alpha(1.0 if vis else 0.3)
        fig.canvas.draw_idle()

    fig.canvas.mpl_connect('pick_event', on_pick)
    print('Interactive: click a legend entry to toggle that series.')


if __name__ == '__main__':
    # Anchor to the project root so 'figures/' always resolves to the same
    # folder no matter what directory this is run from.
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    os.makedirs('figures', exist_ok=True)
    interactive = '--interactive' in sys.argv
    fig = build(interactive)
    if interactive:
        plt.show()
    else:
        out = 'figures/loss_breakdown.png'
        fig.savefig(out, dpi=200, facecolor=SURFACE, bbox_inches='tight')
        print(f'wrote {out}')
        rpm0, T_nm, cu_w, fe_w, me_w = compute()
        xo_nm = crossover(T_nm, cu_w, fe_w)
        print(f'crossover = {xo_nm:.4f} N*m')
        print(f'at T=0.05: cu {cu_w[0]:.2f} W  fe {fe_w[0]:.2f} W  me {me_w[0]:.2f} W')
        tot0_w = cu_w[0] + fe_w[0] + me_w[0]
        print(f'  shares:  cu {100*cu_w[0]/tot0_w:.1f}%  '
              f'fe {100*fe_w[0]/tot0_w:.1f}%  '
              f'me {100*me_w[0]/tot0_w:.1f}%')
