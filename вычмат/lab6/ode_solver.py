from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, DecimalException, InvalidOperation, localcontext
from typing import Callable, Mapping, Sequence


ZERO = Decimal("0")
ONE = Decimal("1")
TWO = Decimal("2")

NumberFunction = Callable[[Decimal, Decimal], Decimal]
ExactFunction = Callable[[Decimal, Decimal, Decimal], Decimal]


class OdeInputError(ValueError):
    pass


@dataclass(frozen=True)
class Equation:
    key: str
    name: str
    formula: str
    default_x0: Decimal
    default_y0: Decimal
    default_xn: Decimal
    default_h: Decimal
    default_epsilon: Decimal
    rhs: NumberFunction
    exact: ExactFunction
    note: str


@dataclass
class GridInfo:
    x_values: list[Decimal]
    requested_xn: Decimal
    actual_xn: Decimal
    h: Decimal
    was_truncated: bool


@dataclass
class MethodSeries:
    x_values: list[Decimal]
    y_values: list[Decimal]
    name: str
    warnings: list[str] = field(default_factory=list)
    milne_iterations: list[int] = field(default_factory=list)


@dataclass
class SolutionResult:
    equation: Equation
    grid: GridInfo
    epsilon: Decimal
    exact_values: list[Decimal]
    euler: MethodSeries
    rk4: MethodSeries
    milne: MethodSeries
    euler_runge_error: Decimal
    rk4_runge_error: Decimal
    euler_exact_error: Decimal
    rk4_exact_error: Decimal
    milne_exact_error: Decimal
    warnings: list[str]


@dataclass(frozen=True)
class CauchyInput:
    x0: Decimal
    y0: Decimal
    xn: Decimal
    h: Decimal
    epsilon: Decimal


def _eq1_rhs(x: Decimal, y: Decimal) -> Decimal:
    return y + (ONE + x) * (y ** 2)


def _eq1_exact(x: Decimal, x0: Decimal, y0: Decimal) -> Decimal:
    if y0 == ZERO:
        return ZERO
    denominator = (x0 + ONE / y0) * (x0 - x).exp() - x
    if denominator == ZERO:
        raise OdeInputError(
            f"Точное решение первого уравнения не определено в точке x = {format_number(x)}."
        )
    return ONE / denominator


def _eq2_rhs(x: Decimal, y: Decimal) -> Decimal:
    return x + y


def _eq2_exact(x: Decimal, x0: Decimal, y0: Decimal) -> Decimal:
    constant = (y0 + x0 + ONE) * (-x0).exp()
    return constant * x.exp() - x - ONE


def _eq3_rhs(x: Decimal, y: Decimal) -> Decimal:
    return y - x ** 2 + ONE


def _eq3_exact(x: Decimal, x0: Decimal, y0: Decimal) -> Decimal:
    constant = (y0 - (x0 + ONE) ** 2) * (-x0).exp()
    return (x + ONE) ** 2 + constant * x.exp()


EQUATIONS: tuple[Equation, ...] = (
    Equation(
        key="eq1",
        name="Уравнение 1",
        formula="y' = y + (1 + x)y^2",
        default_x0=Decimal("1"),
        default_y0=Decimal("-1"),
        default_xn=Decimal("2"),
        default_h=Decimal("0.1"),
        default_epsilon=Decimal("0.0001"),
        rhs=_eq1_rhs,
        exact=_eq1_exact,
        note="При x0 = 1, y0 = -1 точное решение имеет вид y = -1/x.",
    ),
    Equation(
        key="eq2",
        name="Уравнение 2",
        formula="y' = x + y",
        default_x0=Decimal("0"),
        default_y0=Decimal("1"),
        default_xn=Decimal("1"),
        default_h=Decimal("0.1"),
        default_epsilon=Decimal("0.000001"),
        rhs=_eq2_rhs,
        exact=_eq2_exact,
        note="При x0 = 0, y0 = 1 точное решение: y = 2e^x - x - 1.",
    ),
    Equation(
        key="eq3",
        name="Уравнение 3",
        formula="y' = y - x^2 + 1",
        default_x0=Decimal("0"),
        default_y0=Decimal("0.5"),
        default_xn=Decimal("2"),
        default_h=Decimal("0.2"),
        default_epsilon=Decimal("0.000001"),
        rhs=_eq3_rhs,
        exact=_eq3_exact,
        note="При x0 = 0, y0 = 0.5 точное решение: y = (x + 1)^2 - 0.5e^x.",
    ),
)


