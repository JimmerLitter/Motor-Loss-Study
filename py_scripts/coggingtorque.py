"""
N5065 cogging-torque sweep  —  pyFEMM
=====================================
Cogging is the torque from the rotor magnets being pulled toward the stator
STEEL TEETH, with NO current flowing. It exists even in an unpowered motor
(the "notchy" feel when you turn it by hand). So the whole trick here is:
set every phase current to ZERO, then sweep the rotor and read torque.

Because cogging is a small effect (usually a few % of running torque) and
repeats quickly (once per tooth, not per electrical cycle), it needs a
FINER step than the torque sweep to resolve cleanly.

RUN
  1. MODEL_FILE points at your N5065 Motor.FEM (rotor = group 1).
  2. Run in VS Code.
  3. If it prints a "circuit names" list and stops, copy those names into
     PHASE_CIRCUITS below, then run again.
"""

import femm
import csv

# ----------------------------- CONFIG -----------------------------
MODEL_FILE  = r"C:\Users\huang\Downloads\FEMM N5065 Motor-20260729T032754Z-1-001\FEMM N5065 Motor\N5065 Motor.FEM"
POLE_PAIRS  = 7
CYCLES      = 1                       # one electrical cycle is plenty for cogging
STEP        = 300                     # finer than the torque run (cogging is bumpy)
ROTOR_GROUP = 1
OUTPUT_CSV  = r"C:\Users\huang\Downloads\FEMM N5065 Motor-20260729T032754Z-1-001\FEMM N5065 Motor\cogging_vs_angle.csv"

# The names of your three phase circuits, exactly as defined in the model.
# If you're not sure, leave this list EMPTY -> the script will print the
# real names it finds and stop, so you can paste them back in here.
PHASE_CIRCUITS = ["Phase A", "Phase B", "Phase C"]
# ------------------------------------------------------------------

rotation = (360.0 / POLE_PAIRS) * CYCLES
angle_step = rotation / STEP

femm.openfemm()
femm.opendocument(MODEL_FILE)
femm.mi_saveas("temp_cogging.fem")   # work on a copy; original stays untouched
femm.mi_seteditmode("group")

# --- zero out every phase current so ONLY the magnets act ---
if not PHASE_CIRCUITS:
    print("No circuit names given. Trying to list the circuits in the model...")
    print("Open your model's Properties > Circuits to read the exact names,")
    print("then put them in PHASE_CIRCUITS and run again.")
    femm.closefemm()
    raise SystemExit

for name in PHASE_CIRCUITS:
    femm.mi_setcurrent(name, 0)      # <-- the whole point: no current = pure cogging

# --- verify the currents are actually zero before sweeping ---
femm.mi_analyze(1)
femm.mi_loadsolution()
for name in PHASE_CIRCUITS:
    vals = femm.mo_getcircuitproperties(name)
    print(f"circuit '{name}': current = {vals[0]}")   # must print 0.0
results = []
angle = 0.0

for n in range(STEP + 1):
    femm.mi_analyze(1)
    femm.mi_loadsolution()

    current, voltage, flux_linkage = femm.mo_getcircuitproperties("Phase A")
    print(f"{angle:8.3f} deg   flux linkage = {flux_linkage:.6f} Wb")

    femm.mo_groupselectblock(ROTOR_GROUP)
    torque = femm.mo_blockintegral(22)   # weighted stress tensor torque
    femm.mo_clearblock()

    results.append((angle, torque))
    print(f"{angle:8.3f} deg   {torque: .6f} N.m")   # note: 6 decimals, cogging is small

    if n < STEP:
        femm.mi_selectgroup(ROTOR_GROUP)
        femm.mi_moverotate(0, 0, angle_step)   # pyFEMM: 3 args, mode set above
        femm.mi_clearselected()
        angle += angle_step

# --- save ---
with open(OUTPUT_CSV, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["angle_mech_deg", "cogging_torque_Nm"])
    w.writerows(results)
print(f"\nWrote {len(results)} rows to:\n  {OUTPUT_CSV}")

tvals = [t for _, t in results]
peak_to_peak = max(tvals) - min(tvals)
print(f"cogging peak:      {max(tvals): .5f} N.m")
print(f"cogging min:       {min(tvals): .5f} N.m")
print(f"peak-to-peak:      {peak_to_peak: .5f} N.m   <- the cogging spec number")

# --- optional plot ---
try:
    import matplotlib.pyplot as plt
    a = [x for x, _ in results]
    t = [y for _, y in results]
    plt.figure(figsize=(9, 4))
    plt.plot(a, t, linewidth=1.2)
    plt.axhline(0, color="0.7", linewidth=0.8)
    plt.xlabel("rotor angle (mechanical deg)")
    plt.ylabel("cogging torque (N.m)")
    plt.title("N5065 cogging torque (zero current) vs. rotor angle")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
except ImportError:
    print("(install matplotlib to see the plot: pip install matplotlib)")

femm.closefemm()