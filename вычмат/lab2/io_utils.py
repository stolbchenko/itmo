from __future__ import annotations

from pathlib import Path
from typing import Tuple


def _float_to_full_decimal(x: float) -> str:
    s = f"{x:.15g}"
    if "e" not in s and "E" not in s:
        return s

    mantissa_s, exp_s = s.lower().split("e")
    exp = int(exp_s)

    sign = ""
    if mantissa_s.startswith("-"):
        sign = "-"
        mantissa_s = mantissa_s[1:]

    if "." in mantissa_s:
        integer_part, frac_part = mantissa_s.split(".")
    else:
        integer_part, frac_part = mantissa_s, ""

    digits = integer_part + frac_part
    dot_position = len(integer_part) + exp

    if dot_position <= 0:
        full = "0." + "0" * (-dot_position) + digits
    elif dot_position >= len(digits):
        full = digits + "0" * (dot_position - len(digits))
    else:
        full = digits[:dot_position] + "." + digits[dot_position:]

    if "." in full:
        full = full.rstrip("0").rstrip(".")

    return sign + full


def format_number(x: float) -> str:
    if x == 0.0:
        return "0"

    sign = ""
    if x < 0:
        sign = "-"
        x = -x

    full = _float_to_full_decimal(x)
    if full.startswith("-"):
        full = full[1:]

    if "." not in full:
        return sign + full

    integer_part, decimal_part = full.split(".")
    num_decimals = len(decimal_part)

    if num_decimals <= 5:
        return f"{sign}{integer_part}.{decimal_part}"

    truncated = decimal_part[:5]
    remaining = num_decimals - 5
    return f"{sign}{integer_part}.{truncated} * 10^(-{remaining})"


def to_float(value: str, field_name: str) -> float:
    cleaned = value.strip().replace(",", ".")
    if not cleaned:
        raise ValueError(
            f"Поле «{field_name}» не заполнено. Введите числовое значение."
        )
    try:
        return float(cleaned)
    except ValueError:
        raise ValueError(
            f"Поле «{field_name}»: значение «{value.strip()}» не является числом. "
            "Допускается точка или запятая в качестве десятичного разделителя."
        )


def to_int(value: str, field_name: str) -> int:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(
            f"Поле «{field_name}» не заполнено. Введите целое число."
        )
    try:
        return int(cleaned)
    except ValueError:
        raise ValueError(
            f"Поле «{field_name}»: значение «{value.strip()}» не является целым числом."
        )


def _read_lines(path: str) -> list[str]:
    file_path = Path(path)
    if not file_path.exists():
        raise ValueError(f"Файл не найден: {path}")
    with file_path.open("r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def load_equation_input(path: str) -> Tuple[float, float, float, int]:
    lines = _read_lines(path)
    if len(lines) < 4:
        raise ValueError(
            f"Файл должен содержать 4 строки (a, b, eps, max_iter), "
            f"найдено строк: {len(lines)}."
        )
    a = to_float(lines[0], "a (строка 1)")
    b = to_float(lines[1], "b (строка 2)")
    eps = to_float(lines[2], "eps (строка 3)")
    max_iter = to_int(lines[3], "max_iter (строка 4)")
    return a, b, eps, max_iter


def load_system_input(path: str) -> Tuple[float, float, float, int]:
    lines = _read_lines(path)
    if len(lines) < 4:
        raise ValueError(
            f"Файл должен содержать 4 строки (x0, y0, eps, max_iter), "
            f"найдено строк: {len(lines)}."
        )
    x0 = to_float(lines[0], "x0 (строка 1)")
    y0 = to_float(lines[1], "y0 (строка 2)")
    eps = to_float(lines[2], "eps (строка 3)")
    max_iter = to_int(lines[3], "max_iter (строка 4)")
    return x0, y0, eps, max_iter


def save_text_output(path: str, content: str) -> None:
    file_path = Path(path)
    if file_path.parent and not file_path.parent.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as f:
        f.write(content)
