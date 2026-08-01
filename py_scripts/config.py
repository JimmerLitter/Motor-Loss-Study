"""
config.py -- SINGLE SOURCE OF TRUTH for motor + thermal parameters.

Every script imports MOTOR from here. Edit parameters in this file ONLY --
never copy them into a script, or the files drift and figures stop agreeing
with each other.

Sourcing rule (state this in the report): magnetic quantities from FEA,
electrical quantities from manufacturer measurement.
"""
from dataclasses import dataclass


@dataclass
class MotorParams:
    """Physical, electrical, and thermal parameters for a single motor.

    Every loss/thermal function in this project takes a MotorParams instance
    instead of referencing a hardcoded constant -- swap in a different
    instance to run the same functions against a different motor.
    """

    name: str

    # Electrical (datasheet)
    Kv_rpm_per_v: float
    Kt_nm_per_a: float
    R_ph_ohm: float              # phase-neutral, at R_ref_temp_c
    R_ref_temp_c: float
    pole_pairs: int
    bus_voltage_v: float
    T_peak_nm: float             # datasheet peak torque (plot range)

    # Magnetic (FEMM)
    B_pk_t: float                 # peak core flux density
    core_mass_kg: float           # stator iron mass

    # Steinmetz core-loss coefficients (fit per motor/lamination)
    steinmetz_kh: float
    steinmetz_alpha: float
    steinmetz_ke: float

    # Mechanical
    windage_coeff: float          # P_windage = windage_coeff * omega^2
    friction_floor_w: float       # constant bearing-friction floor

    # Winding geometry (measured/reconciled -- see ac_copper.py)
    slot_area_m2: float
    slots: int
    phases: int
    wire_diameter_mm: float
    winding_layers: int

    # Thermal (2-node lumped model)
    R_th_k_per_w: float
    C_th_j_per_k: float
    T_max_c: float                 # insulation-limited design temperature


MOTOR = MotorParams(
    name="ODrive D5065-style outrunner",
    Kv_rpm_per_v=242,
    Kt_nm_per_a=0.034,
    R_ph_ohm=0.039,                # confirmed phase-neutral, not line-to-line
    R_ref_temp_c=25.0,
    pole_pairs=7,                  # 14 poles
    bus_voltage_v=24.0,
    T_peak_nm=1.5,

    B_pk_t=1.845,                  # FEMM magnetostatic solve, rotor angle 19.71 deg
                                    # NOTE: above the ~1.5-1.7 T knee -> core is saturated
    core_mass_kg=0.125,            # estimated from geometry (GAP 7)

    steinmetz_kh=0.03,             # generic (GAP 2)
    steinmetz_alpha=1.6,           # generic (GAP 2)
    steinmetz_ke=7e-5,             # generic (GAP 2)

    windage_coeff=1e-8,
    friction_floor_w=0.2,

    slot_area_m2=2.94367e-5,       # one slot, measured in FEMM
    slots=12,                      # 12N14P assumed -- CONFIRM in FEMM (GAP 3)
    phases=3,
    # n_per_coil = 8 is confirmed for this winding. Conductor size is NOT
    # the "12 AWG, 8 turns" figure found online -- that predicts R_ph
    # ~0.010-0.013 ohm at 8 turns, 3-4x below the measured 0.039 ohm.
    # Solving conductor area from the measured R_ph at 8 turns/coil instead
    # (see ac_copper.py's winding reconciliation table) gives ~AWG 17-18,
    # consistent with the original report estimate.
    wire_diameter_mm=1.024,        # mm, R_ph-reconciled, AWG 18
    winding_layers=8,              # turns/coil, confirmed; also slot layer count

    # R_th derived from the datasheet continuous current rating (free air,
    # I_cont = 45 A), assuming that rating targets T_max_c at steady state:
    #   R_hot = R_ph * (1 + alpha_cu*(T_max_c - 25))
    #         = 0.039 * (1 + 0.00393*95)   = 0.0536 ohm
    #   P_cu  = 3 * I_cont^2 * R_hot       = 3 * 45^2 * 0.0536  = 325 W
    #   R_th  = (T_max_c - T_amb) / P_cu   = (120 - 25) / 325   = 0.29 K/W
    # Cross-check: forced-air rating (I_cont = 65 A) gives R_th = 0.14 K/W
    # < 0.29 K/W, consistent with better cooling under forced air.
    # ASSUMPTION: datasheet's continuous rating targets T_max_c -- not
    # stated explicitly on the datasheet.
    R_th_k_per_w=0.29,
    C_th_j_per_k=60.0,
    # Insulation is Class B (130 degC). That rating governs HOTSPOT
    # temperature while the lumped model predicts MEAN winding temperature;
    # hotspot runs ~10-15 degC above mean, so 120 degC mean preserves
    # hotspot margin.
    T_max_c=120.0,
)


# ---------------- STUDY / ENVIRONMENT (not motor properties) ----------------
T_AMB_C = 25.0              # ambient temperature for this study

# Beyond this torque the R(T) feedback loop diverges (thermally
# unsustainable), so loss curves are not plotted past it.
T_PLOT_MAX_NM = 0.80

# ---------------- COPPER MATERIAL CONSTANT (not motor-specific) ----------------
ALPHA_CU_PER_C = 0.00393    # copper resistivity temp coefficient, 1/degC.
                            # Single source for losses.py (I^2R hot-resistance)
                            # and ac_copper.py (Dowell skin-depth resistivity).