def get_equation(key: str) -> Equation:
    for equation in EQUATIONS:
        if equation.key == key:
            return equation
    raise OdeInputError("Выберите одно из уравнений, предложенных программой.")


def parse_decimal(token: str, field_name: str) -> Decimal:
    raw_value = token.strip()
    if not raw_value:
        raise OdeInputError(f"Поле `{field_name}` пустое. Введите число.")
    normalized = raw_value.replace(",", ".")
    try:
        value = Decimal(normalized)
    except InvalidOperation as exc:
        raise OdeInputError(
            f"Поле `{field_name}` содержит значение `{token}`, которое не похоже на число. "
            "Используйте формат `-2`, `3.14` или `3,14`."
        ) from exc
    if not value.is_finite():
        raise OdeInputError(f"Поле `{field_name}` должно содержать конечное число.")
    return value


def parse_cauchy_input(raw_values: Mapping[str, str]) -> CauchyInput:
    fields = (
        ("x0", "x0"),
        ("y0", "y0"),
        ("xn", "xn"),
        ("h", "h"),
        ("epsilon", "epsilon"),
    )
    if not any(str(raw_values.get(key, "")).strip() for key, _ in fields):
        raise OdeInputError(
            "Ввод пустой. Укажите x0, y0, xn, h и epsilon. "
            "Можно использовать точку или запятую: `0.1` и `0,1` равнозначны."
        )

    parsed: dict[str, Decimal] = {}
    for key, label in fields:
        if key not in raw_values:
            raise OdeInputError(f"Не найдено поле `{label}`. Проверьте форму ввода.")
        parsed[key] = parse_decimal(str(raw_values[key]), label)

    return CauchyInput(
        x0=parsed["x0"],
        y0=parsed["y0"],
        xn=parsed["xn"],
        h=parsed["h"],
        epsilon=parsed["epsilon"],
    )


def generate_grid(x0: Decimal, xn: Decimal, h: Decimal, max_steps: int = 5000) -> GridInfo:
    if h <= ZERO:
        raise OdeInputError("Шаг h должен быть положительным.")
    if xn <= x0:
        raise OdeInputError("Правая граница xn должна быть больше начального значения x0.")

    interval = xn - x0
    n = (Decimal(interval) / h)
    if n <= 0:
        raise OdeInputError("Шаг h слишком большой: на заданном интервале не получается ни одного шага.")
    if n > max_steps:
        raise OdeInputError(
            f"Получается слишком много шагов: {n}. Увеличьте h или сократите интервал "
            f"(ограничение для GUI: {max_steps} шагов)."
        )

    actual_xn = x0 + h * Decimal(n)
    x_values = [x0 + h * Decimal(index) for index in range(int(n) + 1)]
    return GridInfo(
        x_values=x_values,
        requested_xn=xn,
        actual_xn=actual_xn,
        h=h,
        was_truncated=actual_xn != xn,
    )


def validate_input(x0: Decimal, y0: Decimal, xn: Decimal, h: Decimal, epsilon: Decimal) -> GridInfo:
    if epsilon <= ZERO:
        raise OdeInputError("Точность epsilon должна быть положительной.")
    grid = generate_grid(x0, xn, h)
    steps = len(grid.x_values) - 1
    if steps < 4:
        raise OdeInputError(
            f"Для метода Милна нужно минимум 4 шага, а получилось {steps}. "
            "Уменьшите h или увеличьте интервал интегрирования."
        )
    return grid


def euler(f: NumberFunction, x0: Decimal, y0: Decimal, xn: Decimal, h: Decimal) -> MethodSeries:
    grid = generate_grid(x0, xn, h)
    y_values = [y0]
    for index in range(len(grid.x_values) - 1):
        x_value = grid.x_values[index]
        y_value = y_values[-1]
        y_values.append(y_value + h * f(x_value, y_value))
    return MethodSeries(grid.x_values, y_values, "Метод Эйлера")


