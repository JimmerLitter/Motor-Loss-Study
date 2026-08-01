"""
thermal.py -- Lumped-parameter thermal model.

2-node reduction: winding node -> ambient through the motor's thermal
resistance (m.R_th_k_per_w). Includes the copper-loss temperature feedback
(resistance rises with temperature, which raises loss, which raises
temperature) via fixed-point iteration.
"""
import numpy as np
from losses import total_loss


"""Steady winding temperature [degC] including copper R(T) feedback.
Solves T_w = T_amb + P_loss(T_w) * R_th by fixed-point iteration. If the
feedback diverges (thermal runaway -- physically means "this load is not
thermally sustainable"), caps at T_cap_c instead of blowing up to infinity.
Returns (T_winding_c, P_loss_w)."""
def steady_winding_temp(T_nm, rpm, m, T_amb_c, tol=1e-3, itmax=200, T_cap_c=1500.0):
    T_w_c = T_amb_c
    P_loss_w = 0.0
    for _ in range(itmax):
        P_cu, P_fe, P_mech = total_loss(T_nm, rpm, m, T_w_c)
        P_loss_w = P_cu + P_fe + P_mech
        T_new_c = T_amb_c + P_loss_w * m.R_th_k_per_w
        if T_new_c > T_cap_c:
            return T_cap_c, P_loss_w
        if abs(T_new_c - T_w_c) < tol:
            return T_new_c, P_loss_w
        T_w_c = T_new_c
    return T_w_c, P_loss_w


"""Max continuous torque [N*m] at this speed such that T_winding <= T_max_c.
Bisection on torque."""
def continuous_torque_limit(rpm, m, T_amb_c, T_hi_nm=None):
    lo_nm = 0.0
    hi_nm = T_hi_nm if T_hi_nm is not None else m.T_peak_nm
    T_w_hi_c, _ = steady_winding_temp(hi_nm, rpm, m, T_amb_c)
    if T_w_hi_c <= m.T_max_c:          # thermally unlimited within our torque range
        return hi_nm
    for _ in range(80):
        mid_nm = 0.5 * (lo_nm + hi_nm)
        T_w_c, _ = steady_winding_temp(mid_nm, rpm, m, T_amb_c)
        if T_w_c > m.T_max_c:
            hi_nm = mid_nm
        else:
            lo_nm = mid_nm
        if hi_nm - lo_nm < 1e-4:
            break
    return 0.5 * (lo_nm + hi_nm)


"""How long [s] this motor can hold torque T_nm before hitting T_max_c.
Short bursts are ~adiabatic: during a brief peak the heat has no time to
leave, so all loss goes into the thermal mass C_th_j_per_k:
    t = C_th * (T_max - T_start) / P_loss
Returns inf if the load is thermally sustainable indefinitely (steady
winding temp already <= T_max_c). Immune to the runaway artifact in
steady_winding_temp."""
def peak_hold_time(T_nm, rpm, m, T_amb_c, T_start_c=None):
    T_start_c = T_start_c if T_start_c is not None else T_amb_c
    T_ss_c, _ = steady_winding_temp(T_nm, rpm, m, T_amb_c)
    if T_ss_c <= m.T_max_c:
        return np.inf
    P_cu, P_fe, P_mech = total_loss(T_nm, rpm, m, T_start_c)
    P_loss_w = P_cu + P_fe + P_mech
    if P_loss_w <= 0:
        return np.inf
    return m.C_th_j_per_k * (m.T_max_c - T_start_c) / P_loss_w
