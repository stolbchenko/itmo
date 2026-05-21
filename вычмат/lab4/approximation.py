from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
import re
from typing import Callable, Sequence


ZERO = Decimal("0")
ONE = Decimal("1")
TWO = Decimal("2")


class ApproximationError(ValueError):
    pass


@dataclass
class ApproximationResult:
    name: str
    formula: str
    coefficients: dict[str, Decimal]
    predictions: list[Decimal]
    residuals: list[Decimal]
    sse: Decimal
    sigma: Decimal
    r_squared: Decimal
    r_squared_message: str
    pearson: Decimal | None = None


@dataclass
class ApproximationIssue:
    name: str
    message: str


@dataclass
class AnalysisResult:
    results: list[ApproximationResult]
    issues: list[ApproximationIssue]


def parse_points(text: str) -> list[tuple[Decimal, Decimal]]:
    if not text.strip():
        raise ApproximationError(
            "Ввод пустой. Укажите от 8 до 12 точек, по одной в строке, например: `1,25 3.5`."
        )
    points: list[tuple[Decimal, Decimal]] = []
    seen_points: set[tuple[Decimal, Decimal]] = set()
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        parts = [part for part in re.split(r"[;\s]+", line) if part]
        if len(parts) % 2 != 0:
            raise ApproximationError(
                f"Строка {line_number}: ожидается чётное количество чисел, чтобы разбить их на пары `x y`. "
                f"Пример корректного ввода: `1,25 3.5` или `1 2 3 4`."
            )

        for index in range(0, len(parts), 2):
            x_value = _parse_number(parts[index], line_number, "x")
            y_value = _parse_number(parts[index + 1], line_number, "y")
            point = (x_value, y_value)
            if point in seen_points:
                continue
            seen_points.add(point)
            points.append(point)

    if not points:
        raise ApproximationError(
            "Не найдено ни одной точки. Проверьте, что каждая непустая строка содержит пару чисел `x y`."
        )
    if len(points) < 8:
        raise ApproximationError(
            f"Недостаточно уникальных точек: получено {len(points)}, а требуется минимум 8."
        )
    if len(points) > 12:
        raise ApproximationError(
            f"Слишком много уникальных точек: получено {len(points)}, а допускается максимум 12."
        )
    return points


def _parse_number(token: str, line_number: int, coordinate_name: str) -> Decimal:
    normalized = token.replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise ApproximationError(
            f"Строка {line_number}: значение `{token}` в колонке `{coordinate_name}` не похоже на число. "
            f"Используйте запись вида `-2`, `3.14` или `3,14`."
        ) from exc


def analyze_points(points: Sequence[tuple[Decimal, Decimal]]) -> AnalysisResult:
    x_values = [point[0] for point in points]
    y_values = [point[1] for point in points]
    precision = max(50, _required_precision(x_values + y_values))

    with localcontext() as context:
        context.prec = precision
        results: list[ApproximationResult] = []
        issues: list[ApproximationIssue] = []
        builders = [
            ("Линейная", lambda: fit_linear(x_values, y_values)),
            ("Полином 2-й степени", lambda: fit_polynomial_2(x_values, y_values)),
            ("Полином 3-й степени", lambda: fit_polynomial_3(x_values, y_values)),
            ("Экспоненциальная", lambda: fit_exponential(x_values, y_values)),
            ("Логарифмическая", lambda: fit_logarithmic(x_values, y_values)),
            ("Степенная", lambda: fit_power(x_values, y_values)),
        ]

        for model_name, builder in builders:
            try:
                results.append(builder())
            except ApproximationError as exc:
                issues.append(ApproximationIssue(name=model_name, message=str(exc)))

        if not results:
            issue_text = "; ".join(f"{issue.name}: {issue.message}" for issue in issues)
            raise ApproximationError(
                "Ни одна из аппроксимирующих функций не может быть построена для этого набора данных. "
                + issue_text
            )

        return AnalysisResult(results=results, issues=issues)


def _required_precision(values: Sequence[Decimal]) -> int:
    significant = max(len(value.as_tuple().digits) for value in values if value.is_finite())
    fractional = max(max(0, -value.as_tuple().exponent) for value in values if value.is_finite())
    return significant + fractional + 25


def best_result(results: Sequence[ApproximationResult]) -> ApproximationResult:
    return min(results, key=lambda result: result.sigma)


