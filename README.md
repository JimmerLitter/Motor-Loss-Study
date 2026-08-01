# BLDC Motor Loss & Thermal Study

A loss and thermal model for a BLDC/PMSM outrunner (ODrive D5065-style, 24 V bus), built as part of the [Motor Design](../) portfolio project. Given a single `MotorParams` definition, the pipeline computes copper (DC + AC-corrected), core/iron, and mechanical losses across the full torque-speed envelope, couples them to a lumped-parameter thermal model, and renders the result as a set of report-ready figures (efficiency maps, thermal limit curve, per-mechanism loss maps).

The model is motor-agnostic: every loss/thermal function takes a `MotorParams` instance rather than hardcoding constants, so swapping in a different motor's datasheet + FEMM numbers reruns the whole study.

## Quick start

```
python py_scripts/run_study.py
```

Regenerates every figure in `figures/` and prints the report numbers (representative speed, continuous torque, peak-hold time, peak efficiency) to stdout. Edit motor parameters in `py_scripts/config.py` — never inline a constant in a script.

## Folder structure

- **`py_scripts/`** — the model itself.
  - `config.py` — single source of truth: the `MotorParams` dataclass and the `MOTOR` instance (electrical/magnetic/mechanical/thermal parameters + provenance notes on each number).
  - `losses.py` — copper (I²R), Steinmetz core, and windage/friction loss functions, plus efficiency.
  - `ac_copper.py` — AC copper effects DC I²R misses: skin effect, Dowell proximity ratio, and the winding-geometry reconciliation that pins down actual wire gauge from measured phase resistance.
  - `thermal.py` — 2-node lumped thermal model with copper R(T) feedback; steady winding temp, continuous torque limit, peak-hold time.
  - `plot_losses.py` — the loss-breakdown figure (log-magnitude + 100%-composition panels) and the shared plot style/palette.
  - `loss_taxonomy.py` — standalone diagram of the loss-mechanism hierarchy (Motor Losses → Copper/Core/Mechanical → individual physics).
  - `run_study.py` — single entry point; drives every other module to produce all figures in `figures/`.
- **`figures/`** — generated PNGs (efficiency maps, thermal limit, per-mechanism loss maps, output/input power, AC resistance ratio). All reproducible from `run_study.py` — not hand-edited.
- **`md files/`** — report planning and drafting: guiding questions, a 1-day plan/report skeleton, and the report draft itself.

## Notes

- Magnetic quantities (peak flux density, etc.) come from FEMM; electrical quantities come from manufacturer datasheet/measurement — see the sourcing comments in `config.py`.
- Two efficiency maps exist on purpose: `efficiency_map.png` (DC-copper only, from `losses.py`) and `efficiency_map_clean.png` (AC-corrected, self-consistent with the total/input power figures). The clean version is the one to cite.
