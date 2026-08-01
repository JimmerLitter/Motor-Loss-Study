"""
loss_taxonomy.py -- Hierarchical breakdown of every loss mechanism modeled
in this study: Motor Losses -> {Copper, Core/Iron, Mechanical} -> the
individual physical mechanisms (and, for AC copper, one level deeper still
into skin/proximity effect).

This is a taxonomy diagram, not a data plot -- it has no x/y axes. Kept
standalone (imports only config.MOTOR, not plot_losses/thermal/losses) so
it renders independently of the rest of the pipeline.

Run:  python loss_taxonomy.py   # writes figures/loss_taxonomy.png
"""

import os
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from config import MOTOR

# ---- design tokens -- mirrors plot_losses.py's validated palette. Kept as
# a local copy (not an import) because plot_losses.py currently depends on
# config names still being migrated; re-point this at plot_losses once that
# settles, rather than duplicate colors indefinitely.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
BASELINE = "#c3c2b7"
C_COPPER, C_IRON, C_MECH = "#2a78d6", "#eb6834", "#1baf7a"

m = MOTOR

TREE = {
    "label": "Motor Losses",
    "formula": "P_loss = P_cu + P_fe + P_mech",
    "color": INK,
    "fill": "#eceae4",
    "children": [
        {
            "label": "Copper Losses",
            "formula": "I²R (electrical)",
            "color": C_COPPER,
            "children": [
                {
                    "label": "DC Copper Loss",
                    "formula": f"P = 3·I_ph²·R_ph(T)\nR_ph={m.R_ph_ohm} Ω  Kt={m.Kt_nm_per_a} N·m/A",
                    "color": C_COPPER,
                    "children": [],
                },
                {
                    "label": "AC Copper Loss",
                    "formula": "DC loss × Dowell R_ac/R_dc",
                    "color": C_COPPER,
                    "children": [
                        {
                            "label": "Skin Effect",
                            "formula": "δ = √(ρ / (π f μ₀))",
                            "color": C_COPPER,
                            "children": [],
                        },
                        {
                            "label": "Proximity Effect",
                            "formula": f"∝ (n_layers²−1)\nn_layers={m.winding_layers}",
                            "color": C_COPPER,
                            "children": [],
                        },
                    ],
                },
            ],
        },
        {
            "label": "Core (Iron) Losses",
            "formula": "Steinmetz model",
            "color": C_IRON,
            "children": [
                {
                    "label": "Hysteresis Loss",
                    "formula": f"k_h·f·B^α\nk_h={m.steinmetz_kh}  α={m.steinmetz_alpha}",
                    "color": C_IRON,
                    "children": [],
                },
                {
                    "label": "Eddy Current Loss",
                    "formula": f"k_e·f²·B²\nk_e={m.steinmetz_ke:.0e}",
                    "color": C_IRON,
                    "children": [],
                },
            ],
        },
        {
            "label": "Mechanical Losses",
            "formula": "Rotational",
            "color": C_MECH,
            "children": [
                {
                    "label": "Bearing Friction",
                    "formula": f"constant floor\nP = {m.friction_floor_w} W",
                    "color": C_MECH,
                    "children": [],
                },
                {
                    "label": "Windage",
                    "formula": f"k_windage·ω²\nk_windage={m.windage_coeff:.0e}",
                    "color": C_MECH,
                    "children": [],
                },
            ],
        },
    ],
}


def assign_x(node, counter):
    """Post-order layout: leaves get the next free slot, parents center over children."""
    if not node["children"]:
        node["_x"] = counter[0]
        counter[0] += 1
        return node["_x"]
    xs = [assign_x(c, counter) for c in node["children"]]
    node["_x"] = sum(xs) / len(xs)
    return node["_x"]


def assign_y(node, depth=0):
    """Row position by tree depth: root at depth 0, each level one row down."""
    node["_y"] = -depth
    for c in node["children"]:
        assign_y(c, depth + 1)


def hex_to_rgb(h):
    """'#rrggbb' -> (r, g, b) floats in [0, 1]."""
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))


def tint(color, amount=0.88):
    """Lighten a hue toward SURFACE for box fills -- text/edges keep full color."""
    r, g, b = hex_to_rgb(color)
    sr, sg, sb = hex_to_rgb(SURFACE)
    return (r + (sr - r) * amount, g + (sg - g) * amount, b + (sb - b) * amount)


UNIT_X, UNIT_Y = 2.6, 1.9
BOX_W, BOX_H = 2.3, 1.05


def draw_box(ax, node, is_root=False):
    """Render one node: its rounded box, bold label, and formula subtext."""
    x, y = node["_x"] * UNIT_X, node["_y"] * UNIT_Y
    fill = "#eceae4" if is_root else tint(node["color"])
    box = FancyBboxPatch(
        (x - BOX_W / 2, y - BOX_H / 2),
        BOX_W,
        BOX_H,
        boxstyle="round,pad=0.05,rounding_size=0.10",
        linewidth=1.4,
        edgecolor=node["color"],
        facecolor=fill,
        zorder=3,
    )
    ax.add_patch(box)

    has_formula = bool(node.get("formula"))
    title_y = y + (0.16 if has_formula else 0.0)
    ax.text(
        x,
        title_y,
        node["label"],
        ha="center",
        va="center",
        fontsize=10.5 if is_root else 9.5,
        fontweight="bold",
        color=INK,
        zorder=4,
    )
    if has_formula:
        ax.text(
            x,
            y - 0.22,
            node["formula"],
            ha="center",
            va="center",
            fontsize=7.3,
            color=INK_2,
            linespacing=1.5,
            zorder=4,
        )


def draw_connector(ax, parent, child):
    """Elbow line from a parent box's bottom edge to a child box's top edge."""
    x, y = parent["_x"] * UNIT_X, parent["_y"] * UNIT_Y
    cx, cy = child["_x"] * UNIT_X, child["_y"] * UNIT_Y
    mid_y = (y - BOX_H / 2 + cy + BOX_H / 2) / 2.0
    ax.plot(
        [x, x, cx, cx],
        [y - BOX_H / 2, mid_y, mid_y, cy + BOX_H / 2],
        color=BASELINE,
        linewidth=1.2,
        zorder=1,
        solid_capstyle="round",
    )


def draw_tree(ax, node, is_root=False):
    """Recursively render a node, then its connectors and children."""
    draw_box(ax, node, is_root=is_root)
    for child in node["children"]:
        draw_connector(ax, node, child)
        draw_tree(ax, child)


if __name__ == "__main__":
    # Anchor to the project root so 'figures/' always resolves to the same
    # folder no matter what directory this is run from.
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    os.makedirs("figures", exist_ok=True)

    leaf_counter = [0]
    assign_x(TREE, leaf_counter)
    assign_y(TREE)
    n_leaves = leaf_counter[0]

    fig, ax = plt.subplots(figsize=(0.5 + UNIT_X * n_leaves, 8.0))
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    draw_tree(ax, TREE, is_root=True)

    ax.set_xlim(-BOX_W, (n_leaves - 1) * UNIT_X + BOX_W)
    ax.set_ylim(-3 * UNIT_Y - BOX_H, BOX_H)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(
        "Loss taxonomy: every mechanism modeled in this study",
        color=INK,
        fontsize=12,
        pad=4,
        loc="left",
    )

    fig.tight_layout()
    out = "figures/loss_taxonomy.png"
    fig.savefig(out, dpi=200, facecolor=SURFACE, bbox_inches="tight")
    print(f"wrote {out}")
