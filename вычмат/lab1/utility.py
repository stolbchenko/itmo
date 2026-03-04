from __future__ import annotations

import random
from decimal import Decimal, InvalidOperation
from typing import List, Tuple

from gauss import configure_precision, determinant_only

MAX_N = 20


def parse_decimal(token: str) -> Decimal:
    cleaned = token.strip().replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"'{token}' не является корректным числом") from exc


def read_int_in_range(prompt: str, low: int, high: int) -> int:
    while True:
        raw = input(prompt).strip()
        try:
            value = int(raw)
        except ValueError:
            print("Ошибка: нужно ввести целое число.")
            continue
        if not low <= value <= high:
            print(f"Ошибка: число должно быть в диапазоне {low}..{high}.")
            continue
        return value


def read_decimal_row(prompt: str, expected_len: int) -> List[Decimal]:
    while True:
        raw = input(prompt).strip()
        tokens = raw.split()
        if len(tokens) != expected_len:
            print(f"Ошибка: нужно ввести ровно {expected_len} чисел через пробел.")
            continue
        try:
            return [parse_decimal(token) for token in tokens]
        except ValueError as exc:
            print(f"Ошибка: {exc}")


def read_decimal_value(prompt: str) -> Decimal:
    while True:
        raw = input(prompt).strip()
        try:
            return parse_decimal(raw)
        except ValueError as exc:
            print(f"Ошибка: {exc}")


def random_decimal_in_range(low: Decimal, high: Decimal) -> Decimal:
    low_frac_digits = max(0, -low.as_tuple().exponent)
    high_frac_digits = max(0, -high.as_tuple().exponent)
    frac_digits = max(low_frac_digits, high_frac_digits) + random.randint(1, 12)
    scale = Decimal(10) ** frac_digits

    low_scaled = low * scale
    high_scaled = high * scale

    low_int = int(low_scaled)
    high_int = int(high_scaled)

    if low_int > high_int:
        raise ValueError("Некорректный диапазон генерации.")

    random_int = random.randint(low_int, high_int)
    return Decimal(random_int) / scale


def read_system_from_keyboard() -> Tuple[List[List[Decimal]], List[Decimal]]:
    n = read_int_in_range(f"Введите размерность n (1..{MAX_N}): ", 1, MAX_N)

    print("Введите коэффициенты матрицы A построчно (можно использовать и ',' и '.').")
    a: List[List[Decimal]] = []
    for i in range(n):
        row = read_decimal_row(f"A[{i + 1}] = ", n)
        a.append(row)

    b = read_decimal_row(f"Введите вектор b (ровно {n} чисел): ", n)
    configure_precision(a, b)
    return a, b


def read_system_from_file(file_path: str) -> Tuple[List[List[Decimal]], List[Decimal]]:
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            lines = [line.strip() for line in file if line.strip()]
    except FileNotFoundError as exc:
        raise ValueError("Файл не найден. Проверьте путь и попробуйте снова.") from exc
    except OSError as exc:
        raise ValueError(f"Не удалось прочитать файл: {exc}") from exc

    if not lines:
        raise ValueError("Файл пустой.")

    try:
        n = int(lines[0])
    except ValueError as exc:
        raise ValueError("Первая строка файла должна содержать целое число n.") from exc

    if not 1 <= n <= MAX_N:
        raise ValueError(f"Размерность n должна быть в диапазоне 1..{MAX_N}.")

    if len(lines) != n + 2:
        raise ValueError(
            "Некорректный формат файла.\n"
            "Ожидается:\n"
            "1) n\n"
            "2) n строк матрицы A (по n чисел)\n"
            "3) строка вектора b (n чисел)"
        )

    a: List[List[Decimal]] = []
    for i in range(1, n + 1):
        parts = lines[i].split()
        if len(parts) != n:
            raise ValueError(f"В строке {i + 1} должно быть ровно {n} чисел.")
        try:
            row = [parse_decimal(part) for part in parts]
        except ValueError as exc:
            raise ValueError(f"Ошибка в строке {i + 1}: {exc}") from exc
        a.append(row)

    b_parts = lines[n + 1].split()
    if len(b_parts) != n:
        raise ValueError("Последняя строка файла должна содержать ровно n чисел.")
    try:
        b = [parse_decimal(part) for part in b_parts]
    except ValueError as exc:
        raise ValueError(f"Ошибка в строке вектора b: {exc}") from exc

    configure_precision(a, b)
    return a, b


def generate_random_system() -> Tuple[List[List[Decimal]], List[Decimal]]:
    n = read_int_in_range(f"Введите размерность n (1..{MAX_N}): ", 1, MAX_N)
    print("Задайте диапазон случайных десятичных коэффициентов [min, max].")
    low = read_decimal_value("min = ")
    high = read_decimal_value("max = ")

    if low > high:
        low, high = high, low

    if low == 0 and high == 0:
        raise ValueError("Невозможно сгенерировать невырожденную матрицу из одних нулей.")

    for _ in range(500):
        a = [
            [random_decimal_in_range(low, high) for _ in range(n)]
            for _ in range(n)
        ]
        b = [random_decimal_in_range(low, high) for _ in range(n)]
        if determinant_only(a) != 0:
            configure_precision(a, b)
            print("Случайная невырожденная матрица успешно сгенерирована.")
            return a, b

    raise ValueError(
        "Не удалось сгенерировать невырожденную матрицу в заданном диапазоне. "
        "Попробуйте увеличить диапазон."
    )


def read_input_choice() -> str:
    print("Выберите источник данных:")
    print("1 - Ввод с клавиатуры")
    print("2 - Ввод из файла")
    print("3 - Случайная генерация матрицы")
    print("0 - Выход")
    while True:
        choice = input("Ваш выбор (0/1/2/3): ").strip()
        if choice in {"0", "1", "2", "3"}:
            return choice
        print("Ошибка: введите 0, 1, 2 или 3.")
