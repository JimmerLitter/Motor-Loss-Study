# Code Style Guidelines

This file is auto-loaded by Claude Code at the start of every session in this
project. Follow these rules for all code written or edited here.

## Domain Structure
- All motor-specific parameters (R_phase, L_d, L_q, pole pairs, kV, flux
  linkage, rotor inertia, etc.) live in a single `MotorParams` dataclass —
  never hardcode a motor constant inline in a loss function.
- Loss functions take a `MotorParams` instance plus an operating point
  (speed, current, temperature, etc.) as arguments. They must work for any
  `MotorParams` instance, not just the motor currently on the bench.
- Keep each loss mechanism (copper loss, core/iron loss, windage/friction,
  switching loss, etc.) in its own function or module. No monolithic
  `compute_all_losses()` with everything inlined — compose the small
  functions instead.
- New motor topologies or loss mechanisms should be addable without editing
  existing functions — add a new function/module, not new branches in an
  existing one.

## Physics Documentation
- Every equation gets ONE docstring/comment block above the function: what
  it computes, the governing equation in symbol form, units, and the source
  (textbook, paper, datasheet) if it's non-obvious.
- Do not comment individual lines inside an equation implementation
  (e.g. no `# square the current` above `I**2`). Clear variable names and
  the top-level docstring should make the line readable on its own.
- State units in variable names (e.g. `omega_rad_s`, `T_nm`, `R_ohm`) rather
  than in comments explaining what unit something is in.
- No comment above every line. Reserve inline comments for genuinely
  non-obvious logic, edge cases, or a "why," never a restatement of "what."

## Numerical Code
- Prefer explicit, readable equations over "clever" vectorized one-liners
  when translating a physics formula — the code should be checkable against
  the equation by eye.
- Convert units once at the input boundary (e.g. RPM -> rad/s) and work in
  consistent SI units internally. Don't scatter unit conversions through
  functions.
- Don't add defensive code, logging, or error handling beyond what's asked
  unless it's clearly needed for correctness.

## Formatting
- Keep functions short and single-purpose. If a function does more than one
  thing, split it.
- No nested ternaries or overly clever one-liners — prefer clarity over
  brevity.
- Format with `black` (or the project's configured formatter) before
  finishing any task.
- Avoid unnecessary abstraction layers (no wrapper classes/interfaces
  unless there's a real second implementation that needs it).
- Delete commented-out or dead code — don't leave it with an explanatory
  note.

## Self-check
- When asked to review a file, check it against every rule above and
  simplify/re-comment anything that violates one, rather than just
  addressing the specific line mentioned.

  """
  """Motor parameter definitions for the BLDC loss generator.

Every loss/physics function in this project should take a MotorParams
instance as input rather than referencing hardcoded constants. This is
what makes the loss model reusable across different motors.

Below is example code for motorparams, take config and mold it in example below
"""

from dataclasses import dataclass


@dataclass
class MotorParams:
    """Physical and electrical parameters for a single BLDC motor.

    All values are stored in SI units. Convert at the point of input
    (e.g. datasheet RPM/mOhm values) rather than inside loss functions.
    """

    name: str

    # Electrical
    R_phase_ohm: float          # phase resistance
    L_d_h: float                # d-axis inductance
    L_q_h: float                # q-axis inductance
    pole_pairs: int
    flux_linkage_wb: float      # permanent magnet flux linkage

    # Mechanical
    rotor_inertia_kgm2: float
    friction_coeff_nms: float   # viscous friction coefficient

    # Core loss model coefficients (e.g. Steinmetz-style, fit per motor)
    core_loss_coeff_hysteresis: float
    core_loss_coeff_eddy: float


# Example instantiation for the motor currently on the bench.
# Swap this out (or load from a config file / CSV) to run the same
# loss functions against a different motor.
EXAMPLE_MOTOR = MotorParams(
    name="bench_motor_v1",
    R_phase_ohm=0.0,
    L_d_h=0.0,
    L_q_h=0.0,
    pole_pairs=0,
    flux_linkage_wb=0.0,
    rotor_inertia_kgm2=0.0,
    friction_coeff_nms=0.0,
    core_loss_coeff_hysteresis=0.0,
    core_loss_coeff_eddy=0.0,
)

"""
