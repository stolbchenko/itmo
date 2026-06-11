from __future__ import annotations

import os
import re
import tempfile
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "lab6_matplotlib"))

try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
except ModuleNotFoundError:
    FigureCanvasTkAgg = None
    Figure = None

from ode_solver import (
    EQUATIONS,
    OdeInputError,
    SolutionResult,
    format_full_report,
    format_number,
    parse_cauchy_input,
    solve_cauchy,
)


COLORS = {
    "exact": "#111111",
    "euler": "#d1495b",
    "rk4": "#00798c",
    "milne": "#6a4c93",
}

_MD_INLINE_RE = re.compile(r"\*\*(.+?)\*\*|`(.+?)`")


@dataclass
class MethodTab:
    key: str
    title: str
    stats_text: tk.Text
    table: ttk.Treeview
    graph_label: ttk.Label
    figure: Any = None
    axes: Any = None
    canvas: Any = None


def _setup_markdown_tags(widget: tk.Text) -> None:
    widget.tag_configure("h1", font=("Helvetica", 15, "bold"), spacing1=8, spacing3=6)
    widget.tag_configure("h2", font=("Helvetica", 13, "bold"), spacing1=8, spacing3=4)
    widget.tag_configure("bold", font=("Courier", 11, "bold"))
    widget.tag_configure("code", font=("Courier", 11), background="#f4f4f4", foreground="#9f1239")
    widget.tag_configure("quote", lmargin1=18, lmargin2=18, foreground="#30638e")
    widget.tag_configure("bullet", foreground="#555555")
    widget.tag_configure("mono", font=("Courier", 10), background="#f7f7f7", foreground="#222222")


def _insert_markdown_inline(widget: tk.Text, text: str, tags: tuple[str, ...] = ()) -> None:
    position = 0
    for match in _MD_INLINE_RE.finditer(text):
        if match.start() > position:
            widget.insert(tk.END, text[position:match.start()], tags)
        if match.group(1) is not None:
            widget.insert(tk.END, match.group(1), tags + ("bold",))
        else:
            widget.insert(tk.END, match.group(2), tags + ("code",))
        position = match.end()
    if position < len(text):
        widget.insert(tk.END, text[position:], tags)


def render_markdown(widget: tk.Text, markdown_text: str) -> None:
    _setup_markdown_tags(widget)
    widget.configure(state="normal")
    widget.delete("1.0", tk.END)
    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("# "):
            widget.insert(tk.END, line[2:] + "\n", "h1")
        elif line.startswith("## "):
            widget.insert(tk.END, line[3:] + "\n", "h2")
        elif line.startswith("> "):
            _insert_markdown_inline(widget, line[2:] + "\n", ("quote",))
        elif line.startswith("- "):
            widget.insert(tk.END, "  - ", "bullet")
            _insert_markdown_inline(widget, line[2:] + "\n")
        elif line.startswith("    "):
            widget.insert(tk.END, line[4:] + "\n", "mono")
        elif not line:
            widget.insert(tk.END, "\n")
        else:
            _insert_markdown_inline(widget, line + "\n")
    widget.configure(state="disabled")


