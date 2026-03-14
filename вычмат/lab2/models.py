from __future__ import annotations

from dataclasses import dataclass
from math import cos, exp, log, sin, tan
from typing import Callable, List, Tuple


ScalarFunc = Callable[[float], float]
SystemFunc = Callable[[float, float], float]


@dataclass(frozen=True)
class EquationDefinition:
    equation_id: str
    title: str
    phi_expr: str
    f: ScalarFunc
    df: ScalarFunc
    phi: ScalarFunc
    dphi: ScalarFunc


@dataclass(frozen=True)
class SystemDefinition:
    system_id: str
    title: str
    f1: SystemFunc
    f2: SystemFunc
    jacobian: Callable[[float, float], Tuple[Tuple[float, float], Tuple[float, float]]]


def _cbrt(x: float) -> float:
    if x >= 0:
        return x ** (1.0 / 3.0)
    return -((-x) ** (1.0 / 3.0))


def get_equations() -> List[EquationDefinition]:
    return [
        EquationDefinition(
            equation_id="eq_1",
            title="x^3 - 4.5x^2 - 9.21x - 0.383",
            phi_expr="(4.5x^2 + 9.21x + 0.383)^(1/3)",
            f=lambda x: x**3 - 4.5 * x**2 - 9.21 * x - 0.383,
            df=lambda x: 3 * x**2 - 9.0 * x - 9.21,
            phi=lambda x: _cbrt(4.5 * x**2 + 9.21 * x + 0.383),
            dphi=lambda x: (9.0 * x + 9.21)
            / (3.0 * (4.5 * x**2 + 9.21 * x + 0.383) ** (2.0 / 3.0)),
        ),
        EquationDefinition(
            equation_id="eq_2",
            title="x^3 - 3.125x^2 - 3.5x + 2.458",
            phi_expr="(3.125x^2 + 3.5x - 2.458)^(1/3)",
            f=lambda x: x**3 - 3.125 * x**2 - 3.5 * x + 2.458,
            df=lambda x: 3 * x**2 - 6.25 * x - 3.5,
            phi=lambda x: _cbrt(3.125 * x**2 + 3.5 * x - 2.458),
            dphi=lambda x: (6.25 * x + 3.5)
            / (3.0 * abs(3.125 * x**2 + 3.5 * x - 2.458) ** (2.0 / 3.0)),
        ),
        EquationDefinition(
            equation_id="eq_3",
            title="x^3 - 2.92x^2 + 1.435x + 0.791",
            phi_expr="(2.92x^2 - 1.435x - 0.791)^(1/3)",
            f=lambda x: x**3 - 2.92 * x**2 + 1.435 * x + 0.791,
            df=lambda x: 3 * x**2 - 5.84 * x + 1.435,
            phi=lambda x: _cbrt(2.92 * x**2 - 1.435 * x - 0.791),
            dphi=lambda x: (5.84 * x - 1.435)
            / (3.0 * abs(2.92 * x**2 - 1.435 * x - 0.791) ** (2.0 / 3.0)),
        ),
        EquationDefinition(
            equation_id="eq_4",
            title="sin(x) - x/2",
            phi_expr="2sin(x)",
            f=lambda x: sin(x) - x / 2.0,
            df=lambda x: cos(x) - 0.5,
            phi=lambda x: 2.0 * sin(x),
            dphi=lambda x: 2.0 * cos(x),
        ),
        EquationDefinition(
            equation_id="eq_5",
            title="e^x - 3x",
            phi_expr="e^x / 3",
            f=lambda x: exp(x) - 3.0 * x,
            df=lambda x: exp(x) - 3.0,
            phi=lambda x: exp(x) / 3.0,
            dphi=lambda x: exp(x) / 3.0,
        ),
    ]


def get_systems() -> List[SystemDefinition]:
    return [
        SystemDefinition(
            system_id="sys_1",
            title="{ x + sin(y) = -0.4;  2y - cos(x+1) = 0 }",
            f1=lambda x, y: x + sin(y) + 0.4,
            f2=lambda x, y: 2.0 * y - cos(x + 1.0),
            jacobian=lambda x, y: (
                (1.0, cos(y)),
                (sin(x + 1.0), 2.0),
            ),
        ),
        SystemDefinition(
            system_id="sys_2",
            title="{ sin(x+y) - 1.2x = 0.2;  x^2 + 2y^2 = 1 }",
            f1=lambda x, y: sin(x + y) - 1.2 * x - 0.2,
            f2=lambda x, y: x**2 + 2.0 * y**2 - 1.0,
            jacobian=lambda x, y: (
                (cos(x + y) - 1.2, cos(x + y)),
                (2.0 * x, 4.0 * y),
            ),
        ),
        SystemDefinition(
            system_id="sys_3",
            title="{ tan(xy+0.3) = x^2;  0.9x^2 + 2y^2 = 1 }",
            f1=lambda x, y: tan(x * y + 0.3) - x**2,
            f2=lambda x, y: 0.9 * x**2 + 2.0 * y**2 - 1.0,
            jacobian=lambda x, y: (
                (y / cos(x * y + 0.3) ** 2 - 2.0 * x,
                 x / cos(x * y + 0.3) ** 2),
                (1.8 * x, 4.0 * y),
            ),
        ),
    ]
