from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, DecimalException, InvalidOperation, getcontext, localcontext
import math
import re
from typing import Callable, Sequence


ZERO = Decimal("0")
ONE = Decimal("1")
TWO = Decimal("2")
EPS = Decimal("1e-12")
PI = Decimal(str(math.pi))
TWO_PI = PI * TWO


class InterpolationError(ValueError):
    pass


@dataclass
class MethodResult:
    name: str
    value: Decimal
    formula: str
    warning: str | None = None


@dataclass
class InterpolationAnalysis:
    points: list[tuple[Decimal, Decimal]]
    x_value: Decimal
    finite_differences: list[list[Decimal]]
    results: list[MethodResult]
    issues: list[str]
    source_function_name: str | None = None
    exact_value: Decimal | None = None
    is_extrapolation: bool = False


@dataclass(frozen=True)
class FunctionSpec:
    name: str
    evaluator: Callable[[Decimal], Decimal]
    label: str


def decimal_sin(value: Decimal) -> Decimal:
    x = _reduce_angle(value)
    term = x
    result = x
    order = 1
    threshold = Decimal(1).scaleb(-(getcontext().prec + 8))
    while abs(term) > threshold:
        denominator = Decimal((2 * order) * (2 * order + 1))
        term *= -(x * x) / denominator
        result += term
        order += 1
        if order > 200:
            break
    return +result


def decimal_cos(value: Decimal) -> Decimal:
    x = _reduce_angle(value)
    term = ONE
    result = ONE
    order = 1
    threshold = Decimal(1).scaleb(-(getcontext().prec + 8))
    while abs(term) > threshold:
        denominator = Decimal((2 * order - 1) * (2 * order))
        term *= -(x * x) / denominator
        result += term
        order += 1
        if order > 200:
            break
    return +result


def _reduce_angle(value: Decimal) -> Decimal:
    reduced = value.remainder_near(TWO_PI)
    if reduced > PI:
        reduced -= TWO_PI
    elif reduced < -PI:
        reduced += TWO_PI
    return reduced


FUNCTIONS: tuple[FunctionSpec, ...] = (
    FunctionSpec("sin(x)", decimal_sin, "sin(x)"),
    FunctionSpec("cos(x)", decimal_cos, "cos(x)"),
    FunctionSpec("x^2 + x + 1", lambda x: x * x + x + 1, "x^2 + x + 1"),
    FunctionSpec("exp(x)", lambda x: x.exp(), "e^x"),
)


def parse_points(text: str) -> list[tuple[Decimal, Decimal]]:
    if not text.strip():
        raise InterpolationError(
            "Ввод пустой. Укажите точки в формате `x y`, по одной или несколько пар в строке."
        )

    points: list[tuple[Decimal, Decimal]] = []
    seen_points: set[tuple[Decimal, Decimal]] = set()
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        parts = [part for part in re.split(r"[;\s]+", line) if part]
        if len(parts) % 2 != 0:
            raise InterpolationError(
                f"Строка {line_number}: ожидается чётное количество чисел, чтобы разбить их на пары `x y`."
            )

        for index in range(0, len(parts), 2):
            point = (
                _parse_number(parts[index], line_number, "x"),
                _parse_number(parts[index + 1], line_number, "y"),
            )
            if point in seen_points:
                continue
            seen_points.add(point)
            points.append(point)

    return normalize_points(points)


def normalize_points(points: Sequence[tuple[Decimal, Decimal]]) -> list[tuple[Decimal, Decimal]]:
    if len(points) < 2:
        raise InterpolationError(
            f"Недостаточно точек: получено {len(points)}, а требуется минимум 2."
        )
    if len(points) > 20:
        raise InterpolationError(
            f"Слишком много точек: получено {len(points)}, а рекомендуется не более 20."
        )

    sorted_points = sorted(points, key=lambda point: point[0])
    seen_x: set[Decimal] = set()
    for x_value, _ in sorted_points:
        if x_value in seen_x:
            raise InterpolationError(
                f"Узел x = {format_number(x_value)} повторяется. Для интерполяции значения x должны быть различны."
            )
        seen_x.add(x_value)
    return sorted_points


def _parse_number(token: str, line_number: int, coordinate_name: str) -> Decimal:
    normalized = token.replace(",", ".")
    try:
        value = Decimal(normalized)
    except InvalidOperation as exc:
        raise InterpolationError(
            f"Строка {line_number}: значение `{token}` в колонке `{coordinate_name}` не похоже на число."
        ) from exc
    if not value.is_finite():
        raise InterpolationError(
            f"Строка {line_number}: значение `{token}` в колонке `{coordinate_name}` должно быть конечным числом."
        )
    return value


