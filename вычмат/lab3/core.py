from decimal import Decimal


DISPLAY_FRACTION_DIGITS = 5
START_PARTITIONS = 4
MAX_ITERATIONS = 30
BASE_PRECISION = 80


def to_decimal_string(value: Decimal) -> str:
    sign = "-" if value.is_signed() and value != 0 else ""
    value = abs(value)

    if value == 0:
        return "0"

    decimal_tuple = value.normalize().as_tuple()
    digits = "".join(str(digit) for digit in decimal_tuple.digits) or "0"
    exponent = decimal_tuple.exponent

    if exponent >= 0:
        integer_part = digits + ("0" * exponent)
        return f"{sign}{integer_part}"

    split_index = len(digits) + exponent
    if split_index > 0:
        integer_part = digits[:split_index]
        fractional_part = digits[split_index:]
    else:
        integer_part = "0"
        fractional_part = ("0" * (-split_index)) + digits

    fractional_part = fractional_part.rstrip("0")
    if not fractional_part:
        return f"{sign}{integer_part}"

    return f"{sign}{integer_part}.{fractional_part}"


def format_decimal_for_output(value: Decimal) -> str:
    plain = to_decimal_string(value)
    sign = ""

    if plain.startswith("-"):
        sign = "-"
        plain = plain[1:]

    if "." not in plain:
        return f"{sign}{plain}"

    integer_part, fractional_part = plain.split(".", 1)
    if len(fractional_part) <= DISPLAY_FRACTION_DIGITS:
        return f"{sign}{integer_part}.{fractional_part}"

    visible = fractional_part[:DISPLAY_FRACTION_DIGITS]
    hidden = len(fractional_part) - DISPLAY_FRACTION_DIGITS
    return f"{sign}{integer_part}.{visible} * 10^(-{hidden})"


def compute_dynamic_precision(epsilon: Decimal, left_border: Decimal, right_border: Decimal) -> int:
    return max(
        BASE_PRECISION,
        len(to_decimal_string(epsilon).replace("-", "").replace(".", "")) + 30,
        len(to_decimal_string(left_border).replace("-", "").replace(".", "")) + 30,
        len(to_decimal_string(right_border).replace("-", "").replace(".", "")) + 30,
    )


def function_left_original(x: Decimal) -> Decimal:
    return x.exp() / x.sqrt()


def function_right_original(x: Decimal) -> Decimal:
    return Decimal("1") / (Decimal("1") - x)


def function_proper_quadratic(x: Decimal) -> Decimal:
    return x * x


def function_proper_exp(x: Decimal) -> Decimal:
    return x.exp()


def function_principal_value_original(x: Decimal) -> Decimal:
    return Decimal("1") / x


def function_left_transformed(t: Decimal) -> Decimal:
    return Decimal("2") * (t * t).exp()


def build_functions():
    return [
        {
            "name": "x^2",
            "description": "Собственный интеграл на любом отрезке [a, b].",
            "formula": function_proper_quadratic,
            "type": "proper",
            "converges": True,
            "reason": "Функция непрерывна на [a, b], интеграл существует.",
            "substitution": "Преобразование не требуется.",
        },
        {
            "name": "e^x",
            "description": "Собственный интеграл на любом отрезке [a, b].",
            "formula": function_proper_exp,
            "type": "proper",
            "converges": True,
            "reason": "Функция непрерывна на [a, b], интеграл существует.",
            "substitution": "Преобразование не требуется.",
        },
        {
            "name": "e^x / sqrt(x)",
            "description": "Несобственный интеграл 2 рода: разрыв в левой границе a = 0. Используйте [0, b], b > 0.",
            "formula": function_left_original,
            "type": "improper_2nd",
            "kind": "left",
            "singularity": Decimal("0"),
            "converges": True,
            "reason": "Интеграл сходится, так как около x = 0 функция ведет себя как 1 / x^p при p = 1/2 < 1.",
            "substitution": "Замена x = t^2 сводит интеграл к собственному: ∫(e^x / sqrt(x))dx = ∫2e^(t^2)dt.",
        },
        {
            "name": "1 / (1 - x)",
            "description": "Несобственный интеграл 2 рода: разрыв в правой границе b = 1. Используйте [a, 1], a < 1.",
            "formula": function_right_original,
            "type": "improper_2nd",
            "kind": "right",
            "singularity": Decimal("1"),
            "converges": False,
            "reason": "Интеграл расходится, так как функция ведет себя как 1 / (1 - x)^p при p = 1 >= 1.",
            "substitution": "Численное вычисление не выполняется, потому что интеграл расходится.",
        },
        {
            "name": "1 / x",
            "description": "Разрыв 2 рода внутри интервала в точке x = 0. Считается как главное значение с симметричным сокращением.",
            "formula": function_principal_value_original,
            "type": "principal_value",
            "kind": "inside",
            "singularity": Decimal("0"),
            "converges": True,
            "reason": "Обычный несобственный интеграл расходится, но главное значение существует за счет взаимного сокращения симметричных частей.",
            "substitution": "Симметричный участок [-d, d] вокруг 0 зануляется, интегрируются только оставшиеся несокращаемые части.",
        },
    ]


