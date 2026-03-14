from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from models import ScalarFunc, SystemDefinition
from methods_equations import EquationIterationRow


def plot_equation(f: ScalarFunc, a: float, b: float, root: float | None = None) -> None:
    xs = np.linspace(a, b, 500)
    ys = np.array([f(x) for x in xs])

    plt.figure(figsize=(7, 4))
    plt.axhline(0, color="black", linewidth=1)
    plt.plot(xs, ys, label="f(x)")
    if root is not None:
        plt.scatter([root], [f(root)], color="red", label=f"root={root:.6f}", zorder=5)
    plt.xlim(a, b)
    plt.title("График нелинейного уравнения")
    plt.xlabel("x")
    plt.ylabel("f(x)")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.show()


def plot_simple_iteration(
    phi: ScalarFunc,
    a: float,
    b: float,
    rows: list[EquationIterationRow],
    root: float | None = None,
) -> None:
    xs = np.linspace(a, b, 500)
    ys_phi = np.array([phi(x) for x in xs])

    plt.figure(figsize=(7, 4))
    plt.plot(xs, xs, color="black", linewidth=1, label="y = x")
    plt.plot(xs, ys_phi, color="tab:orange", label="y = phi(x)")

    if rows:
        x0 = rows[0].x_prev
        traj_x = [x0]
        traj_y = [x0]
        for row in rows:
            traj_x.extend([row.x_prev, row.x_prev, row.x_curr])
            traj_y.extend([row.x_prev, row.x_curr, row.x_curr])
        plt.plot(
            traj_x,
            traj_y,
            color="tab:blue",
            linewidth=1.2,
            marker="o",
            markersize=3,
            label="итерации",
        )

    if root is not None:
        plt.scatter([root], [root], color="red", label=f"root={root:.6f}", zorder=5)
    plt.xlim(a, b)
    plt.title("График метода простой итерации")
    plt.xlabel("x")
    plt.ylabel("y")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.show()


def plot_system(
    system: SystemDefinition,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    solution: tuple[float, float] | None = None,
) -> None:
    x = np.linspace(x_min, x_max, 300)
    y = np.linspace(y_min, y_max, 300)
    x_grid, y_grid = np.meshgrid(x, y)
    z1 = np.vectorize(system.f1)(x_grid, y_grid)
    z2 = np.vectorize(system.f2)(x_grid, y_grid)

    plt.figure(figsize=(6, 6))
    c1 = plt.contour(x_grid, y_grid, z1, levels=[0], colors="blue")
    c2 = plt.contour(x_grid, y_grid, z2, levels=[0], colors="green")
    c1.collections[0].set_label("F1(x, y)=0")
    c2.collections[0].set_label("F2(x, y)=0")
    if solution is not None:
        plt.scatter(
            [solution[0]],
            [solution[1]],
            color="red",
            zorder=5,
            label=f"sol=({solution[0]:.4f}, {solution[1]:.4f})",
        )

    plt.xlim(x_min, x_max)
    plt.ylim(y_min, y_max)
    plt.title("Графики системы нелинейных уравнений")
    plt.xlabel("x")
    plt.ylabel("y")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.show()
