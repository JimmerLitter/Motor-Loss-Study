"""
N5065 peak core flux density  —  Method 2 (numeric, scripted)
=============================================================
Finds the peak flux density |B| in the STATOR STEEL across the rotor sweep.
That peak is what feeds core-loss (Steinmetz) estimates.

How it finds "the steel" without exact radii:
  It samples a grid of points over the motor area and, at each point, asks
  FEMM for the material's relative permeability (mu). Steel has mu in the
  hundreds-to-thousands; air/copper/magnet are ~1. So we keep only points
  with mu above a threshold -> those are in the iron. No radii needed.

Because flux redistributes as the rotor turns, "peak core flux density" is
the MAX over the whole electrical cycle, so we sample at every rotor step.

RUN
  1. MODEL_FILE points at your N5065 Motor.FEM (rotor = group 1).
  2. Run in VS Code.
  3. It prints the peak core |B| and where it occurred.
"""

import femm
import csv
import math

# ----------------------------- CONFIG -----------------------------
MODEL_FILE   = r"C:\Users\huang\Downloads\FEMM N5065 Motor-20260729T032754Z-1-001\FEMM N5065 Motor\N5065 Motor.FEM"
POLE_PAIRS   = 7
CYCLES       = 1
STEP         = 60                # coarser is fine; we want peak B, not a smooth curve
ROTOR_GROUP  = 1
OUTER_R      = 25.0              # mm — rough outer radius you read off (bounds the search)
GRID_N       = 120              # sampling resolution across the box (120x120 grid)
MU_STEEL_MIN = 100              # relative-permeability threshold to count a point as steel
B_ARTIFACT   = 2.5              # |B| above this is flagged as a likely corner artifact (T)
OUTPUT_CSV   = r"C:\Users\huang\Downloads\FEMM N5065 Motor-20260729T032754Z-1-001\FEMM N5065 Motor\peak_core_B.csv"
# ------------------------------------------------------------------

rotation = (360.0 / POLE_PAIRS) * CYCLES
angle_step = rotation / STEP

# build the sample grid once (square box a bit inside OUTER_R so we skip rotor/airgap edge)
lim = OUTER_R * 0.98
xs = [(-lim + 2 * lim * i / (GRID_N - 1)) for i in range(GRID_N)]
ys = xs[:]  # same range vertically

femm.openfemm()
femm.opendocument(MODEL_FILE)
femm.mi_saveas("temp_coreB.fem")
femm.mi_seteditmode("group")

per_angle = []          # (angle, peak_B_this_angle, x, y)
global_peak = 0.0
global_where = (0.0, 0.0, 0.0)   # (angle, x, y) of the overall peak
angle = 0.0

for n in range(STEP + 1):
    femm.mi_analyze(1)
    femm.mi_loadsolution()

    step_peak = 0.0
    step_xy = (0.0, 0.0)

    for x in xs:
        for y in ys:
            # mo_getpointvalues returns a tuple of field quantities at (x,y).
            # If the point is outside the meshed region it returns zeros/None.
            vals = femm.mo_getpointvalues(x, y)
            if vals is None:
                continue
            # unpack the pieces we need: flux density Bx, By and permeabilities mux, muy
            # (FEMM order: A, B1(Bx), B2(By), Sig, E, H1, H2, Je, Js, Mu1, Mu2, Pe, Ph)
            Bx = vals[1]
            By = vals[2]
            mux = vals[9]
            muy = vals[10]
            mu = max(mux, muy)
            if mu < MU_STEEL_MIN:      # not steel (air/copper/magnet) -> skip
                continue
            b = math.sqrt(Bx * Bx + By * By)
            if b > step_peak:
                step_peak = b
                step_xy = (x, y)

    per_angle.append((angle, step_peak, step_xy[0], step_xy[1]))
    if step_peak > global_peak:
        global_peak = step_peak
        global_where = (angle, step_xy[0], step_xy[1])

    print(f"angle {angle:7.2f}   peak core |B| = {step_peak:5.3f} T")

    if n < STEP:
        femm.mi_selectgroup(ROTOR_GROUP)
        femm.mi_moverotate(0, 0, angle_step)
        femm.mi_clearselected()
        angle += angle_step

# --- save per-angle peaks ---
with open(OUTPUT_CSV, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["angle_mech_deg", "peak_core_B_T", "x_mm", "y_mm"])
    w.writerows(per_angle)

# --- report ---
ga, gx, gy = global_where
gr = math.sqrt(gx * gx + gy * gy)
print("\n" + "=" * 48)
print(f"PEAK CORE FLUX DENSITY:  {global_peak:.3f} T")
print(f"  occurred at rotor angle {ga:.2f} deg")
print(f"  at point ({gx:.2f}, {gy:.2f}) mm  ->  radius {gr:.2f} mm")
print("=" * 48)
if global_peak > B_ARTIFACT:
    print(f"NOTE: {global_peak:.2f} T is very high — likely a sharp-corner")
    print("      singularity, not real bulk saturation. Check the location:")
    print("      if it's a tooth-tip corner, the true working B is lower.")
else:
    print("This is in a physically sane range for laminated silicon steel")
    print("(~1.5-2.0 T saturation). Good for a core-loss estimate.")

femm.closefemm()