def parse_decimal(text: str, field_name: str) -> Decimal:
    if not text.strip():
        raise InterpolationError(f"Поле `{field_name}` не заполнено.")
    try:
        value = Decimal(text.strip().replace(",", "."))
    except InvalidOperation as exc:
        raise InterpolationError(f"Поле `{field_name}` должно содержать число.") from exc
    if not value.is_finite():
        raise InterpolationError(f"Поле `{field_name}` должно содержать конечное число.")
    return value


def generate_function_points(
    function_name: str,
    start: Decimal,
    end: Decimal,
    count: int,
) -> list[tuple[Decimal, Decimal]]:
    if count < 2:
        raise InterpolationError("Количество точек на интервале должно быть не меньше 2.")
    if count > 20:
        raise InterpolationError("Количество точек на интервале должно быть не больше 20.")
    if start == end:
        raise InterpolationError("Границы интервала не должны совпадать.")

    function = get_function(function_name)
    precision = max(80, _required_precision([start, end]) + 20)
    with localcontext() as context:
        context.prec = precision
        h = (end - start) / Decimal(count - 1)
        points: list[tuple[Decimal, Decimal]] = []
        for index in range(count):
            x_value = start + Decimal(index) * h
            try:
                y_value = +function.evaluator(x_value)
            except DecimalException as exc:
                raise InterpolationError(
                    f"Не удалось вычислить функцию `{function_name}` в точке x = {format_number(x_value)}."
                ) from exc
            points.append((x_value, y_value))
    return normalize_points(points)


def get_function(function_name: str) -> FunctionSpec:
    for function in FUNCTIONS:
        if function.name == function_name:
            return function
    raise InterpolationError(f"Неизвестная функция: {function_name}.")


def analyze_interpolation(
    points: Sequence[tuple[Decimal, Decimal]],
    x_value: Decimal,
    source_function_name: str | None = None,
) -> InterpolationAnalysis:
    normalized = normalize_points(points)
    precision = max(60, _required_precision([coord for point in normalized for coord in point] + [x_value]))

    with localcontext() as context:
        context.prec = precision
        differences = build_finite_differences(normalized)
        results: list[MethodResult] = []
        issues: list[str] = []
        is_extrapolation = x_value < normalized[0][0] or x_value > normalized[-1][0]

        results.append(
            MethodResult(
                name="Многочлен Лагранжа",
                value=lagrange_value(normalized, x_value),
                formula="L_n(x) = Σ y_i l_i(x)",
            )
        )

        try:
            _ensure_equally_spaced(normalized)
            results.append(newton_forward_value(normalized, differences, x_value))
            results.append(newton_backward_value(normalized, differences, x_value))
            for builder in (gauss_first_value, gauss_second_value):
                try:
                    results.append(builder(normalized, differences, x_value))
                except InterpolationError as exc:
                    issues.append(str(exc))
        except InterpolationError as exc:
            issues.append(str(exc))

        exact_value = None
        if source_function_name:
            function = get_function(source_function_name)
            try:
                exact_value = +function.evaluator(x_value)
            except DecimalException as exc:
                raise InterpolationError(
                    f"Не удалось вычислить точное значение функции `{source_function_name}` в точке x = {format_number(x_value)}."
                ) from exc

        return InterpolationAnalysis(
            points=normalized,
            x_value=x_value,
            finite_differences=differences,
            results=results,
            issues=issues,
            source_function_name=source_function_name,
            exact_value=exact_value,
            is_extrapolation=is_extrapolation,
        )


def build_finite_differences(
    points: Sequence[tuple[Decimal, Decimal]]
) -> list[list[Decimal]]:
    differences = [[y_value for _, y_value in points]]
    while len(differences[-1]) > 1:
        previous = differences[-1]
        differences.append(
            [previous[index + 1] - previous[index] for index in range(len(previous) - 1)]
        )
    return differences


def lagrange_value(points: Sequence[tuple[Decimal, Decimal]], x_value: Decimal) -> Decimal:
    result = ZERO
    for i, (x_i, y_i) in enumerate(points):
        basis = ONE
        for j, (x_j, _) in enumerate(points):
            if i == j:
                continue
            basis *= (x_value - x_j) / (x_i - x_j)
        result += y_i * basis
    return result


