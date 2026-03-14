from decimal import Decimal, InvalidOperation


def parse_decimal(user_input: str) -> Decimal:
    normalized = user_input.strip().replace(",", ".")
    if not normalized:
        raise ValueError("Пустой ввод. Введите число.")

    if normalized.count(".") > 1:
        raise ValueError("Число содержит несколько разделителей дробной части.")

    try:
        return Decimal(normalized)
    except InvalidOperation as error:
        raise ValueError(
            "Не удалось распознать число. Используйте только цифры, знак и разделитель '.' или ','."
        ) from error


def parse_positive_decimal(user_input: str) -> Decimal:
    value = parse_decimal(user_input)
    if value <= 0:
        raise ValueError("Точность должна быть положительным числом.")
    return value


def parse_menu_choice(user_input: str, max_choice: int) -> int:
    stripped = user_input.strip()
    if not stripped:
        raise ValueError("Пустой ввод. Выберите один из пунктов меню.")
    if not stripped.isdigit():
        raise ValueError("Номер пункта должен быть целым положительным числом.")

    choice = int(stripped)
    if choice < 1 or choice > max_choice:
        raise ValueError(f"Допустимые номера пунктов: от 1 до {max_choice}.")
    return choice


def read_value(prompt: str, parser):
    while True:
        raw_value = input(prompt)
        try:
            return parser(raw_value)
        except ValueError as error:
            print(f"Ошибка: {error}")


def read_function_choice(functions) -> int:
    print("Доступные функции:")
    for index, function_data in enumerate(functions, start=1):
        if function_data["type"] == "improper_2nd":
            function_type = "несобственный 2 рода"
        elif function_data["type"] == "principal_value":
            function_type = "главное значение"
        else:
            function_type = "собственный"
        print(f"{index}. {function_data['name']} ({function_type})")
        print(f"   {function_data['description']}")
    return read_value("Выберите функцию: ", lambda value: parse_menu_choice(value, len(functions))) - 1


def read_method_choice(methods) -> int:
    method_map = {
        "1.1": 0,
        "1.2": 1,
        "1.3": 2,
        "2": 3,
        "3": 4,
    }

    def parse_method_choice(value: str) -> int:
        normalized = value.strip().replace(",", ".")
        if normalized in method_map:
            return method_map[normalized]
        raise ValueError("Введите один из вариантов: 1.1, 1.2, 1.3, 2 или 3.")

    print("Доступные численные методы:")
    print("1.1 Метод прямоугольников (левые)")
    print("1.2 Метод прямоугольников (правые)")
    print("1.3 Метод прямоугольников (средние)")
    print("2 Метод трапеций")
    print("3 Метод Симпсона")
    return read_value("Выберите метод: ", parse_method_choice)
