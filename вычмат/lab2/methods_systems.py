from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

from models import SystemDefinition


@dataclass
class SystemIterationRow:
    iteration: int
    x: float
    y: float
    dx: float
    dy: float
    error: float
    spectral_radius: float


@dataclass
class SystemMethodResult:
    x: float
    y: float
    iterations: int
    residual_1: float
    residual_2: float
    spectral_radius_initial: float
    rows: List[SystemIterationRow]


def _solve_2x2(
    a11: float, a12: float, a21: float, a22: float, b1: float, b2: float
) -> tuple[float, float]:
    det = a11 * a22 - a12 * a21
    if abs(det) < 1e-14:
        raise ValueError(
            "Якобиан вырожден или близок к вырожденному. "
            "Метод Ньютона не применим в данной точке."
        )
    dx = (b1 * a22 - a12 * b2) / det
    dy = (a11 * b2 - b1 * a21) / det
    return dx, dy


def spectral_radius_2x2(
    a11: float, a12: float, a21: float, a22: float,
) -> Tuple[float, float, float]:
    trace = a11 + a22
    det = a11 * a22 - a12 * a21
    discriminant = trace * trace - 4.0 * det

    if discriminant >= 0:
        sqrt_d = math.sqrt(discriminant)
        lam1 = (trace + sqrt_d) / 2.0
        lam2 = (trace - sqrt_d) / 2.0
    else:
        sqrt_d = math.sqrt(-discriminant)
        lam1 = math.sqrt((trace / 2.0) ** 2 + (sqrt_d / 2.0) ** 2)
        lam2 = lam1

    return lam1, lam2, max(abs(lam1), abs(lam2))


def newton_system_method(
    system: SystemDefinition,
    x0: float,
    y0: float,
    eps: float,
    max_iter: int,
) -> SystemMethodResult:
    x, y = x0, y0
    rows: List[SystemIterationRow] = []

    j_init = system.jacobian(x0, y0)
    _, _, rho_init = spectral_radius_2x2(
        j_init[0][0], j_init[0][1], j_init[1][0], j_init[1][1]
    )

    for iteration in range(1, max_iter + 1):
        f1 = system.f1(x, y)
        f2 = system.f2(x, y)
        j = system.jacobian(x, y)

        _, _, rho = spectral_radius_2x2(
            j[0][0], j[0][1], j[1][0], j[1][1]
        )

        dx, dy = _solve_2x2(j[0][0], j[0][1], j[1][0], j[1][1], -f1, -f2)
        x_new = x + dx
        y_new = y + dy
        error = max(abs(dx), abs(dy))
        rows.append(
            SystemIterationRow(
                iteration=iteration,
                x=x_new,
                y=y_new,
                dx=dx,
                dy=dy,
                error=error,
                spectral_radius=rho,
            )
        )
        x, y = x_new, y_new
        if error < eps:
            return SystemMethodResult(
                x=x,
                y=y,
                iterations=iteration,
                residual_1=system.f1(x, y),
                residual_2=system.f2(x, y),
                spectral_radius_initial=rho_init,
                rows=rows,
            )

    raise ValueError("Метод Ньютона для системы не сошёлся за max_iter.")