def _rk4_step(f: NumberFunction, x: Decimal, y: Decimal, h: Decimal) -> Decimal:
    half_h = h / TWO
    k1 = h * f(x, y)
    k2 = h * f(x + half_h, y + k1 / TWO)
    k3 = h * f(x + half_h, y + k2 / TWO)
    k4 = h * f(x + h, y + k3)
    return y + (k1 + TWO * k2 + TWO * k3 + k4) / Decimal(6)


def runge_kutta_4(
    f: NumberFunction, x0: Decimal, y0: Decimal, xn: Decimal, h: Decimal
) -> MethodSeries:
    grid = generate_grid(x0, xn, h)
    y_values = [y0]
    for index in range(len(grid.x_values) - 1):
        y_values.append(_rk4_step(f, grid.x_values[index], y_values[-1], h))
    return MethodSeries(grid.x_values, y_values, "Метод Рунге-Кутты 4-го порядка")


def milne(
    f: NumberFunction,
    x0: Decimal,
    y0: Decimal,
    xn: Decimal,
    h: Decimal,
    epsilon: Decimal,
    max_iterations: int = 100,
) -> MethodSeries:
    if epsilon <= ZERO:
        raise OdeInputError("Точность epsilon должна быть положительной.")
    grid = generate_grid(x0, xn, h)
    if len(grid.x_values) - 1 < 4:
        raise OdeInputError("Для метода Милна нужно минимум 4 шага.")

    y_values = [y0]
    for index in range(3):
        y_values.append(_rk4_step(f, grid.x_values[index], y_values[-1], h))

    warnings: list[str] = []
    iterations_by_node: list[int] = [0, 0, 0, 0]

    for index in range(4, len(grid.x_values)):
        f_i_3 = f(grid.x_values[index - 3], y_values[index - 3])
        f_i_2 = f(grid.x_values[index - 2], y_values[index - 2])
        f_i_1 = f(grid.x_values[index - 1], y_values[index - 1])

        y_predict = y_values[index - 4] + (Decimal(4) * h / Decimal(3)) * (
            TWO * f_i_3 - f_i_2 + TWO * f_i_1
        )
        y_current = y_values[index - 2] + (h / Decimal(3)) * (
            f_i_2 + Decimal(4) * f_i_1 + f(grid.x_values[index], y_predict)
        )

        used_iterations = 1
        for used_iterations in range(1, max_iterations + 1):
            y_next = y_values[index - 2] + (h / Decimal(3)) * (
                f_i_2 + Decimal(4) * f_i_1 + f(grid.x_values[index], y_current)
            )
            if abs(y_next - y_current) <= epsilon:
                y_current = y_next
                break
            y_current = y_next
        else:
            warnings.append(
                f"В узле i = {index} корректор Милна не достиг epsilon за {max_iterations} итераций."
            )

        y_values.append(y_current)
        iterations_by_node.append(used_iterations)

    return MethodSeries(
        grid.x_values,
        y_values,
        "Метод Милна",
        warnings=warnings,
        milne_iterations=iterations_by_node,
    )


def runge_rule(
    method: Callable[[NumberFunction, Decimal, Decimal, Decimal, Decimal], MethodSeries],
    f: NumberFunction,
    x0: Decimal,
    y0: Decimal,
    xn: Decimal,
    h: Decimal,
    p: int,
) -> Decimal:
    coarse = method(f, x0, y0, xn, h)
    actual_xn = coarse.x_values[-1]
    fine = method(f, x0, y0, actual_xn, h / TWO)
    denominator = Decimal(2) ** p - ONE
    values = [
        abs(coarse.y_values[index] - fine.y_values[index * 2]) / denominator
        for index in range(len(coarse.y_values))
    ]
    return max(values) if values else ZERO


def max_exact_error(
    x_values: Sequence[Decimal],
    y_values: Sequence[Decimal],
    exact_solution: Callable[[Decimal], Decimal],
) -> Decimal:
    errors = [abs(exact_solution(x_values[index]) - y_values[index]) for index in range(len(x_values))]
    return max(errors) if errors else ZERO


