from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Tuple

from models import EquationDefinition


ScalarFunc = Callable[[float], float]


@dataclass
class EquationIterationRow:
    iteration: int
    x_prev: float
    x_curr: float
    f_curr: float
    error: float


@dataclass
class EquationMethodResult:
    root: float
    f_root: float
    iterations: int
    rows: List[EquationIterationRow]


def _estimate_second_derivative(f: ScalarFunc, x: float, h: float = 1e-5) -> float:
    return (f(x + h) - 2 * f(x) + f(x - h)) / (h * h)


def count_sign_changes(f: ScalarFunc, a: float, b: float, samples: int = 400) -> int:
    if b <= a:
        return 0
    step = (b - a) / samples
    prev = f(a)
    changes = 0
    for i in range(1, samples + 1):
        x = a + i * step
        cur = f(x)
        if prev == 0:
            prev = cur
            continue
        if cur == 0:
            continue
        if prev * cur < 0:
            changes += 1
        prev = cur
    return changes


def validate_interval(f: ScalarFunc, a: float, b: float) -> Tuple[bool, str]:
    if b <= a:
        return False, "Правая граница должна быть больше левой."
    sign_changes = count_sign_changes(f, a, b)
    if sign_changes == 0:
        return False, "На интервале не найдено смены знака (корень может отсутствовать)."
    if sign_changes > 1:
        return False, "На интервале обнаружено несколько смен знака (возможно несколько корней)."
    return True, "Интервал корректный."


def bisection_method(
    equation: EquationDefinition,
    a: float,
    b: float,
    eps: float,
    max_iter: int,
) -> EquationMethodResult:
    f = equation.f
    fa = f(a)
    fb = f(b)
    if fa * fb > 0:
        raise ValueError("Для половинного деления требуется f(a)*f(b) < 0.")

    rows: List[EquationIterationRow] = []
    x_prev = a
    x_curr = (a + b) / 2

    for iteration in range(1, max_iter + 1):
        x_curr = (a + b) / 2
        fx = f(x_curr)
        error = abs(b - a)
        rows.append(
            EquationIterationRow(
                iteration=iteration,
                x_prev=x_prev,
                x_curr=x_curr,
                f_curr=fx,
                error=error,
            )
        )
        if abs(fx) < eps or error < eps:
            return EquationMethodResult(x_curr, fx, iteration, rows)
        if fa * fx < 0:
            b = x_curr
            fb = fx
        else:
            a = x_curr
            fa = fx
        x_prev = x_curr

    raise ValueError("Метод половинного деления не сошелся за max_iter.")


def choose_newton_start(equation: EquationDefinition, a: float, b: float) -> float:
    f = equation.f
    if f(a) * _estimate_second_derivative(f, a) > 0:
        return a
    return b


def choose_simple_iteration_start(equation: EquationDefinition, a: float, b: float) -> float:
    dphi = equation.dphi
    return a if abs(dphi(a)) <= abs(dphi(b)) else b


def newton_method(
    equation: EquationDefinition,
    a: float,
    b: float,
    eps: float,
    max_iter: int,
) -> EquationMethodResult:
    f = equation.f
    df = equation.df
    x_prev = choose_newton_start(equation, a, b)
    rows: List[EquationIterationRow] = []

    for iteration in range(1, max_iter + 1):
        dfx = df(x_prev)
        """if abs(dfx) < 1e-14:
            raise ValueError("Производная близка к нулю, метод Ньютона остановлен.")"""
        x_curr = x_prev - f(x_prev) / dfx
        fx = f(x_curr)
        error = abs(x_curr - x_prev)
        rows.append(
            EquationIterationRow(
                iteration=iteration,
                x_prev=x_prev,
                x_curr=x_curr,
                f_curr=fx,
                error=error,
            )
        )
        if error < eps or abs(fx) < eps:
            return EquationMethodResult(x_curr, fx, iteration, rows)
        x_prev = x_curr

    raise ValueError("Метод Ньютона не сошелся за max_iter.")


"""def check_simple_iteration_convergence(
    equation: EquationDefinition, a: float, b: float, samples: int = 300
) -> Tuple[bool, float]:
    dphi = equation.dphi
    step = (b - a) / samples
    q = 0.0
    for i in range(samples + 1):
        x = a + i * step
        q = max(q, abs(dphi(x)))
    return q < 1.0, q"""


def simple_iteration_method(
    equation: EquationDefinition,
    a: float,
    b: float,
    eps: float,
    max_iter: int,
    x0: float | None = None,
) -> EquationMethodResult:
    if x0 is None:
        x0 = choose_simple_iteration_start(equation, a, b)
    phi = equation.phi
    f = equation.f
    x_prev = x0
    rows: List[EquationIterationRow] = []

    for iteration in range(1, max_iter + 1):
        x_curr = phi(x_prev)
        fx = f(x_curr)
        error = abs(x_curr - x_prev)
        rows.append(
            EquationIterationRow(
                iteration=iteration,
                x_prev=x_prev,
                x_curr=x_curr,
                f_curr=fx,
                error=error,
            )
        )
        if error < eps or abs(fx) < eps:
            return EquationMethodResult(x_curr, fx, iteration, rows)
        x_prev = x_curr

    raise ValueError("Метод простой итерации не сошелся за max_iter.")