def _fit_with_predictions(
    name: str,
    formula: str,
    coefficients: dict[str, Decimal],
    x_values: Sequence[Decimal],
    y_values: Sequence[Decimal],
    predictor: Callable[[Decimal], Decimal],
    pearson: Decimal | None = None,
) -> ApproximationResult:
    predictions = [predictor(x_value) for x_value in x_values]
    residuals = [predictions[index] - y_values[index] for index in range(len(y_values))]
    sse = sum(value * value for value in residuals)
    sigma = (sse / Decimal(len(x_values))).sqrt()
    mean_y = sum(y_values) / Decimal(len(y_values))
    total = sum((y_value - mean_y) ** 2 for y_value in y_values)
    if total == ZERO:
        r_squared = ONE if sse == ZERO else ZERO
    else:
        r_squared = ONE - sse / total
    return ApproximationResult(
        name=name,
        formula=formula,
        coefficients=coefficients,
        predictions=predictions,
        residuals=residuals,
        sse=sse,
        sigma=sigma,
        r_squared=r_squared,
        r_squared_message=interpret_r_squared(r_squared),
        pearson=pearson,
    )


def fit_linear(x_values: Sequence[Decimal], y_values: Sequence[Decimal]) -> ApproximationResult:
    intercept, slope = solve_normal_equations(
        basis_count=2,
        x_values=x_values,
        y_values=y_values,
        basis_functions=[lambda _: ONE, lambda x: x],
    )
    pearson = pearson_correlation(x_values, y_values)
    return _fit_with_predictions(
        name="Линейная",
        formula=f"y = {format_number(intercept)} {'+' if slope >= ZERO else '-'} {format_number(abs(slope))}x",
        coefficients={"a0": intercept, "a1": slope},
        x_values=x_values,
        y_values=y_values,
        predictor=lambda x: intercept + slope * x,
        pearson=pearson,
    )


def fit_polynomial_2(
    x_values: Sequence[Decimal], y_values: Sequence[Decimal]
) -> ApproximationResult:
    basis_functions = [
        lambda _value: ONE,
        lambda value: value,
        lambda value: value ** 2,
    ]
    coefficients = solve_normal_equations(
        basis_count=3,
        x_values=x_values,
        y_values=y_values,
        basis_functions=basis_functions,
    )
    a0, a1, a2 = coefficients
    return _fit_with_predictions(
        name="Полином 2-й степени",
        formula=(
            f"y = {format_number(a0)} "
            f"{'+' if a1 >= ZERO else '-'} {format_number(abs(a1))}x "
            f"{'+' if a2 >= ZERO else '-'} {format_number(abs(a2))}x^2"
        ),
        coefficients={"a0": a0, "a1": a1, "a2": a2},
        x_values=x_values,
        y_values=y_values,
        predictor=lambda x: a0 + a1 * x + a2 * (x ** 2),
    )


def fit_polynomial_3(
    x_values: Sequence[Decimal], y_values: Sequence[Decimal]
) -> ApproximationResult:
    basis_functions = [
        lambda _value: ONE,
        lambda value: value,
        lambda value: value ** 2,
        lambda value: value ** 3,
    ]
    coefficients = solve_normal_equations(
        basis_count=4,
        x_values=x_values,
        y_values=y_values,
        basis_functions=basis_functions,
    )
    a0, a1, a2, a3 = coefficients
    return _fit_with_predictions(
        name="Полином 3-й степени",
        formula=(
            f"y = {format_number(a0)} "
            f"{'+' if a1 >= ZERO else '-'} {format_number(abs(a1))}x "
            f"{'+' if a2 >= ZERO else '-'} {format_number(abs(a2))}x^2 "
            f"{'+' if a3 >= ZERO else '-'} {format_number(abs(a3))}x^3"
        ),
        coefficients={"a0": a0, "a1": a1, "a2": a2, "a3": a3},
        x_values=x_values,
        y_values=y_values,
        predictor=lambda x: a0 + a1 * x + a2 * (x ** 2) + a3 * (x ** 3),
    )