def newton_forward_value(
    points: Sequence[tuple[Decimal, Decimal]],
    differences: Sequence[Sequence[Decimal]],
    x_value: Decimal,
) -> MethodResult:
    h = points[1][0] - points[0][0]
    t = (x_value - points[0][0]) / h
    result = differences[0][0]
    coefficient = ONE
    for order in range(1, len(points)):
        coefficient *= (t - Decimal(order - 1)) / Decimal(order)
        result += coefficient * differences[order][0]
    return MethodResult(
        name="Ньютон, первая формула",
        value=+result,
        formula="N_n(x) = y_0 + tΔy_0 + t(t-1)/2! Δ²y_0 + ...",
    )


def newton_backward_value(
    points: Sequence[tuple[Decimal, Decimal]],
    differences: Sequence[Sequence[Decimal]],
    x_value: Decimal,
) -> MethodResult:
    h = points[1][0] - points[0][0]
    n = len(points) - 1
    t = (x_value - points[-1][0]) / h
    result = differences[0][n]
    coefficient = ONE
    for order in range(1, len(points)):
        coefficient *= (t + Decimal(order - 1)) / Decimal(order)
        result += coefficient * differences[order][n - order]
    return MethodResult(
        name="Ньютон, вторая формула",
        value=+result,
        formula="N_n(x) = y_n + tΔy_(n-1) + t(t+1)/2! Δ²y_(n-2) + ...",
    )


def gauss_value(
    points: Sequence[tuple[Decimal, Decimal]],
    differences: Sequence[Sequence[Decimal]],
    x_value: Decimal,
) -> MethodResult:
    table_mid = (points[0][0] + points[-1][0]) / TWO
    if x_value >= table_mid:
        return gauss_first_value(points, differences, x_value)
    return gauss_second_value(points, differences, x_value)


def gauss_first_value(
    points: Sequence[tuple[Decimal, Decimal]],
    differences: Sequence[Sequence[Decimal]],
    x_value: Decimal,
) -> MethodResult:
    h = points[1][0] - points[0][0]
    n = len(points) - 1
    m = n // 2
    t = (x_value - points[m][0]) / h
    result = differences[0][m]
    for order in range(1, len(points)):
        row_index = m - order // 2
        _check_difference_index(differences, order, row_index, "первой формулы Гаусса")
        result += _gauss_first_coefficient(t, order) * differences[order][row_index]
    return MethodResult(
        name="Гаусс, первая формула",
        value=+result,
        formula="P_n(x) = y_0 + tΔy_0 + t(t-1)/2! Δ²y_-1 + ...",
    )


def gauss_second_value(
    points: Sequence[tuple[Decimal, Decimal]],
    differences: Sequence[Sequence[Decimal]],
    x_value: Decimal,
) -> MethodResult:
    h = points[1][0] - points[0][0]
    n = len(points) - 1
    m = (n + 1) // 2
    t = (x_value - points[m][0]) / h
    result = differences[0][m]
    for order in range(1, len(points)):
        row_index = m - (order + 1) // 2
        _check_difference_index(differences, order, row_index, "второй формулы Гаусса")
        result += _gauss_second_coefficient(t, order) * differences[order][row_index]
    return MethodResult(
        name="Гаусс, вторая формула",
        value=+result,
        formula="P_n(x) = y_0 + tΔy_-1 + t(t+1)/2! Δ²y_-1 + ...",
    )


def _gauss_first_coefficient(t: Decimal, order: int) -> Decimal:
    factors = _gauss_first_offsets(order)
    product = ONE
    for offset in factors:
        product *= t - Decimal(offset)
    return product / _factorial(order)


def _gauss_second_coefficient(t: Decimal, order: int) -> Decimal:
    factors = _gauss_second_offsets(order)
    product = ONE
    for offset in factors:
        product *= t - Decimal(offset)
    return product / _factorial(order)


def _gauss_first_offsets(order: int) -> range:
    if order % 2 == 0:
        s = order // 2
        return range(-(s - 1), s + 1)
    s = order // 2
    return range(-s, s + 1)


def _gauss_second_offsets(order: int) -> range:
    if order % 2 == 0:
        s = order // 2
        return range(-s, s)
    s = order // 2
    return range(-s, s + 1)


def _check_difference_index(
    differences: Sequence[Sequence[Decimal]],
    order: int,
    index: int,
    method_name: str,
) -> None:
    if index < 0 or index >= len(differences[order]):
        raise InterpolationError(
            f"Недостаточно узлов вокруг центрального узла для {method_name}."
        )