def solve_cauchy(
    equation_key: str,
    x0: Decimal,
    y0: Decimal,
    xn: Decimal,
    h: Decimal,
    epsilon: Decimal,
) -> SolutionResult:
    equation = get_equation(equation_key)
    precision = _required_precision([x0, y0, xn, h, epsilon])

    with localcontext() as context:
        context.prec = precision
        grid = validate_input(x0, y0, xn, h, epsilon)
        exact = lambda x: equation.exact(x, x0, y0)

        try:
            exact_values = [exact(x) for x in grid.x_values]
        except DecimalException as exc:
            raise OdeInputError(
                "Точное решение не удалось вычислить на заданном интервале: "
                "получены слишком большие или неопределённые значения. "
                "Уменьшите интервал интегрирования."
            ) from exc

        try:
            euler_result = euler(equation.rhs, x0, y0, xn, h)
        except DecimalException as exc:
            raise OdeInputError(
                "Метод Эйлера получил слишком большие численные значения. "
                f"Для h = {format_number(h)} на этом интервале расчёт неустойчив; уменьшите h."
            ) from exc

        try:
            rk4_result = runge_kutta_4(equation.rhs, x0, y0, xn, h)
        except DecimalException as exc:
            raise OdeInputError(
                "Метод Рунге-Кутты 4-го порядка получил слишком большие численные значения. "
                f"Для h = {format_number(h)} на этом интервале расчёт неустойчив; уменьшите h."
            ) from exc

        try:
            milne_result = milne(equation.rhs, x0, y0, xn, h, epsilon)
        except DecimalException as exc:
            raise OdeInputError(
                "Метод Милна расходится на заданных параметрах и получил слишком большие значения. "
                f"Для h = {format_number(h)} на интервале до xn = {format_number(xn)} "
                "уменьшите шаг h или сократите интервал интегрирования."
            ) from exc

        warnings: list[str] = []
        if grid.was_truncated:
            warnings.append(
                "Длина интервала не делится на h нацело. Сетка построена до ближайшего узла, "
                f"не превышающего xn: последний x = {format_number(grid.actual_xn)}."
            )
        warnings.extend(milne_result.warnings)

        try:
            return SolutionResult(
                equation=equation,
                grid=grid,
                epsilon=epsilon,
                exact_values=exact_values,
                euler=euler_result,
                rk4=rk4_result,
                milne=milne_result,
                euler_runge_error=runge_rule(euler, equation.rhs, x0, y0, grid.actual_xn, h, 1),
                rk4_runge_error=runge_rule(runge_kutta_4, equation.rhs, x0, y0, grid.actual_xn, h, 4),
                euler_exact_error=max_exact_error(grid.x_values, euler_result.y_values, exact),
                rk4_exact_error=max_exact_error(grid.x_values, rk4_result.y_values, exact),
                milne_exact_error=max_exact_error(grid.x_values, milne_result.y_values, exact),
                warnings=warnings,
            )
        except DecimalException as exc:
            raise OdeInputError(
                "Не удалось оценить погрешности: при дополнительном расчёте получены слишком большие "
                f"численные значения. Уменьшите h = {format_number(h)}."
            ) from exc


def format_number(value: Decimal | int | float) -> str:
    decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    if not decimal_value.is_finite():
        return str(value)
    if decimal_value == ZERO:
        return "0"

    plain = format(decimal_value, "f")
    sign = ""
    if plain.startswith("-"):
        sign = "-"
        plain = plain[1:]

    if "." not in plain:
        return sign + plain

    integer_part, fractional_part = plain.split(".", 1)
    fractional_part = fractional_part.rstrip("0")
    if not fractional_part:
        return sign + integer_part
    if len(fractional_part) <= 5:
        return sign + integer_part + "." + fractional_part

    shift = len(fractional_part) - 5
    mantissa = f"{integer_part}.{fractional_part[:5]}"
    return f"{sign}{mantissa} × 10^(-{shift})"


