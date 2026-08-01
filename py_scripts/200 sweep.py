"""
N5065 fine back-EMF / torque sweep  —  pyFEMM version
=====================================================
The pyFEMM twin of the Lua sweep you validated in the console, refined to
200 steps. Same setup you confirmed works:
  - rotor tagged as group 1
  - torque via weighted stress tensor  (blockintegral type 22)
  - two electrical cycles for a 7-pole-pair motor  ->  rotation = (360/7)*2

Difference from the Lua run: this writes torque-vs-angle straight to a CSV
and plots it at the end, so there's no console copy-paste.

RUN
  1. Make sure MODEL_FILE points at your N5065 Motor.FEM (rotor = group 1).
  2. In VS Code, press Run (or:  python n5065_finesweep.py ).
  3. FEMM opens, sweeps, writes the CSV, and shows the plot.

NOTE: this rotates a working COPY (temp_sweep.fem), so your original
      N5065 Motor.FEM is never modified.
"""

import femm
import csv
import math

# ----------------------------- CONFIG -----------------------------
MODEL_FILE  = r"C:\Users\huang\Downloads\FEMM N5065 Motor-20260729T032754Z-1-001\FEMM N5065 Motor\N5065 Motor.FEM"
POLE_PAIRS  = 7                       # N5065 has 14 poles -> 7 pole pairs
CYCLES      = 2                       # electrical cycles to sweep (blog did 2)
STEP        = 200                     # number of steps (finer = smoother curve)
ROTOR_GROUP = 1                       # your rotor's group number
OUTPUT_CSV  = r"C:\Users\huang\Downloads\FEMM N5065 Motor-20260729T032754Z-1-001\FEMM N5065 Motor\torque_vs_angle_200.csv"
# ------------------------------------------------------------------

rotation = (360.0 / POLE_PAIRS) * CYCLES   # total mechanical degrees to sweep
angle_step = rotation / STEP               # degrees per step

femm.openfemm()                 # launch FEMM
femm.opendocument(MODEL_FILE)   # load your validated model
femm.mi_saveas("temp_sweep.fem")  # work on a copy so the original stays untouched
femm.mi_seteditmode("group")

results = []
angle = 0.0

for n in range(STEP + 1):
    femm.mi_analyze(1)          # solve (1 = hide the fkern window)
    femm.mi_loadsolution()

    femm.mo_groupselectblock(ROTOR_GROUP)
    torque = femm.mo_blockintegral(22)   # 22 = torque via weighted stress tensor
    femm.mo_clearblock()

    results.append((angle, torque))
    print(f"{angle:8.3f} deg   {torque: .5f} N.m")

    if n < STEP:
        femm.mi_selectgroup(ROTOR_GROUP)
        femm.mi_moverotate(0, 0, angle_step)
        femm.mi_clearselected()
        angle += angle_step

# --- write results to CSV (no more console copy-paste) ---
with open(OUTPUT_CSV, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["angle_mech_deg", "torque_Nm"])
    w.writerows(results)
print(f"\nWrote {len(results)} rows to:\n  {OUTPUT_CSV}")

# --- quick summary so you can eyeball it against the blog's ~1.37 N.m ---
tvals = [t for _, t in results]
print(f"peak torque:  {max(tvals): .4f} N.m")
print(f"min  torque:  {min(tvals): .4f} N.m")

# --- optional plot (needs: pip install matplotlib) ---
try:
    import matplotlib.pyplot as plt
    a = [x for x, _ in results]
    t = [y for _, y in results]
    plt.figure(figsize=(9, 4))
    plt.plot(a, t, linewidth=1.5)
    plt.axhline(0, color="0.7", linewidth=0.8)
    plt.xlabel("rotor angle (mechanical deg)")
    plt.ylabel("torque (N.m)")
    plt.title("N5065 torque vs. rotor angle  (= back-EMF shape) — 200 steps")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
except ImportError:
    print("(install matplotlib to see the plot: pip install matplotlib)")

femm.closefemm()