def validate_interval(function_data, left: Decimal, right: Decimal) -> None:
    if left >= right:
        raise ValueError("Нижний предел должен быть меньше верхнего.")

    if function_data["type"] == "proper":
        return

    singularity = function_data["singularity"]
    kind = function_data["kind"]
    if kind == "left" and left != singularity:
        raise ValueError("Для выбранной функции левая граница должна совпадать с точкой разрыва: a = 0.")

    if kind == "right" and right != singularity:
        raise ValueError("Для выбранной функции правая граница должна совпадать с точкой разрыва: b = 1.")

    if function_data["type"] == "principal_value" and not (left < singularity < right):
        raise ValueError("Для функции 1 / x точка разрыва x = 0 должна находиться внутри интервала интегрирования.")


def integrate_left_rectangles(function, left: Decimal, right: Decimal, partitions: int) -> Decimal:
    step = (right - left) / Decimal(partitions)
    total = Decimal("0")
    for index in range(partitions):
        x_value = left + Decimal(index) * step
        total += function(x_value)
    return total * step


def integrate_right_rectangles(function, left: Decimal, right: Decimal, partitions: int) -> Decimal:
    step = (right - left) / Decimal(partitions)
    total = Decimal("0")
    for index in range(1, partitions + 1):
        x_value = left + Decimal(index) * step
        total += function(x_value)
    return total * step


def integrate_middle_rectangles(function, left: Decimal, right: Decimal, partitions: int) -> Decimal:
    step = (right - left) / Decimal(partitions)
    total = Decimal("0")
    for index in range(partitions):
        x_value = left + (Decimal(index) + Decimal("0.5")) * step
        total += function(x_value)
    return total * step


def integrate_trapezoid(function, left: Decimal, right: Decimal, partitions: int) -> Decimal:
    step = (right - left) / Decimal(partitions)
    total = (function(left) + function(right)) / Decimal("2")
    for index in range(1, partitions):
        x_value = left + Decimal(index) * step
        total += function(x_value)
    return total * step


def integrate_simpson(function, left: Decimal, right: Decimal, partitions: int) -> Decimal:
    if partitions % 2 != 0:
        raise ValueError("Для метода Симпсона число разбиений должно быть четным.")

    step = (right - left) / Decimal(partitions)
    total = function(left) + function(right)
    odd_sum = Decimal("0")
    even_sum = Decimal("0")

    for index in range(1, partitions):
        x_value = left + Decimal(index) * step
        if index % 2 == 0:
            even_sum += function(x_value)
        else:
            odd_sum += function(x_value)

    return (total + Decimal("4") * odd_sum + Decimal("2") * even_sum) * step / Decimal("3")


def build_methods():
    return [
        {"name": "Метод левых прямоугольников", "function": integrate_left_rectangles, "order": 1},
        {"name": "Метод правых прямоугольников", "function": integrate_right_rectangles, "order": 1},
        {"name": "Метод средних прямоугольников", "function": integrate_middle_rectangles, "order": 2},
        {"name": "Метод трапеций", "function": integrate_trapezoid, "order": 2},
        {"name": "Метод Симпсона", "function": integrate_simpson, "order": 4},
    ]


def apply_runge_rule(method, order: int, function, left: Decimal, right: Decimal, epsilon: Decimal):
    partitions = START_PARTITIONS
    previous_value = method(function, left, right, partitions)

    for _ in range(MAX_ITERATIONS):
        partitions *= 2
        current_value = method(function, left, right, partitions)
        runge_error = abs(current_value - previous_value) / (Decimal(2) ** order - Decimal("1"))

        if runge_error <= epsilon:
            return current_value, partitions, runge_error

        previous_value = current_value

    raise RuntimeError("Не удалось достичь требуемой точности. Попробуйте увеличить допустимую погрешность.")


def build_regular_segments(function_data, left: Decimal, right: Decimal):
    if function_data["type"] == "proper":
        return [
            {
                "label": "исходный интервал",
                "left": left,
                "right": right,
                "formula": function_data["formula"],
            }
        ]

    if function_data["kind"] == "left":
        return [
            {
                "label": "после замены x = t^2",
                "left": Decimal("0"),
                "right": right.sqrt(),
                "formula": function_left_transformed,
            }
        ]

    if function_data["type"] == "principal_value":
        symmetric_radius = min(-left, right)
        segments = []

        if -left > symmetric_radius:
            segments.append(
                {
                    "label": "левая несокращаемая часть",
                    "left": left,
                    "right": -symmetric_radius,
                    "formula": function_principal_value_original,
                }
            )

        if right > symmetric_radius:
            segments.append(
                {
                    "label": "правая несокращаемая часть",
                    "left": symmetric_radius,
                    "right": right,
                    "formula": function_principal_value_original,
                }
            )

        return segments

    return []


def compute_integral(function_data, method_data, left: Decimal, right: Decimal, epsilon: Decimal):
    if not function_data["converges"]:
        return {"exists": False}

    segments = build_regular_segments(function_data, left, right)
    if not segments:
        return {
            "exists": True,
            "value": Decimal("0"),
            "runge_error": Decimal("0"),
            "partitions_text": "симметричный участок полностью сократился",
            "segments_count": 0,
        }

    segment_epsilon = epsilon / Decimal(len(segments) * 2)
    total_value = Decimal("0")
    total_runge_error = Decimal("0")
    partition_descriptions = []

    for segment in segments:
        value, partitions, runge_error = apply_runge_rule(
            method_data["function"],
            method_data["order"],
            segment["formula"],
            segment["left"],
            segment["right"],
            segment_epsilon,
        )
        total_value += value
        total_runge_error += runge_error
        partition_descriptions.append(f"{segment['label']} -> {partitions}")

    return {
        "exists": True,
        "value": total_value,
        "runge_error": total_runge_error,
        "partitions_text": "; ".join(partition_descriptions),
        "segments_count": len(segments),
    }