def format_full_report(result: SolutionResult) -> str:
    lines = [
        "# Решение задачи Коши",
        "",
        f"**Уравнение:** {result.equation.formula}",
        f"**Начальное условие:** y({format_number(result.grid.x_values[0])}) = {format_number(result.euler.y_values[0])}",
        f"**Интервал:** [{format_number(result.grid.x_values[0])}; {format_number(result.grid.requested_xn)}]",
        f"**Шаг:** h = {format_number(result.grid.h)}",
        f"**Точность корректора Милна:** epsilon = {format_number(result.epsilon)}",
        f"**Комментарий к точному решению:** {result.equation.note}",
        "",
    ]

    if result.warnings:
        lines.append("**Предупреждения:**")
        for warning in result.warnings:
            lines.append(f"> {warning}")
        lines.append("")

    lines.extend(
        [
            "## Оценка точности",
            "",
            f"**Метод Эйлера, правило Рунге:** {format_number(result.euler_runge_error)}",
            f"**Рунге-Кутта 4-го порядка, правило Рунге:** {format_number(result.rk4_runge_error)}",
            f"**Метод Милна, max |yточн - yi|:** {format_number(result.milne_exact_error)}",
            "",
            f"Дополнительно по точному решению: Эйлер = {format_number(result.euler_exact_error)}, "
            f"РК4 = {format_number(result.rk4_exact_error)}.",
            "",
            "## Таблица значений",
            "",
            format_result_table(result),
            "",
            "## Анализ",
            "",
            "- Метод Эйлера является явным одношаговым методом: он использует касательную в текущей точке и имеет порядок O(h).",
            "- Метод Рунге-Кутты 4-го порядка является явным одношаговым методом: на каждом шаге вычисляет четыре коэффициента и использует их взвешенное среднее.",
            "- Рунге-Кутта 4-го порядка обычно заметно точнее метода Эйлера при том же h, но требует больше вычислений функции f на шаг.",
            "- Метод Милна является многошаговым методом предиктор-корректор: сначала строит прогноз, затем уточняет его коррекцией.",
            "- Метод Милна имеет порядок O(h^4), использует несколько предыдущих значений, а первые три новые точки получены методом РК4.",
            "- Для одношаговых методов точность оценена правилом Рунге, для метода Милна — через max |yточн - yi|.",
            "- При уменьшении h точность обычно растёт, но увеличивается число узлов и вычислений.",
        ]
    )
    return "\n".join(lines)


def format_result_table(result: SolutionResult) -> str:
    headers = [
        "i",
        "x_i",
        "y_exact",
        "Euler",
        "RK4",
        "Milne",
        "|ex-E|",
        "|ex-RK4|",
        "|ex-M|",
    ]
    rows = []
    for index, x_value in enumerate(result.grid.x_values):
        y_exact = result.exact_values[index]
        y_euler = result.euler.y_values[index]
        y_rk4 = result.rk4.y_values[index]
        y_milne = result.milne.y_values[index]
        rows.append(
            [
                str(index),
                format_number(x_value),
                format_number(y_exact),
                format_number(y_euler),
                format_number(y_rk4),
                format_number(y_milne),
                format_number(abs(y_exact - y_euler)),
                format_number(abs(y_exact - y_rk4)),
                format_number(abs(y_exact - y_milne)),
            ]
        )

    widths = [
        max(len(headers[column]), *(len(row[column]) for row in rows))
        for column in range(len(headers))
    ]
    lines = [
        "    "
        + " | ".join(headers[column].rjust(widths[column]) for column in range(len(headers))),
        "    "
        + "-+-".join("-" * widths[column] for column in range(len(headers))),
    ]
    for row in rows:
        lines.append(
            "    "
            + " | ".join(row[column].rjust(widths[column]) for column in range(len(headers)))
        )
    return "\n".join(lines)


def _required_precision(values: Sequence[Decimal]) -> int:
    finite_values = [value for value in values if value.is_finite()]
    significant = max(len(value.as_tuple().digits) for value in finite_values)
    fractional = max(max(0, -value.as_tuple().exponent) for value in finite_values)
    return max(100, significant + fractional + 50)
    return  10
