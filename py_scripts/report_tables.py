"""
report_tables.py -- The two blog-post summary tables (torque sweep, speed
sweep), both built from ONE function over ONE MotorParams instance.

Postmortem (see md files/(C) Report Draft.md Section 3.1 note): the old
Table 1 was hand-copied from a run made before config.py's MOTOR was
updated (Kt 0.031->0.034, Kv 270->242, core_mass 0.08->0.125 kg, R_th
1.5->0.29 K/W). Table 2 was generated afterward, against the updated
config.py. Nobody re-ran Table 1, so the two tables silently described two
different motors. This script makes that impossible: every row in both
tables comes from operating_point(), which always reads MOTOR from
config.py -- there is no second parameter set to drift out of sync.

Run:  python report_tables.py
"""
from config import MOTOR, T_AMB_C
from losses import (copper_loss, iron_loss, mech_loss, output_power,
                    resistance_ratio, representative_rpm, elec_freq)
from thermal import steady_winding_temp

# The shared operating point the two sweeps must agree on: Table 1 holds
# this speed fixed while varying torque; Table 2 holds this torque fixed
# while varying speed. representative_rpm() (half no-load speed) is the
# same speed the loss_breakdown figure and report Section 3 already use.
SHARED_RPM = representative_rpm(MOTOR)
SHARED_TORQUE_NM = 0.3


"""Every reported quantity at one (T_nm, rpm) point, from a single
self-consistent thermal solve. Both tables call only this function -- no
operating point is ever computed a second, independent way."""
def operating_point(T_nm, rpm, m=MOTOR, T_amb_c=T_AMB_C):
    T_w_c, _ = steady_winding_temp(T_nm, rpm, m, T_amb_c)
    P_cu = copper_loss(T_nm, m, T_w_c)
    P_fe = iron_loss(rpm, m)
    P_mech = mech_loss(rpm, m)
    P_out = output_power(T_nm, rpm)
    P_loss = P_cu + P_fe + P_mech
    eff_pct = 100.0 * P_out / (P_out + P_loss) if (P_out + P_loss) > 0 else 0.0
    return {
        'T_nm': T_nm, 'rpm': rpm,
        'P_cu': P_cu, 'P_fe': P_fe, 'P_mech': P_mech,
        'efficiency_pct': eff_pct,
        'T_winding_c': T_w_c,
        'R_multiplier': resistance_ratio(T_w_c, m),
    }


def build_table1_torque_sweep(torques_nm, rpm=SHARED_RPM):
    return [operating_point(T, rpm) for T in torques_nm]


def build_table2_speed_sweep(rpms, T_nm=SHARED_TORQUE_NM):
    return [operating_point(T_nm, rpm) for rpm in rpms]


"""Table 1 must agree with Table 2 wherever their operating points overlap
(Table 1's fixed speed, at Table 2's fixed torque). Since both come from
the same operating_point() call this is not a tolerance check on two
independent models -- it's a regression guard against ever going back to
two hand-maintained tables."""
def self_check(table1_rows, table2_rows, tol_pct=1.0):
    row1 = next(r for r in table1_rows if abs(r['T_nm'] - SHARED_TORQUE_NM) < 1e-9)
    row2 = next(r for r in table2_rows if abs(r['rpm'] - SHARED_RPM) < 1e-6)
    diff_pct = 100.0 * abs(row1['P_cu'] - row2['P_cu']) / row2['P_cu']
    if diff_pct >= tol_pct:
        raise AssertionError(
            f"Table 1 and Table 2 diverge at the shared operating point "
            f"({SHARED_TORQUE_NM} N*m, {SHARED_RPM:.0f} rpm): "
            f"P_cu = {row1['P_cu']:.3f} W (Table 1) vs {row2['P_cu']:.3f} W "
            f"(Table 2), {diff_pct:.2f}% apart (tolerance {tol_pct}%).")
    print(f"self-check OK: at ({SHARED_TORQUE_NM} N*m, {SHARED_RPM:.0f} rpm) "
          f"the two tables agree to {diff_pct:.4f}% "
          f"(P_cu = {row1['P_cu']:.3f} W both).")


def render_table1(rows, m=MOTOR):
    f_hz = elec_freq(SHARED_RPM, m.pole_pairs)
    lines = [
        f"**Table 1 — copper loss vs. torque, at {SHARED_RPM:.0f} rpm "
        f"({f_hz:.0f} Hz electrical, half no-load speed)**",
        "",
        "| Torque [N·m] | Speed [rpm] | P_cu [W] | P_fe [W] | P_mech [W] "
        "| Efficiency | T_winding [°C] | R(T)/R_25°C |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r['T_nm']:.1f} | {r['rpm']:.0f} | {r['P_cu']:.2f} "
            f"| {r['P_fe']:.2f} | {r['P_mech']:.2f} | {r['efficiency_pct']:.1f}% "
            f"| {r['T_winding_c']:.0f} | {r['R_multiplier']:.3f}x |")
    return "\n".join(lines)


def render_table2(rows, m=MOTOR):
    lines = [
        f"**Table 2 — copper loss vs. speed, at {SHARED_TORQUE_NM} N·m**",
        "",
        "| Speed [rpm] | f_elec [Hz] | Torque [N·m] | P_cu [W] | P_fe [W] "
        "| Efficiency | T_winding [°C] | R(T)/R_25°C |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        f_hz = elec_freq(r['rpm'], m.pole_pairs)
        lines.append(
            f"| {r['rpm']:.0f} | {f_hz:.0f} | {r['T_nm']:.1f} "
            f"| {r['P_cu']:.2f} | {r['P_fe']:.2f} | {r['efficiency_pct']:.1f}% "
            f"| {r['T_winding_c']:.0f} | {r['R_multiplier']:.3f}x |")
    return "\n".join(lines)


if __name__ == '__main__':
    torques_nm = [0.1, 0.2, 0.3, 0.4, 0.6, 0.8]
    max_rpm = MOTOR.Kv_rpm_per_v * MOTOR.bus_voltage_v
    speeds_rpm = sorted({200, 1000, 2000, SHARED_RPM, 4000, max_rpm})

    table1_rows = build_table1_torque_sweep(torques_nm)
    table2_rows = build_table2_speed_sweep(speeds_rpm)

    self_check(table1_rows, table2_rows)

    print()
    print(render_table1(table1_rows))
    print()
    print(render_table2(table2_rows))
