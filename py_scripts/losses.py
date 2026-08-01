"""
losses.py -- Loss models for a BLDC/PMSM motor.
Copper (I2R), iron (Steinmetz hysteresis+eddy), mechanical (windage+friction).

Every function takes a MotorParams instance (config.MOTOR) for motor
constants, plus an operating point (T_nm, rpm, temp_c) as arguments -- no
motor constant is ever hardcoded inline, so these run against any motor.
"""
import numpy as np
from config import ALPHA_CU_PER_C


"""RMS phase current for torque T_nm:  I = T / Kt."""
def phase_current(T_nm, Kt_nm_per_a):
    return T_nm / Kt_nm_per_a


"""3-phase copper (Joule) loss, with copper resistance temperature rise.
P_cu = 3 * I_ph^2 * R_ph(temp_c)
R_ph(temp_c) = R_ph_ohm * (1 + alpha_cu * (temp_c - R_ref_temp_c))"""
def copper_loss(T_nm, m, temp_c):
    I_ph_a = phase_current(T_nm, m.Kt_nm_per_a)
    R_hot_ohm = m.R_ph_ohm * (1.0 + ALPHA_CU_PER_C * (temp_c - m.R_ref_temp_c))
    return 3.0 * I_ph_a ** 2 * R_hot_ohm


"""Electrical frequency [Hz] from mechanical speed: f = pole_pairs * rpm / 60."""
def elec_freq(rpm, pole_pairs):
    return pole_pairs * rpm / 60.0


"""Steinmetz iron loss: P_fe = (k_h*f*B^alpha + k_e*f^2*B^2) * core_mass.
Coefficients are fit per motor from a lamination datasheet (e.g. M235-35A)
or measurement."""
def iron_loss(rpm, m):
    f_hz = elec_freq(rpm, m.pole_pairs)
    p_hyst_w = m.steinmetz_kh * f_hz * m.B_pk_t ** m.steinmetz_alpha
    p_eddy_w = m.steinmetz_ke * f_hz ** 2 * m.B_pk_t ** 2
    return (p_hyst_w + p_eddy_w) * m.core_mass_kg


"""Windage (~omega^2) plus a constant bearing-friction floor [W]."""
def mech_loss(rpm, m):
    omega_rad_s = 2.0 * np.pi * rpm / 60.0
    return m.windage_coeff * omega_rad_s ** 2 + m.friction_floor_w


"""Mechanical output power [W]: P_out = T * omega_mech."""
def output_power(T_nm, rpm):
    return T_nm * 2.0 * np.pi * rpm / 60.0


"""Representative study speed: half of no-load (Kv * Vdc) speed."""
def representative_rpm(m):
    return 0.5 * m.Kv_rpm_per_v * m.bus_voltage_v


"""Return (P_cu, P_fe, P_mech) [W] for motor m at this operating point."""
def total_loss(T_nm, rpm, m, temp_c):
    P_cu = copper_loss(T_nm, m, temp_c)
    P_fe = iron_loss(rpm, m)
    P_mech = mech_loss(rpm, m)
    return P_cu, P_fe, P_mech


"""Motoring efficiency [0-1]: P_out / (P_out + P_loss)."""
def efficiency(T_nm, rpm, m, temp_c):
    P_out = output_power(T_nm, rpm)
    P_cu, P_fe, P_mech = total_loss(T_nm, rpm, m, temp_c)
    P_loss = P_cu + P_fe + P_mech
    denom = P_out + P_loss
    return P_out / denom if denom > 0 else 0.0
