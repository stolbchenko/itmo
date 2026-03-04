from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gauss import display_decimal, gauss_elimination, print_augmented_system, print_matrix, print_vector, residual_vector
from utility import (
    generate_random_system,
    read_input_choice,
    read_system_from_file,
    read_system_from_keyboard,
)


def main() -> None:
    print("Лабораторная работа №1. Решение СЛАУ")
    print("Вариант 17: Метод Гаусса")

    choice = read_input_choice()

    if choice == "0":
        print("Выход из программы.")
        return
    if choice == "1":
        a, b = read_system_from_keyboard()
    elif choice == "2":
        path = input("Введите путь к файлу: ").strip()
        a, b = read_system_from_file(path)
    else:
        a, b = generate_random_system()

    a_original = [row[:] for row in a]
    b_original = b[:]

    print()
    print_augmented_system(a_original, b_original, "Исходная матрица:")

    x, triangular_aug, det_a = gauss_elimination(a, b)
    r = residual_vector(a_original, b_original, x)

    print()
    print_matrix(triangular_aug, "Треугольная расширенная матрица [U|c]:")
    print("\nОпределитель det(A):", display_decimal(det_a))
    print_vector(x, "x", "\nВектор неизвестных:")
    print_vector(r, "r", "\nВектор невязок r = b - A*x:")


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        print(f"Ошибка: {exc}")
    except Exception as exc:
        print(f"Непредвиденная ошибка: {exc}")
