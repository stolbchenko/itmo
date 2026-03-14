from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any

from io_utils import (
    format_number,
    load_equation_input,
    load_system_input,
    save_text_output,
    to_float,
    to_int,
)
from methods_equations import (
    bisection_method,
    choose_newton_start,
    choose_simple_iteration_start,
    newton_method,
    simple_iteration_method,
    validate_interval,
)
from methods_systems import newton_system_method
from models import get_equations, get_systems
from plotting import plot_equation, plot_system
from plotting import plot_simple_iteration


EQUATION_METHODS = {
    "1 - Половинное деление": "bisection",
    "3 - Ньютон": "newton",
    "5 - Простая итерация": "simple_iteration",
}

SYSTEM_METHODS = {
    "6 - Ньютон": "newton_system",
}


class Lab2App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ЛР2 — Нелинейные уравнения и системы (вариант 12)")
        self.geometry("1100x780")

        self.equations = get_equations()
        self.systems = get_systems()

        self._build_ui()

    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        eq_tab = ttk.Frame(notebook)
        sys_tab = ttk.Frame(notebook)
        notebook.add(eq_tab, text="Нелинейное уравнение")
        notebook.add(sys_tab, text="Система уравнений")

        self._build_equation_tab(eq_tab)
        self._build_system_tab(sys_tab)

    def _build_common_output_panel(
        self, parent: ttk.Frame, row_start: int
    ) -> tuple[tk.StringVar, ttk.Entry]:
        ttk.Label(parent, text="Вывод результата:").grid(
            row=row_start, column=0, sticky="w", padx=6, pady=4
        )
        output_mode = tk.StringVar(value="screen")
        ttk.Radiobutton(
            parent, text="На экран", value="screen", variable=output_mode
        ).grid(row=row_start, column=1, sticky="w")
        ttk.Radiobutton(
            parent, text="В файл", value="file", variable=output_mode
        ).grid(row=row_start, column=2, sticky="w")

        ttk.Label(parent, text="Файл вывода:").grid(
            row=row_start + 1, column=0, sticky="w", padx=6, pady=4
        )
        output_entry = ttk.Entry(parent, width=42)
        output_entry.grid(
            row=row_start + 1, column=1, columnspan=2, sticky="we", padx=6, pady=4
        )
        ttk.Button(
            parent, text="Обзор", command=lambda: self._pick_output_file(output_entry)
        ).grid(row=row_start + 1, column=3, padx=6, pady=4)
        return output_mode, output_entry

    def _build_equation_tab(self, tab: ttk.Frame) -> None:
        frame = ttk.Frame(tab)
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        for col in range(4):
            frame.columnconfigure(col, weight=1)

        ttk.Label(frame, text="Выбор уравнения:").grid(
            row=0, column=0, sticky="w", padx=6, pady=4
        )
        self.eq_selector = ttk.Combobox(
            frame,
            values=[f"{eq.equation_id}: {eq.title}" for eq in self.equations],
            state="readonly",
        )
        self.eq_selector.current(0)
        self.eq_selector.grid(row=0, column=1, columnspan=3, sticky="we", padx=6, pady=4)

        ttk.Label(frame, text="Метод:").grid(
            row=1, column=0, sticky="w", padx=6, pady=4
        )
        self.eq_method_selector = ttk.Combobox(
            frame, values=list(EQUATION_METHODS.keys()), state="readonly"
        )
        self.eq_method_selector.current(0)
        self.eq_method_selector.grid(
            row=1, column=1, columnspan=3, sticky="we", padx=6, pady=4
        )

        ttk.Separator(frame, orient="horizontal").grid(
            row=2, column=0, columnspan=4, sticky="we", pady=6
        )

        self.eq_input_mode = tk.StringVar(value="manual")
        self.eq_input_mode.trace_add("write", lambda *_: self._toggle_eq_input())
        ttk.Label(frame, text="Источник входных данных:").grid(
            row=3, column=0, sticky="w", padx=6, pady=4
        )
        ttk.Radiobutton(
            frame, text="С клавиатуры", value="manual", variable=self.eq_input_mode
        ).grid(row=3, column=1, sticky="w")
        ttk.Radiobutton(
            frame, text="Из файла", value="file", variable=self.eq_input_mode
        ).grid(row=3, column=2, sticky="w")

        self.eq_file_frame = ttk.Frame(frame)
        self.eq_file_frame.columnconfigure(1, weight=1)
        ttk.Label(self.eq_file_frame, text="Файл входных данных:").grid(
            row=0, column=0, sticky="w", padx=6, pady=4
        )
        self.eq_input_file = ttk.Entry(self.eq_file_frame, width=42)
        self.eq_input_file.grid(row=0, column=1, sticky="we", padx=6, pady=4)
        ttk.Button(
            self.eq_file_frame,
            text="Обзор",
            command=lambda: self._pick_input_file(self.eq_input_file),
        ).grid(row=0, column=2, padx=6, pady=4)

        self.eq_manual_frame = ttk.Frame(frame)
        for c in range(4):
            self.eq_manual_frame.columnconfigure(c, weight=1)

        ttk.Label(self.eq_manual_frame, text="Левая граница a:").grid(
            row=0, column=0, sticky="w", padx=6, pady=4
        )
        self.eq_a = ttk.Entry(self.eq_manual_frame)
        self.eq_a.insert(0, "-1")
        self.eq_a.grid(row=0, column=1, sticky="we", padx=6, pady=4)

        ttk.Label(self.eq_manual_frame, text="Правая граница b:").grid(
            row=0, column=2, sticky="w", padx=6, pady=4
        )
        self.eq_b = ttk.Entry(self.eq_manual_frame)
        self.eq_b.insert(0, "1")
        self.eq_b.grid(row=0, column=3, sticky="we", padx=6, pady=4)

        ttk.Label(self.eq_manual_frame, text="Погрешность eps:").grid(
            row=1, column=0, sticky="w", padx=6, pady=4
        )
        self.eq_eps = ttk.Entry(self.eq_manual_frame)
        self.eq_eps.insert(0, "0.001")
        self.eq_eps.grid(row=1, column=1, sticky="we", padx=6, pady=4)

        ttk.Label(self.eq_manual_frame, text="Макс. итераций:").grid(
            row=1, column=2, sticky="w", padx=6, pady=4
        )
        self.eq_max_iter = ttk.Entry(self.eq_manual_frame)
        self.eq_max_iter.insert(0, "100")
        self.eq_max_iter.grid(row=1, column=3, sticky="we", padx=6, pady=4)

        self.eq_manual_frame.grid(row=4, column=0, columnspan=4, sticky="we")

        self.eq_plot_flag = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            frame, text="Построить график", variable=self.eq_plot_flag
        ).grid(row=5, column=0, columnspan=2, sticky="w", padx=6)

        self.eq_output_mode, self.eq_output_file = self._build_common_output_panel(
            frame, row_start=6
        )

        ttk.Button(frame, text="Запустить расчёт", command=self.run_equation).grid(
            row=8, column=0, columnspan=4, sticky="we", padx=6, pady=8
        )

        self.eq_text = tk.Text(frame, height=16, wrap="none", font=("Courier", 11))
        eq_scroll = ttk.Scrollbar(frame, orient="horizontal", command=self.eq_text.xview)
        self.eq_text.configure(xscrollcommand=eq_scroll.set)
        self.eq_text.grid(row=9, column=0, columnspan=4, sticky="nsew", padx=6, pady=6)
        eq_scroll.grid(row=10, column=0, columnspan=4, sticky="we", padx=6)
        frame.rowconfigure(9, weight=1)

    def _build_system_tab(self, tab: ttk.Frame) -> None:
        frame = ttk.Frame(tab)
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        for col in range(4):
            frame.columnconfigure(col, weight=1)

        ttk.Label(frame, text="Выбор системы:").grid(
            row=0, column=0, sticky="w", padx=6, pady=4
        )
        self.sys_selector = ttk.Combobox(
            frame,
            values=[f"{s.system_id}: {s.title}" for s in self.systems],
            state="readonly",
        )
        self.sys_selector.current(0)
        self.sys_selector.grid(row=0, column=1, columnspan=3, sticky="we", padx=6, pady=4)

        ttk.Label(frame, text="Метод:").grid(
            row=1, column=0, sticky="w", padx=6, pady=4
        )
        self.sys_method_selector = ttk.Combobox(
            frame, values=list(SYSTEM_METHODS.keys()), state="readonly"
        )
        self.sys_method_selector.current(0)
        self.sys_method_selector.grid(
            row=1, column=1, columnspan=3, sticky="we", padx=6, pady=4
        )

        ttk.Separator(frame, orient="horizontal").grid(
            row=2, column=0, columnspan=4, sticky="we", pady=6
        )

        self.sys_input_mode = tk.StringVar(value="manual")
        self.sys_input_mode.trace_add("write", lambda *_: self._toggle_sys_input())
        ttk.Label(frame, text="Источник входных данных:").grid(
            row=3, column=0, sticky="w", padx=6, pady=4
        )
        ttk.Radiobutton(
            frame, text="С клавиатуры", value="manual", variable=self.sys_input_mode
        ).grid(row=3, column=1, sticky="w")
        ttk.Radiobutton(
            frame, text="Из файла", value="file", variable=self.sys_input_mode
        ).grid(row=3, column=2, sticky="w")

        self.sys_file_frame = ttk.Frame(frame)
        self.sys_file_frame.columnconfigure(1, weight=1)
        ttk.Label(self.sys_file_frame, text="Файл входных данных:").grid(
            row=0, column=0, sticky="w", padx=6, pady=4
        )
        self.sys_input_file = ttk.Entry(self.sys_file_frame, width=42)
        self.sys_input_file.grid(row=0, column=1, sticky="we", padx=6, pady=4)
        ttk.Button(
            self.sys_file_frame,
            text="Обзор",
            command=lambda: self._pick_input_file(self.sys_input_file),
        ).grid(row=0, column=2, padx=6, pady=4)

        self.sys_manual_frame = ttk.Frame(frame)
        for c in range(4):
            self.sys_manual_frame.columnconfigure(c, weight=1)

        ttk.Label(self.sys_manual_frame, text="Начальное приближение x0:").grid(
            row=0, column=0, sticky="w", padx=6, pady=4
        )
        self.sys_x0 = ttk.Entry(self.sys_manual_frame)
        self.sys_x0.insert(0, "0")
        self.sys_x0.grid(row=0, column=1, sticky="we", padx=6, pady=4)

        ttk.Label(self.sys_manual_frame, text="Начальное приближение y0:").grid(
            row=0, column=2, sticky="w", padx=6, pady=4
        )
        self.sys_y0 = ttk.Entry(self.sys_manual_frame)
        self.sys_y0.insert(0, "0")
        self.sys_y0.grid(row=0, column=3, sticky="we", padx=6, pady=4)

        ttk.Label(self.sys_manual_frame, text="Погрешность eps:").grid(
            row=1, column=0, sticky="w", padx=6, pady=4
        )
        self.sys_eps = ttk.Entry(self.sys_manual_frame)
        self.sys_eps.insert(0, "0.001")
        self.sys_eps.grid(row=1, column=1, sticky="we", padx=6, pady=4)

        ttk.Label(self.sys_manual_frame, text="Макс. итераций:").grid(
            row=1, column=2, sticky="w", padx=6, pady=4
        )
        self.sys_max_iter = ttk.Entry(self.sys_manual_frame)
        self.sys_max_iter.insert(0, "100")
        self.sys_max_iter.grid(row=1, column=3, sticky="we", padx=6, pady=4)

        self.sys_manual_frame.grid(row=4, column=0, columnspan=4, sticky="we")

        ttk.Label(frame, text="Область графика (x_min;x_max;y_min;y_max):").grid(
            row=5, column=0, sticky="w", padx=6, pady=4
        )
        self.sys_plot_range = ttk.Entry(frame)
        self.sys_plot_range.insert(0, "-3;3;-3;3")
        self.sys_plot_range.grid(
            row=5, column=1, columnspan=2, sticky="we", padx=6, pady=4
        )
        self.sys_plot_flag = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            frame, text="Построить график", variable=self.sys_plot_flag
        ).grid(row=5, column=3, sticky="w")

        self.sys_output_mode, self.sys_output_file = self._build_common_output_panel(
            frame, row_start=6
        )

        ttk.Button(frame, text="Запустить расчёт", command=self.run_system).grid(
            row=8, column=0, columnspan=4, sticky="we", padx=6, pady=8
        )

        self.sys_text = tk.Text(frame, height=16, wrap="none", font=("Courier", 11))
        sys_scroll = ttk.Scrollbar(frame, orient="horizontal", command=self.sys_text.xview)
        self.sys_text.configure(xscrollcommand=sys_scroll.set)
        self.sys_text.grid(row=9, column=0, columnspan=4, sticky="nsew", padx=6, pady=6)
        sys_scroll.grid(row=10, column=0, columnspan=4, sticky="we", padx=6)
        frame.rowconfigure(9, weight=1)

    def _pick_input_file(self, target: ttk.Entry) -> None:
        path = filedialog.askopenfilename(
            title="Выберите файл с входными данными",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            target.delete(0, tk.END)
            target.insert(0, path)

    def _pick_output_file(self, target: ttk.Entry) -> None:
        path = filedialog.asksaveasfilename(
            title="Сохранить результат в файл",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            target.delete(0, tk.END)
            target.insert(0, path)

    def _toggle_eq_input(self) -> None:
        if self.eq_input_mode.get() == "manual":
            self.eq_file_frame.grid_remove()
            self.eq_manual_frame.grid(row=4, column=0, columnspan=4, sticky="we")
        else:
            self.eq_manual_frame.grid_remove()
            self.eq_file_frame.grid(row=4, column=0, columnspan=4, sticky="we")

    def _toggle_sys_input(self) -> None:
        if self.sys_input_mode.get() == "manual":
            self.sys_file_frame.grid_remove()
            self.sys_manual_frame.grid(row=4, column=0, columnspan=4, sticky="we")
        else:
            self.sys_manual_frame.grid_remove()
            self.sys_file_frame.grid(row=4, column=0, columnspan=4, sticky="we")

    def _selected_equation(self):
        equation_id = self.eq_selector.get().split(":")[0]
        return next(eq for eq in self.equations if eq.equation_id == equation_id)

    def _selected_system(self):
        system_id = self.sys_selector.get().split(":")[0]
        return next(s for s in self.systems if s.system_id == system_id)

    def _show_output(
        self, text_widget: tk.Text, output_mode: str, output_path: str, content: str
    ) -> None:
        text_widget.delete("1.0", tk.END)
        text_widget.insert("1.0", content)
        if output_mode == "file":
            if not output_path.strip():
                raise ValueError(
                    "Для записи результата в файл необходимо указать путь "
                    "к выходному файлу (кнопка «Обзор» или ввод вручную)."
                )
            save_text_output(output_path, content)
            messagebox.showinfo(
                "Сохранено",
                f"Результат успешно сохранён в файл:\n{output_path}",
            )

    def _format_equation_result(
        self,
        method_label: str,
        result: Any,
        x0_used: float,
        q_value: float | None = None,
        phi_expr: str | None = None,
    ) -> str:
        fn = format_number
        lines = [
            f"Метод: {method_label}",
            f"Начальное приближение x0: {fn(x0_used)}",
            f"Найденный корень: {fn(result.root)}",
            f"Значение функции в корне f(root): {fn(result.f_root)}",
            f"Число итераций: {result.iterations}",
        ]
        if phi_expr is not None:
            lines.append(f"phi(x) = {phi_expr}")
            lines.append("Итерационная формула: x_(k+1) = phi(x_k)")
        if q_value is not None:
            lines.append(f"Оценка q = max|phi'(x)| на интервале: {fn(q_value)}")
        lines.append("")
        lines.append("Таблица итераций:")
        header = f"{'k':>4} | {'x_prev':>22} | {'x_curr':>22} | {'f(x_curr)':>22} | {'|x_curr - x_prev|':>22}"
        lines.append(header)
        lines.append("-" * len(header))
        for row in result.rows:
            lines.append(
                f"{row.iteration:4d} | {fn(row.x_prev):>22} | {fn(row.x_curr):>22} "
                f"| {fn(row.f_curr):>22} | {fn(row.error):>22}"
            )
        return "\n".join(lines)

    def _format_system_result(self, result: Any) -> str:
        fn = format_number
        lines = [
            "Метод: 6 — Ньютон",
            f"Вектор неизвестных:  x1 = {fn(result.x)},  x2 = {fn(result.y)}",
            f"Число итераций: {result.iterations}",
            f"Невязка F1(x1, x2): {fn(result.residual_1)}",
            f"Невязка F2(x1, x2): {fn(result.residual_2)}",
            "",
            f"Проверка сходимости (спектральный радиус якобиана):",
            f"  ρ(J) в начальной точке: {fn(result.spectral_radius_initial)}",
        ]
        if result.spectral_radius_initial < 1e-14:
            lines.append("  Якобиан вырожден в начальной точке — сходимость не гарантирована.")
        else:
            lines.append(
                f"  Якобиан невырожден (ρ > 0), метод Ньютона применим."
            )

        lines.append("")
        lines.append("Таблица итераций:")
        header = (
            f"{'k':>4} | {'x1':>22} | {'x2':>22} "
            f"| {'dx1':>22} | {'dx2':>22} | {'max(|dx1|,|dx2|)':>22} | {'ρ(J)':>14}"
        )
        lines.append(header)
        lines.append("-" * len(header))
        for row in result.rows:
            lines.append(
                f"{row.iteration:4d} | {fn(row.x):>22} | {fn(row.y):>22} "
                f"| {fn(row.dx):>22} | {fn(row.dy):>22} | {fn(row.error):>22} "
                f"| {fn(row.spectral_radius):>14}"
            )
        return "\n".join(lines)

    def _parse_range(self, value: str) -> tuple[float, float, float, float]:
        parts = [p.strip().replace(",", ".") for p in value.split(";")]
        if len(parts) != 4:
            raise ValueError(
                "Область графика задаётся четырьмя числами через точку с запятой: "
                "x_min;x_max;y_min;y_max. Пример: -3;3;-3;3."
            )
        try:
            x_min, x_max, y_min, y_max = [float(p) for p in parts]
        except ValueError:
            raise ValueError(
                "Одно из значений области графика не является числом. "
                "Введите четыре числа через точку с запятой."
            )
        if x_max <= x_min or y_max <= y_min:
            raise ValueError(
                "Некорректная область графика: "
                "x_max должен быть больше x_min, y_max больше y_min."
            )
        return x_min, x_max, y_min, y_max

    def run_equation(self) -> None:
        equation = None
        a = b = None
        root = None
        method = None
        try:
            equation = self._selected_equation()
            method_label = self.eq_method_selector.get()
            method = EQUATION_METHODS[method_label]

            if self.eq_input_mode.get() == "file":
                a, b, eps, max_iter = load_equation_input(self.eq_input_file.get())
            else:
                a = to_float(self.eq_a.get(), "Левая граница a")
                b = to_float(self.eq_b.get(), "Правая граница b")
                eps = to_float(self.eq_eps.get(), "Погрешность eps")
                max_iter = to_int(self.eq_max_iter.get(), "Макс. итераций")

            if eps <= 0:
                raise ValueError(
                    "Погрешность eps должна быть положительным числом."
                )
            if max_iter <= 0:
                raise ValueError(
                    "Максимальное число итераций должно быть положительным целым числом."
                )

            q_value = None
            phi_expr = None
            x0_used = 0.0
            if method == "bisection":
                ok, msg = validate_interval(equation.f, a, b)
                if not ok:
                    raise ValueError(msg)
                x0_used = (a + b) / 2
                result = bisection_method(equation, a, b, eps, max_iter)
            elif method == "newton":
                x0_used = choose_newton_start(equation, a, b)
                result = newton_method(equation, a, b, eps, max_iter)
            else:
                """converges, q_value = check_simple_iteration_convergence(equation, a, b)"""
                """if not converges:
                    raise ValueError(
                        f"Достаточное условие сходимости метода простой итерации "
                        f"не выполнено на интервале [{a}, {b}]: "
                        f"q = max|phi'(x)| = {format_number(q_value)} >= 1.\n\n"
                        f"Попробуйте сузить интервал или выбрать другой метод."
                    )"""
                x0_used = choose_simple_iteration_start(equation, a, b)
                result = simple_iteration_method(equation, a, b, eps, max_iter, x0=None)
                phi_expr = equation.phi_expr

            root = result.root
            content = self._format_equation_result(
                method_label,
                result,
                x0_used=x0_used,
                q_value=q_value,
                phi_expr=phi_expr,
            )
            self._show_output(
                self.eq_text,
                self.eq_output_mode.get(),
                self.eq_output_file.get(),
                content,
            )

        except Exception as exc:
            self.eq_text.delete("1.0", tk.END)
            self.eq_text.insert("1.0", f"Ошибка при решении уравнения:\n{exc}")
            messagebox.showerror("Ошибка при решении уравнения", str(exc))
            return

        if (
            self.eq_plot_flag.get()
            and method is not None
            and equation is not None
            and a is not None
            and b is not None
        ):
            if method == "simple_iteration":
                plot_simple_iteration(equation.phi, a, b, result.rows, root)
            else:
                plot_equation(equation.f, a, b, root)

    def run_system(self) -> None:
        try:
            system = self._selected_system()

            if self.sys_input_mode.get() == "file":
                x0, y0, eps, max_iter = load_system_input(self.sys_input_file.get())
                x_min, x_max, y_min, y_max = self._parse_range(self.sys_plot_range.get())
            else:
                x0 = to_float(self.sys_x0.get(), "Начальное приближение x0")
                y0 = to_float(self.sys_y0.get(), "Начальное приближение y0")
                eps = to_float(self.sys_eps.get(), "Погрешность eps")
                max_iter = to_int(self.sys_max_iter.get(), "Макс. итераций")
                x_min, x_max, y_min, y_max = self._parse_range(self.sys_plot_range.get())

            if eps <= 0:
                raise ValueError(
                    "Погрешность eps должна быть положительным числом."
                )
            if max_iter <= 0:
                raise ValueError(
                    "Максимальное число итераций должно быть положительным целым числом."
                )

            result = newton_system_method(system, x0=x0, y0=y0, eps=eps, max_iter=max_iter)
            content = self._format_system_result(result)
            self._show_output(
                self.sys_text,
                self.sys_output_mode.get(),
                self.sys_output_file.get(),
                content,
            )

            if abs(result.residual_1) > eps or abs(result.residual_2) > eps:
                messagebox.showwarning(
                    "Проверка решения системы",
                    f"Решение найдено, но невязка одного из уравнений превышает eps:\n"
                    f"  F1(x1, x2) = {format_number(result.residual_1)}\n"
                    f"  F2(x1, x2) = {format_number(result.residual_2)}\n\n"
                    f"Рекомендуется проверить начальное приближение или уменьшить eps.",
                )
            else:
                messagebox.showinfo(
                    "Проверка решения системы",
                    f"Подстановка найденного решения в систему:\n"
                    f"  F1(x1, x2) = {format_number(result.residual_1)}\n"
                    f"  F2(x1, x2) = {format_number(result.residual_2)}\n\n"
                    f"Обе невязки меньше eps = {format_number(eps)}. Решение корректно.",
                )

            if self.sys_plot_flag.get():
                plot_system(system, x_min, x_max, y_min, y_max, (result.x, result.y))

        except Exception as exc:
            messagebox.showerror("Ошибка при решении системы", str(exc))


if __name__ == "__main__":
    app = Lab2App()
    app.mainloop()
