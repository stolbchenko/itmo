from decimal import localcontext

from core import (
    compute_dynamic_precision,
    compute_integral,
    format_decimal_for_output,
    build_functions,
    build_methods,
    validate_interval,
)
from ui import parse_decimal, parse_positive_decimal, read_value, read_function_choice, read_method_choice


def main():
    functions = build_functions()
    methods = build_methods()

    epsilon = read_value("Введите желаемую точность вычисления: ", parse_positive_decimal)
    left_border = read_value("Введите нижний предел интегрирования: ", parse_decimal)
    right_border = read_value("Введите верхний предел интегрирования: ", parse_decimal)

    function_index = read_function_choice(functions)
    selected_function = functions[function_index]

    try:
        validate_interval(selected_function, left_border, right_border)
    except ValueError as error:
        print(f"Ошибка: {error}")
        return

    print()
    print(f"Проверка сходимости: {selected_function['reason']}")
    if selected_function["type"] == "improper_2nd" and not selected_function["converges"]:
        print("Интеграл не существует.")
        return

    method_index = read_method_choice(methods)
    selected_method = methods[method_index]

    dynamic_precision = compute_dynamic_precision(epsilon, left_border, right_border)

    try:
        with localcontext() as context:
            context.prec = dynamic_precision
            result = compute_integral(
                selected_function,
                selected_method,
                left_border,
                right_border,
                epsilon,
            )
    except (ArithmeticError, ValueError, RuntimeError) as error:
        print(f"Ошибка: {error}")
        return

    print()
    print(f"Выбранная функция: {selected_function['name']}")
    print(f"Выбранный метод: {selected_method['name']}")
    print(f"Интервал интегрирования: [{format_decimal_for_output(left_border)}; {format_decimal_for_output(right_border)}]")
    print(f"Требуемая точность: {format_decimal_for_output(epsilon)}")
    print(f"Преобразование: {selected_function['substitution']}")
    print(f"Приближенное значение интеграла: {format_decimal_for_output(result['value'])}")
    print(f"Оценка погрешности по правилу Рунге: {format_decimal_for_output(result['runge_error'])}")
    print(f"Число разбиений интервала: {result['partitions_text']}")


if __name__ == "__main__":
    main()