def fit_exponential(x_values: Sequence[Decimal], y_values: Sequence[Decimal]) -> ApproximationResult:
    if any(y_value <= ZERO for y_value in y_values):
        raise ApproximationError(
            "экспоненциальная модель неприменима: для логарифмирования требуется y > 0 во всех точках."
        )
    log_y = [y_value.ln() for y_value in y_values]
    intercept, slope = solve_normal_equations(
        basis_count=2,
        x_values=x_values,
        y_values=log_y,
        basis_functions=[lambda _: ONE, lambda x: x],
    )
    a_value = intercept.exp()
    b_value = slope
    return _fit_with_predictions(
        name="Экспоненциальная",
        formula=f"y = {format_number(a_value)}e^({format_number(b_value)}x)",
        coefficients={"a": a_value, "b": b_value},
        x_values=x_values,
        y_values=y_values,
        predictor=lambda x: a_value * (b_value * x).exp(),
    )


def fit_logarithmic(x_values: Sequence[Decimal], y_values: Sequence[Decimal]) -> ApproximationResult:
    if any(x_value <= ZERO for x_value in x_values):
        raise ApproximationError(
            "логарифмическая модель неприменима: требуется x > 0 во всех точках."
        )
    intercept, slope = solve_normal_equations(
        basis_count=2,
        x_values=[x_value.ln() for x_value in x_values],
        y_values=y_values,
        basis_functions=[lambda _: ONE, lambda x: x],
    )
    b_value = intercept
    a_value = slope
    return _fit_with_predictions(
        name="Логарифмическая",
        formula=f"y = {format_number(a_value)}ln(x) {'+' if b_value >= ZERO else '-'} {format_number(abs(b_value))}",
        coefficients={"a": a_value, "b": b_value},
        x_values=x_values,
        y_values=y_values,
        predictor=lambda x: a_value * x.ln() + b_value,
    )


def fit_power(x_values: Sequence[Decimal], y_values: Sequence[Decimal]) -> ApproximationResult:
    if any(x_value <= ZERO for x_value in x_values):
        raise ApproximationError(
            "степенная модель неприменима: требуется x > 0 во всех точках."
        )
    if any(y_value <= ZERO for y_value in y_values):
        raise ApproximationError(
            "степенная модель неприменима: требуется y > 0 во всех точках."
        )
    intercept, slope = solve_normal_equations(
        basis_count=2,
        x_values=[x_value.ln() for x_value in x_values],
        y_values=[y_value.ln() for y_value in y_values],
        basis_functions=[lambda _: ONE, lambda x: x],
    )
    a_value = intercept.exp()
    b_value = slope
    return _fit_with_predictions(
        name="Степенная",
        formula=f"y = {format_number(a_value)}x^{format_number(b_value)}",
        coefficients={"a": a_value, "b": b_value},
        x_values=x_values,
        y_values=y_values,
        predictor=lambda x: a_value * (b_value * x.ln()).exp(),
    )


def solve_normal_equations(
    basis_count: int,
    x_values: Sequence[Decimal],
    y_values: Sequence[Decimal],
    basis_functions: Sequence[Callable[[Decimal], Decimal]],
) -> list[Decimal]:
    matrix = [[ZERO for _ in range(basis_count)] for _ in range(basis_count)]
    vector = [ZERO for _ in range(basis_count)]

    for row in range(basis_count):
        for column in range(basis_count):
            matrix[row][column] = sum(
                basis_functions[row](x_value) * basis_functions[column](x_value)
                for x_value in x_values
            )
        vector[row] = sum(
            basis_functions[row](x_values[index]) * y_values[index]
            for index in range(len(x_values))
        )

    return gaussian_elimination(matrix, vector)


def gaussian_elimination(matrix: list[list[Decimal]], vector: list[Decimal]) -> list[Decimal]:
    size = len(vector)
    for pivot in range(size):
        pivot_row = max(range(pivot, size), key=lambda index: abs(matrix[index][pivot]))
        if abs(matrix[pivot_row][pivot]) < Decimal("1e-40"):
            raise ApproximationError(
                "Система нормальных уравнений вырождена. Проверьте, что точки не образуют вырожденный набор."
            )
        if pivot_row != pivot:
            matrix[pivot], matrix[pivot_row] = matrix[pivot_row], matrix[pivot]
            vector[pivot], vector[pivot_row] = vector[pivot_row], vector[pivot]

        pivot_value = matrix[pivot][pivot]
        for column in range(pivot, size):
            matrix[pivot][column] /= pivot_value
        vector[pivot] /= pivot_value

        for row in range(size):
            if row == pivot:
                continue
            factor = matrix[row][pivot]
            for column in range(pivot, size):
                matrix[row][column] -= factor * matrix[pivot][column]
            vector[row] -= factor * vector[pivot]

    return vector