def _ensure_equally_spaced(points: Sequence[tuple[Decimal, Decimal]]) -> None:
    if len(points) < 2:
        raise InterpolationError("Для конечных разностей нужно минимум 2 узла.")

    h = points[1][0] - points[0][0]
    if h == ZERO:
        raise InterpolationError("Шаг интерполяции не может быть равен нулю.")

    tolerance = max(ONE, abs(h)) * EPS
    for index in range(2, len(points)):
        current_h = points[index][0] - points[index - 1][0]
        if abs(current_h - h) > tolerance:
            raise InterpolationError(
                "Узлы не являются равноотстоящими. "
                "Для Ньютона с конечными разностями и Гаусса нужен постоянный шаг h; "
                "для этого набора доступен только метод Лагранжа."
            )


def _factorial(value: int) -> Decimal:
    result = 1
    for factor in range(2, value + 1):
        result *= factor
    return Decimal(result)


def _required_precision(values: Sequence[Decimal]) -> int:
    finite = [value for value in values if value.is_finite()]
    significant = max((len(value.as_tuple().digits) for value in finite), default=30)
    fractional = max((max(0, -value.as_tuple().exponent) for value in finite), default=10)
    return significant + fractional + 30


def format_number(value: Decimal | float | int) -> str:
    decimal_value = _to_decimal(value)
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
        return f"{sign}{integer_part}.{fractional_part}"

    shift = len(fractional_part) - 5
    mantissa = f"{integer_part}.{fractional_part[:5]}"
    return f"{sign}{mantissa} * 10^(-{shift})"


def _to_decimal(value: Decimal | float | int) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return ZERO


def format_difference_table(
    points: Sequence[tuple[Decimal, Decimal]],
    differences: Sequence[Sequence[Decimal]],
) -> str:
    headers = ["i", "x_i", "y_i"] + [f"Δ^{order} y_i" for order in range(1, len(points))]
    rows: list[list[str]] = []
    for index, (x_value, _) in enumerate(points):
        row = [str(index), format_number(x_value), format_number(differences[0][index])]
        for order in range(1, len(points)):
            if index < len(differences[order]):
                row.append(format_number(differences[order][index]))
            else:
                row.append("")
        rows.append(row)

    widths = [
        max(len(headers[col]), *(len(row[col]) for row in rows))
        for col in range(len(headers))
    ]
    lines = [
        " | ".join(headers[col].rjust(widths[col]) for col in range(len(headers))),
        "-+-".join("-" * width for width in widths),
    ]
    for row in rows:
        lines.append(" | ".join(row[col].rjust(widths[col]) for col in range(len(row))))
    return "\n".join(lines)


def format_report(analysis: InterpolationAnalysis) -> str:
    lines = [
        "# Результаты интерполяции",
        "",
        f"**Точка вычисления:** `x = {format_number(analysis.x_value)}`",
        f"**Количество узлов:** {len(analysis.points)}",
    ]
    if analysis.is_extrapolation:
        lines.append(
            "> **Предупреждение:** точка находится вне интервала узлов, это экстраполяция."
        )
    if analysis.source_function_name:
        lines.append(f"**Исходная функция:** `{analysis.source_function_name}`")
    if analysis.exact_value is not None:
        lines.append(f"**Точное значение функции:** `{format_number(analysis.exact_value)}`")

    lines.extend(
        [
            "",
            "## Таблица конечных разностей",
            "",
            "    " + format_difference_table(
                analysis.points, analysis.finite_differences
            ).replace("\n", "\n    "),
            "",
        ]
    )

    lines.append("## Сравнение методов")
    for result in analysis.results:
        error_text = ""
        if analysis.exact_value is not None:
            error_text = f", |ошибка| = {format_number(abs(result.value - analysis.exact_value))}"
        lines.append(f"- **{result.name}:** `{format_number(result.value)}`{error_text}")
        lines.append(f"  `{result.formula}`")
    if analysis.issues:
        lines.append("")
        lines.append("## Ограничения")
        for issue in analysis.issues:
            lines.append(f"- {issue}")

    lines.append("")
    lines.append("## Анализ результата")
    if analysis.exact_value is not None:
        best = min(analysis.results, key=lambda result: abs(result.value - analysis.exact_value))
        lines.append(
            f"На этом наборе минимальную ошибку относительно исходной функции дал метод: **{best.name}**."
        )
    elif len(analysis.results) > 1:
        values = [result.value for result in analysis.results]
        spread = max(values) - min(values)
        lines.append(
            f"Разброс между построенными методами: {format_number(spread)}. "
            "Чем меньше разброс, тем согласованнее интерполяционные формулы на выбранных узлах."
        )
    else:
        lines.append(
            "Для неравномерной сетки рассчитан только универсальный многочлен Лагранжа."
        )
    return "\n".join(lines)
