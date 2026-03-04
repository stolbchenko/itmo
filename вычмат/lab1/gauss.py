from __future__ import annotations

from decimal import Decimal, getcontext
from typing import List, Tuple


def configure_precision(a: List[List[Decimal]], b: List[Decimal]) -> None:
    max_digits = 1
    for row in a:
        for value in row:
            max_digits = max(max_digits, len(value.as_tuple().digits))
    for value in b:
        max_digits = max(max_digits, len(value.as_tuple().digits))
    getcontext().prec = max(60, max_digits * 3 + 20)


def determinant_only(a: List[List[Decimal]]) -> Decimal:
    n = len(a)
    u = [row[:] for row in a]
    swap_count = 0

    for k in range(n):
        if u[k][k] == 0:
            swap_row = None
            for i in range(k + 1, n):
                if u[i][k] != 0:
                    swap_row = i
                    break
            if swap_row is None:
                return Decimal(0)
            u[k], u[swap_row] = u[swap_row], u[k]
            swap_count += 1

        pivot = u[k][k]
        for i in range(k + 1, n):
            factor = u[i][k] / pivot
            for j in range(k, n):
                u[i][j] -= factor * u[k][j]

    det = Decimal(-1) if swap_count % 2 else Decimal(1)
    for i in range(n):
        det *= u[i][i]
    return det


def gauss_elimination(
    a: List[List[Decimal]],
    b: List[Decimal],
) -> Tuple[List[Decimal], List[List[Decimal]], Decimal]:
    n = len(a)
    aug = [row[:] + [b_i] for row, b_i in zip(a, b)]
    swap_count = 0
    for k in range(n):
        if aug[k][k] == 0:
            swap_row = None
            for i in range(k + 1, n):
                if aug[i][k] != 0:
                    swap_row = i
                    break
            if swap_row is None:
                raise ValueError("Система не имеет единственного решения: det(A) = 0.")
            aug[k], aug[swap_row] = aug[swap_row], aug[k]
            swap_count += 1
        pivot = aug[k][k]
        for i in range(k + 1, n):
            factor = aug[i][k] / pivot
            for j in range(k, n + 1):
                aug[i][j] -= factor * aug[k][j]
    det = Decimal(-1) if swap_count % 2 else Decimal(1)
    for i in range(n):
        det *= aug[i][i]
    if det == 0:
        raise ValueError("Система не имеет единственного решения: det(A) = 0.")
    x = [Decimal(0)] * n
    for i in range(n - 1, -1, -1):
        s = sum(aug[i][j] * x[j] for j in range(i + 1, n))
        x[i] = (aug[i][n] - s) / aug[i][i]
    return x, aug, det


def residual_vector(a: List[List[Decimal]], b: List[Decimal], x: List[Decimal]) -> List[Decimal]:
    n = len(a)
    return [b[i] - sum(a[i][j] * x[j] for j in range(n)) for i in range(n)]


FRAC_LIMIT = 5


def display_decimal(value: Decimal) -> str:
    if value == 0:
        return "0"

    full = format(value.normalize(), "f")

    if full.startswith("-"):
        sign_str = "-"
        unsigned = full[1:]
    else:
        sign_str = ""
        unsigned = full

    if "." in unsigned:
        int_part, frac_raw = unsigned.split(".")
        frac = frac_raw.rstrip("0")
    else:
        int_part = unsigned
        frac = ""

    frac_len = len(frac)

    if frac_len <= FRAC_LIMIT:
        if frac:
            return f"{sign_str}{int_part}.{frac}"
        return f"{sign_str}{int_part}"

    short_frac = frac[:FRAC_LIMIT].rstrip("0")
    power = frac_len - FRAC_LIMIT

    if int_part.lstrip("0") == "" and not short_frac:
        leading_zeros = len(frac) - len(frac.lstrip("0"))
        sig_digits = frac.lstrip("0")[:FRAC_LIMIT]
        m = -(leading_zeros + 1)
        if len(sig_digits) > 1:
            k = sig_digits[0] + "." + sig_digits[1:].rstrip("0")
        else:
            k = sig_digits
        return f"{sign_str}{k} * 10^{m}"

    if short_frac:
        return f"{sign_str}{int_part}.{short_frac} * 10^{power}"
    return f"{sign_str}{int_part} * 10^{power}"


def print_augmented_system(a: List[List[Decimal]], b: List[Decimal], title: str) -> None:
    n = len(a)
    headers = [f"x{i}" for i in range(1, n + 1)] + ["b"]
    str_rows = [[display_decimal(v) for v in row] + [display_decimal(b[i])] for i, row in enumerate(a)]

    col_widths = [max(len(headers[c]), max(len(row[c]) for row in str_rows)) for c in range(n + 1)]

    print(title)
    print("  ".join(h.rjust(w) for h, w in zip(headers, col_widths)))
    for row in str_rows:
        print("  ".join(s.rjust(w) for s, w in zip(row, col_widths)))


def print_matrix(matrix: List[List[Decimal]], title: str) -> None:
    print(title)
    str_rows = [[display_decimal(v) for v in row] for row in matrix]
    col_widths: List[int] = []
    for col in range(len(str_rows[0])):
        col_widths.append(max(len(row[col]) for row in str_rows))
    for row in str_rows:
        print("  ".join(s.rjust(w) for s, w in zip(row, col_widths)))


def print_vector(vector: List[Decimal], prefix: str, title: str) -> None:
    print(title)
    for i, value in enumerate(vector, start=1):
        print(f"{prefix}{i} = {display_decimal(value)}")