def pearson_correlation(x_values: Sequence[Decimal], y_values: Sequence[Decimal]) -> Decimal:
    count = Decimal(len(x_values))
    mean_x = sum(x_values) / count
    mean_y = sum(y_values) / count
    numerator = sum(
        (x_values[index] - mean_x) * (y_values[index] - mean_y)
        for index in range(len(x_values))
    )
    x_dispersion = sum((value - mean_x) ** 2 for value in x_values)
    y_dispersion = sum((value - mean_y) ** 2 for value in y_values)
    denominator = (x_dispersion * y_dispersion).sqrt()
    if denominator == ZERO:
        return ZERO
    return numerator / denominator


def interpret_r_squared(r_squared: Decimal) -> str:
    if r_squared >= Decimal("0.95"):
        return "Высокая точность аппроксимации (модель хорошо описывает явление)"
    if r_squared >= Decimal("0.75"):
        return "Удовлетворительная аппроксимация (модель в целом адекватно описывает явление)"
    if r_squared >= Decimal("0.5"):
        return "Слабая аппроксимация (модель слабо описывает явление)"
    return "Точность аппроксимации недостаточна, модель требует изменения"


def format_number(value: Decimal | float | int) -> str:
    decimal_value = _to_decimal(value)
    if not decimal_value.is_finite():
        return str(value)

    plain = format(decimal_value, "f")
    sign = ""
    if plain.startswith("-"):
        sign = "-"
        plain = plain[1:]

    if "." not in plain:
        return sign + plain

    integer_part, fractional_part = plain.split(".", 1)
    if len(fractional_part) <= 5:
        return sign + plain

    shift = len(fractional_part) - 5
    mantissa = f"{integer_part}.{fractional_part[:5]}"
    return f"{sign}{mantissa} × 10^(-{shift})"


def _to_decimal(value: Decimal | float | int) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return ZERO


def format_result_block(
    x_values: Sequence[Decimal],
    y_values: Sequence[Decimal],
    result: ApproximationResult,
) -> str:
    coeff_str = ", ".join(
        f"{name} = {format_number(value)}" for name, value in result.coefficients.items()
    )
    lines = [
        f"## {result.name}",
        "",
        f"**Формула:** `{result.formula}`",
        f"**Коэффициенты:** {coeff_str}",
        f"**S =** {format_number(result.sse)}  ·  **δ =** {format_number(result.sigma)}  ·  **R² =** {format_number(result.r_squared)}",
        f"**Оценка R²:** {result.r_squared_message}",
    ]
    if result.pearson is not None:
        lines.append(f"**Коэффициент Пирсона:** {format_number(result.pearson)}")

    w = 10
    lines.append("")
    lines.append(f"    {'i':>3} | {'xi':>{w}} | {'yi':>{w}} | {'φ(xi)':>{w}} | {'εi':>{w}}")
    lines.append(f"    {'---':>3}-+-{'-' * w}-+-{'-' * w}-+-{'-' * w}-+-{'-' * w}")
    for index, (x_value, y_value, approximation, residual) in enumerate(
        zip(x_values, y_values, result.predictions, result.residuals),
        start=1,
    ):
        lines.append(
            f"    {index:>3} | {format_number(x_value):>{w}} | {format_number(y_value):>{w}} | "
            f"{format_number(approximation):>{w}} | {format_number(residual):>{w}}"
        )
    return "\n".join(lines)


def format_full_report(points: Sequence[tuple[Decimal, Decimal]], analysis: AnalysisResult) -> str:
    x_values = [point[0] for point in points]
    y_values = [point[1] for point in points]
    best = best_result(analysis.results)

    lines = [
        "# Результаты аппроксимации МНК",
        "",
        f"**Количество точек:** {len(points)}",
        f"**Наилучшая функция:** {best.name}",
        f"**Формула:** `{best.formula}`",
        "",
    ]

    if analysis.issues:
        lines.append("**Модели, которые не удалось построить:**")
        for issue in analysis.issues:
            lines.append(f"> **{issue.name}:** {issue.message}")
        lines.append("")

    lines.append("---")
    lines.append("")

    for index, result in enumerate(analysis.results):
        lines.append(format_result_block(x_values, y_values, result))
        lines.append("")
        if index < len(analysis.results) - 1:
            lines.append("---")
            lines.append("")

    return "\n".join(lines).strip()