class Lab6App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ЛР6 — Численное решение задачи Коши")
        self.geometry("1220x820")
        self.minsize(1040, 700)

        self.result: SolutionResult | None = None
        self.figure: Any = None
        self.axes: Any = None
        self.figure_canvas: Any = None
        self.graph_message: ttk.Label | None = None
        self.method_tabs: dict[str, MethodTab] = {}

        self._build_ui()
        self._apply_equation_defaults()

    def _build_ui(self) -> None:
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        calc_tab = ttk.Frame(self.notebook)
        graph_tab = ttk.Frame(self.notebook)
        report_tab = ttk.Frame(self.notebook)
        self.notebook.add(calc_tab, text="Расчёт")
        self.notebook.add(graph_tab, text="График")
        self.notebook.add(report_tab, text="Отчёт")

        self._build_calc_tab(calc_tab)
        self._build_graph_tab(graph_tab)
        self._build_report_tab(report_tab)

        for key, title in (("euler", "Эйлер"), ("rk4", "РК4"), ("milne", "Милн")):
            method_tab = ttk.Frame(self.notebook)
            self.notebook.add(method_tab, text=title)
            self.method_tabs[key] = self._build_method_tab(method_tab, key, title)

    def _build_calc_tab(self, tab: ttk.Frame) -> None:
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(3, weight=1)

        input_frame = ttk.LabelFrame(tab, text="  Исходные данные  ")
        input_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        for column in range(8):
            input_frame.columnconfigure(column, weight=1)

        ttk.Label(input_frame, text="ОДУ:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        self.equation_var = tk.StringVar(value=EQUATIONS[0].key)
        self.equation_box = ttk.Combobox(
            input_frame,
            state="readonly",
            textvariable=self.equation_var,
            values=[equation.key for equation in EQUATIONS],
            width=8,
        )
        self.equation_box.grid(row=0, column=1, sticky="w", padx=6, pady=6)
        self.equation_box.bind("<<ComboboxSelected>>", lambda _event: self._apply_equation_defaults())

        self.equation_label = ttk.Label(
            input_frame,
            text="",
            font=("Helvetica", 11, "bold"),
            wraplength=860,
        )
        self.equation_label.grid(row=0, column=2, columnspan=6, sticky="w", padx=6, pady=6)

        self.input_vars: dict[str, tk.StringVar] = {
            "x0": tk.StringVar(),
            "y0": tk.StringVar(),
            "xn": tk.StringVar(),
            "h": tk.StringVar(),
            "epsilon": tk.StringVar(),
        }
        labels = [("x0", "x0"), ("y0", "y0"), ("xn", "xn"), ("h", "h"), ("epsilon", "epsilon")]
        for index, (key, label) in enumerate(labels):
            row = 1 if index < 4 else 2
            label_column = index * 2 if index < 4 else 0
            entry_column = index * 2 + 1 if index < 4 else 1
            ttk.Label(input_frame, text=f"{label}:").grid(
                row=row, column=label_column, sticky="e", padx=4, pady=6
            )
            ttk.Entry(input_frame, textvariable=self.input_vars[key], width=16).grid(
                row=row, column=entry_column, sticky="we", padx=4, pady=6
            )

        ttk.Label(
            input_frame,
            text="Можно вводить десятичные числа с точкой или запятой: 0.1 и 0,1 равнозначны.",
            foreground="#555555",
        ).grid(row=2, column=2, columnspan=4, sticky="w", padx=6, pady=6)

        ttk.Button(input_frame, text="Вернуть значения по умолчанию", command=self._apply_equation_defaults).grid(
            row=2, column=6, columnspan=2, sticky="we", padx=6, pady=6
        )

        self._build_output_panel(tab)

        button_frame = ttk.Frame(tab)
        button_frame.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 6))
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        ttk.Button(button_frame, text="Запустить расчёт", command=self.run_calculation).grid(
            row=0, column=0, sticky="we", padx=(0, 4)
        )
        ttk.Button(button_frame, text="Сохранить отчёт", command=self.save_report).grid(
            row=0, column=1, sticky="we", padx=(4, 0)
        )

        table_frame = ttk.LabelFrame(tab, text="  Таблица приближённых значений  ")
        table_frame.grid(row=3, column=0, sticky="nsew", padx=8, pady=6)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        columns = ("i", "x", "exact", "euler", "rk4", "milne", "err_e", "err_rk4", "err_m")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", height=14)
        headings = {
            "i": "i",
            "x": "x_i",
            "exact": "y точн.",
            "euler": "Эйлер",
            "rk4": "РК4",
            "milne": "Милн",
            "err_e": "|точн.-Э|",
            "err_rk4": "|точн.-РК4|",
            "err_m": "|точн.-М|",
        }
        widths = {
            "i": 44,
            "x": 95,
            "exact": 130,
            "euler": 130,
            "rk4": 130,
            "milne": 130,
            "err_e": 125,
            "err_rk4": 125,
            "err_m": 125,
        }
        for column in columns:
            self.table.heading(column, text=headings[column])
            self.table.column(column, width=widths[column], anchor="e", stretch=True)
        self.table.column("i", anchor="center", stretch=False)

        y_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        x_scroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.table.grid(row=0, column=0, sticky="nsew", padx=6, pady=(6, 0))
        y_scroll.grid(row=0, column=1, sticky="ns", pady=(6, 0))
        x_scroll.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 6))

        self.summary_text = tk.Text(tab, height=9, wrap="word", state="disabled")
        self.summary_text.grid(row=4, column=0, sticky="ew", padx=8, pady=(4, 8))

    def _build_output_panel(self, tab: ttk.Frame) -> None:
        output_frame = ttk.LabelFrame(tab, text="  Вывод результата  ")
        output_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 6))
        for column in range(5):
            output_frame.columnconfigure(column, weight=1 if column == 3 else 0)

        self.output_mode = tk.StringVar(value="screen")
        ttk.Radiobutton(
            output_frame, text="На экран", value="screen", variable=self.output_mode
        ).grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Radiobutton(
            output_frame, text="В файл", value="file", variable=self.output_mode
        ).grid(row=0, column=1, sticky="w", padx=6, pady=6)

        ttk.Label(output_frame, text="Файл отчёта:").grid(row=0, column=2, sticky="e", padx=6, pady=6)
        self.output_file = ttk.Entry(output_frame, width=46)
        self.output_file.grid(row=0, column=3, sticky="we", padx=6, pady=6)
        ttk.Button(output_frame, text="Обзор", command=self._pick_output_file).grid(
            row=0, column=4, sticky="e", padx=6, pady=6
        )

    def _build_graph_tab(self, tab: ttk.Frame) -> None:
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)
        if Figure is None or FigureCanvasTkAgg is None:
            self.graph_message = ttk.Label(
                tab,
                text="Для построения графиков нужен matplotlib. Установите его командой: pip install matplotlib",
                anchor="center",
                foreground="#666666",
            )
            self.graph_message.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
            return

        self.figure = Figure(figsize=(9, 5.4), dpi=100)
        self.axes = self.figure.add_subplot(111)
        self.figure_canvas = FigureCanvasTkAgg(self.figure, master=tab)
        self.figure_canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self._draw_empty_graph()

    def _build_report_tab(self, tab: ttk.Frame) -> None:
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)
        self.report_text = tk.Text(tab, wrap="word", state="disabled", font=("Courier", 11))
        self.report_text.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        scroll = ttk.Scrollbar(tab, orient="vertical", command=self.report_text.yview)
        scroll.grid(row=0, column=1, sticky="ns", padx=(0, 8), pady=8)
        self.report_text.configure(yscrollcommand=scroll.set)

    def _build_method_tab(self, tab: ttk.Frame, key: str, title: str) -> MethodTab:
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)

        stats_frame = ttk.LabelFrame(tab, text=f"  {title}: приближённая функция  ")
        stats_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        stats_frame.columnconfigure(0, weight=1)

        stats_text = tk.Text(stats_frame, height=7, wrap="word", state="disabled")
        stats_text.grid(row=0, column=0, sticky="ew", padx=6, pady=6)

        table_frame = ttk.LabelFrame(tab, text="  Таблица значений метода  ")
        table_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=4)
        table_frame.columnconfigure(0, weight=1)

        columns = ("i", "x", "exact", "method", "error")
        table = ttk.Treeview(table_frame, columns=columns, show="headings", height=8)
        headings = {
            "i": "i",
            "x": "x_i",
            "exact": "y точн.",
            "method": title,
            "error": "|точн.-метод|",
        }
        for column in columns:
            table.heading(column, text=headings[column])
            table.column(column, anchor="e", width=150, stretch=True)
        table.column("i", anchor="center", width=44, stretch=False)

        y_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=table.yview)
        table.configure(yscrollcommand=y_scroll.set)
        table.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        y_scroll.grid(row=0, column=1, sticky="ns", pady=6)

        graph_frame = ttk.LabelFrame(tab, text="  График метода  ")
        graph_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=(4, 8))
        graph_frame.columnconfigure(0, weight=1)
        graph_frame.rowconfigure(0, weight=1)

        graph_label = ttk.Label(
            graph_frame,
            text="После расчёта здесь появится график метода.",
            foreground="#666666",
            anchor="center",
        )
        graph_label.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

        figure = axes = canvas = None
        if Figure is not None and FigureCanvasTkAgg is not None:
            figure = Figure(figsize=(8.6, 3.8), dpi=100)
            axes = figure.add_subplot(111)
            canvas = FigureCanvasTkAgg(figure, master=graph_frame)
            canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
            canvas.get_tk_widget().grid_remove()
        else:
            graph_label.configure(text="Для построения графика нужен matplotlib.")

        method_tab = MethodTab(
            key=key,
            title=title,
            stats_text=stats_text,
            table=table,
            graph_label=graph_label,
            figure=figure,
            axes=axes,
            canvas=canvas,
        )
        self._reset_method_tab(method_tab)
        return method_tab

    def _apply_equation_defaults(self) -> None:
        equation = self._selected_equation()
        self.equation_label.configure(text=f"{equation.formula}. {equation.note}")
        self.input_vars["x0"].set(format(equation.default_x0, "f"))
        self.input_vars["y0"].set(format(equation.default_y0, "f"))
        self.input_vars["xn"].set(format(equation.default_xn, "f"))
        self.input_vars["h"].set(format(equation.default_h, "f"))
        self.input_vars["epsilon"].set(format(equation.default_epsilon, "f"))

    def _selected_equation(self):
        key = self.equation_var.get()
        for equation in EQUATIONS:
            if equation.key == key:
                return equation
        return EQUATIONS[0]

    def _read_decimal_inputs(self):
        raw_values = {key: var.get() for key, var in self.input_vars.items()}
        return parse_cauchy_input(raw_values)

    def _pick_output_file(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Сохранить отчёт",
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            self.output_file.delete(0, tk.END)
            self.output_file.insert(0, path)

    def _write_report_if_requested(self, report: str) -> None:
        if self.output_mode.get() != "file":
            return
        output_path = self.output_file.get().strip()
        if not output_path:
            raise ValueError("Для записи отчёта в файл необходимо указать путь к файлу.")
        try:
            Path(output_path).write_text(report + "\n", encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"Не удалось записать отчёт в файл: {exc}") from exc
        messagebox.showinfo("Готово", f"Отчёт сохранён:\n{output_path}")

    def run_calculation(self) -> None:
        try:
            values = self._read_decimal_inputs()
            result = solve_cauchy(
                self.equation_var.get(),
                values.x0,
                values.y0,
                values.xn,
                values.h,
                values.epsilon,
            )
        except (OdeInputError, ArithmeticError, ValueError) as exc:
            self._clear_result()
            messagebox.showerror("Ошибка входных данных", str(exc))
            return

        self.result = result
        self._fill_table(result)
        self._fill_summary(result)
        report = format_full_report(result)
        render_markdown(self.report_text, report)
        self._draw_graph(result)
        self._fill_method_tabs(result)
        try:
            self._write_report_if_requested(report)
        except ValueError as exc:
            messagebox.showerror("Ошибка записи", str(exc))
        self.notebook.select(0)

    def save_report(self) -> None:
        if self.result is None:
            messagebox.showinfo("Нет отчёта", "Сначала выполните расчёт.")
            return
        self._pick_output_file()
        output_path = self.output_file.get().strip()
        if not output_path:
            return
        try:
            Path(output_path).write_text(format_full_report(self.result) + "\n", encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Ошибка записи", f"Не удалось сохранить файл: {exc}")
            return
        messagebox.showinfo("Готово", f"Отчёт сохранён:\n{output_path}")

    def _clear_result(self) -> None:
        self.result = None
        for row in self.table.get_children():
            self.table.delete(row)
        for widget in (self.summary_text, self.report_text):
            widget.configure(state="normal")
            widget.delete("1.0", tk.END)
            widget.configure(state="disabled")
        self._draw_empty_graph()
        for method_tab in self.method_tabs.values():
            self._reset_method_tab(method_tab)

    def _fill_table(self, result: SolutionResult) -> None:
        for row in self.table.get_children():
            self.table.delete(row)
        for index, x_value in enumerate(result.grid.x_values):
            exact = result.exact_values[index]
            euler = result.euler.y_values[index]
            rk4 = result.rk4.y_values[index]
            milne = result.milne.y_values[index]
            self.table.insert(
                "",
                "end",
                values=(
                    index,
                    format_number(x_value),
                    format_number(exact),
                    format_number(euler),
                    format_number(rk4),
                    format_number(milne),
                    format_number(abs(exact - euler)),
                    format_number(abs(exact - rk4)),
                    format_number(abs(exact - milne)),
                ),
            )

    def _fill_summary(self, result: SolutionResult) -> None:
        lines = [
            "# Краткий итог",
            f"**Уравнение:** {result.equation.formula}",
            f"**Узлов сетки:** {len(result.grid.x_values)}",
            f"**Последний узел:** {format_number(result.grid.actual_xn)}",
            f"**Эйлер, правило Рунге:** {format_number(result.euler_runge_error)}",
            f"**РК4, правило Рунге:** {format_number(result.rk4_runge_error)}",
            f"**Милн, max |yточн - yi|:** {format_number(result.milne_exact_error)}",
        ]
        if result.warnings:
            lines.append("")
            lines.append("**Предупреждения:**")
            for warning in result.warnings:
                lines.append(f"> {warning}")
        render_markdown(self.summary_text, "\n".join(lines))

    def _fill_method_tabs(self, result: SolutionResult) -> None:
        for method_tab in self.method_tabs.values():
            self._populate_method_tab(method_tab, result)

    def _populate_method_tab(self, method_tab: MethodTab, result: SolutionResult) -> None:
        series = self._method_series(result, method_tab.key)
        max_error = self._method_exact_error(result, method_tab.key)
        lines = [
            f"# {series.name}",
            f"**Уравнение:** {result.equation.formula}",
            f"**Узлов сетки:** {len(result.grid.x_values)}",
            f"**Максимальная ошибка относительно точного решения:** {format_number(max_error)}",
        ]
        if method_tab.key == "euler":
            lines.append(f"**Оценка по правилу Рунге, p = 1:** {format_number(result.euler_runge_error)}")
        elif method_tab.key == "rk4":
            lines.append(f"**Оценка по правилу Рунге, p = 4:** {format_number(result.rk4_runge_error)}")
        else:
            max_iteration = max(series.milne_iterations) if series.milne_iterations else 0
            lines.append("**Оценка точности:** max |yточн - yi|")
            lines.append(f"**Максимум итераций корректора по узлам:** {max_iteration}")
            if series.warnings:
                lines.append("")
                lines.append("**Предупреждения метода:**")
                lines.extend(f"> {warning}" for warning in series.warnings)
        render_markdown(method_tab.stats_text, "\n".join(lines))

        for row in method_tab.table.get_children():
            method_tab.table.delete(row)
        for index, x_value in enumerate(series.x_values):
            exact = result.exact_values[index]
            method_value = series.y_values[index]
            method_tab.table.insert(
                "",
                "end",
                values=(
                    index,
                    format_number(x_value),
                    format_number(exact),
                    format_number(method_value),
                    format_number(abs(exact - method_value)),
                ),
            )
        self._draw_method_graph(method_tab, result)

    def _reset_method_tab(self, method_tab: MethodTab) -> None:
        render_markdown(method_tab.stats_text, "После расчёта здесь появится статистика метода.")
        for row in method_tab.table.get_children():
            method_tab.table.delete(row)
        method_tab.graph_label.configure(text="После расчёта здесь появится график метода.")
        method_tab.graph_label.grid()
        if method_tab.canvas is not None:
            method_tab.canvas.get_tk_widget().grid_remove()

    def _method_series(self, result: SolutionResult, key: str):
        if key == "euler":
            return result.euler
        if key == "rk4":
            return result.rk4
        return result.milne

    def _method_exact_error(self, result: SolutionResult, key: str):
        if key == "euler":
            return result.euler_exact_error
        if key == "rk4":
            return result.rk4_exact_error
        return result.milne_exact_error

    def _draw_method_graph(self, method_tab: MethodTab, result: SolutionResult) -> None:
        if method_tab.figure is None or method_tab.axes is None or method_tab.canvas is None:
            return

        series = self._method_series(result, method_tab.key)
        x_values = [float(value) for value in series.x_values]
        exact_y = [float(value) for value in result.exact_values]
        method_y = [float(value) for value in series.y_values]
        all_y = exact_y + method_y

        x_min, x_max = min(x_values), max(x_values)
        y_min, y_max = min(all_y), max(all_y)
        y_span = (y_max - y_min) or 1.0

        method_tab.graph_label.grid_remove()
        method_tab.canvas.get_tk_widget().grid()

        axes = method_tab.axes
        axes.clear()
        axes.set_facecolor("white")
        axes.grid(True, color="#e6e6e6", linewidth=0.9)
        axes.plot(x_values, exact_y, color=COLORS["exact"], linewidth=2.4, label="Точное решение")
        axes.plot(
            x_values,
            method_y,
            color=COLORS[method_tab.key],
            marker="o",
            markersize=3,
            label=series.name,
        )
        axes.set_xlim(x_min, x_max)
        axes.set_ylim(y_min - 0.12 * y_span, y_max + 0.12 * y_span)
        if y_min <= 0 <= y_max:
            axes.axhline(0, color="#555555", linewidth=1)
        if x_min <= 0 <= x_max:
            axes.axvline(0, color="#555555", linewidth=1)
        axes.set_xlabel("x")
        axes.set_ylabel("y")
        axes.set_title(f"{series.name}: приближённая функция")
        axes.legend(loc="best")
        method_tab.figure.tight_layout()
        method_tab.canvas.draw_idle()

    def _draw_empty_graph(self) -> None:
        if self.figure is None or self.axes is None or self.figure_canvas is None:
            return
        self.axes.clear()
        self.axes.set_axis_off()
        self.axes.text(
            0.5,
            0.5,
            "После расчёта здесь появится график точного и численных решений.",
            ha="center",
            va="center",
            transform=self.axes.transAxes,
            color="#666666",
            fontsize=12,
        )
        self.figure.tight_layout()
        self.figure_canvas.draw_idle()

    def _draw_graph(self, result: SolutionResult) -> None:
        if self.figure is None or self.axes is None or self.figure_canvas is None:
            return
        axes = self.axes
        axes.clear()
        axes.set_facecolor("white")
        axes.grid(True, color="#e6e6e6", linewidth=0.9)

        x_values = [float(value) for value in result.grid.x_values]
        exact_y = [float(value) for value in result.exact_values]
        euler_y = [float(value) for value in result.euler.y_values]
        rk4_y = [float(value) for value in result.rk4.y_values]
        milne_y = [float(value) for value in result.milne.y_values]

        all_y = exact_y + euler_y + rk4_y + milne_y
        x_min, x_max = min(x_values), max(x_values)
        y_min, y_max = min(all_y), max(all_y)
        y_span = (y_max - y_min) or 1.0

        axes.plot(x_values, exact_y, color=COLORS["exact"], linewidth=2.5, label="Точное решение")
        axes.plot(x_values, euler_y, color=COLORS["euler"], marker="o", markersize=3, label="Метод Эйлера")
        axes.plot(x_values, rk4_y, color=COLORS["rk4"], marker="s", markersize=3, label="Рунге-Кутта 4")
        axes.plot(x_values, milne_y, color=COLORS["milne"], marker="^", markersize=3, label="Метод Милна")

        axes.set_xlim(x_min, x_max)
        axes.set_ylim(y_min - 0.12 * y_span, y_max + 0.12 * y_span)
        if y_min <= 0 <= y_max:
            axes.axhline(0, color="#555555", linewidth=1)
        if x_min <= 0 <= x_max:
            axes.axvline(0, color="#555555", linewidth=1)
        axes.set_xlabel("x")
        axes.set_ylabel("y")
        axes.set_title("Решение задачи Коши численными методами")
        axes.legend(loc="best")
        self.figure.tight_layout()
        self.figure_canvas.draw_idle()


def main() -> None:
    app = Lab6App()
    app.mainloop()


if __name__ == "__main__":
    main()
