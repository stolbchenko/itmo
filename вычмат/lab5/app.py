from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, DecimalException
import html.parser
from pathlib import Path
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any

try:
    import markdown as _markdown_lib
    _HAS_MARKDOWN = True
except ImportError:
    _HAS_MARKDOWN = False

try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
except ModuleNotFoundError:
    FigureCanvasTkAgg = None
    Figure = None

from interpolation import (
    FUNCTIONS,
    InterpolationAnalysis,
    InterpolationError,
    analyze_interpolation,
    format_number,
    format_report,
    gauss_first_value,
    gauss_second_value,
    generate_function_points,
    get_function,
    lagrange_value,
    newton_backward_value,
    newton_forward_value,
    parse_decimal,
    parse_points,
)


def _is_dark(widget: tk.Text) -> bool:
    try:
        r, g, b = widget.winfo_rgb(widget.cget("background"))
        return (0.299 * r + 0.587 * g + 0.114 * b) / 65535 < 0.5
    except Exception:
        return False


def _md_setup_tags(widget: tk.Text) -> None:
    dark = _is_dark(widget)
    if dark:
        widget.tag_configure("md_h1", font=("Helvetica", 15, "bold"), spacing1=6, spacing3=4, foreground="#ffffff")
        widget.tag_configure("md_h2", font=("Helvetica", 13, "bold"), spacing1=4, spacing3=2, foreground="#e0e0e0")
        widget.tag_configure("md_bold", font=("Courier", 11, "bold"), foreground="#ffffff")
        widget.tag_configure("md_italic", font=("Courier", 11, "italic"), foreground="#cccccc")
        widget.tag_configure("md_code", font=("Courier", 11), foreground="#e5c07b")
        widget.tag_configure("md_rule", foreground="#404040")
        widget.tag_configure("md_quote", font=("Courier", 11, "italic"), lmargin1=16, lmargin2=16, foreground="#56b6c2")
        widget.tag_configure("md_bullet", foreground="#888888")
        widget.tag_configure("md_mono", font=("Courier", 10), lmargin1=8, lmargin2=8, background="#2a2a2a", foreground="#abb2bf")
    else:
        widget.tag_configure("md_h1", font=("Helvetica", 15, "bold"), spacing1=6, spacing3=4, foreground="#1a1a1a")
        widget.tag_configure("md_h2", font=("Helvetica", 13, "bold"), spacing1=4, spacing3=2, foreground="#2d2d2d")
        widget.tag_configure("md_bold", font=("Courier", 11, "bold"), foreground="#1a1a1a")
        widget.tag_configure("md_italic", font=("Courier", 11, "italic"))
        widget.tag_configure("md_code", font=("Courier", 11), background="#f9f2f4", foreground="#c7254e")
        widget.tag_configure("md_rule", foreground="#d0d0d0")
        widget.tag_configure("md_quote", font=("Courier", 11, "italic"), lmargin1=16, lmargin2=16, foreground="#2a9d8f")
        widget.tag_configure("md_bullet", foreground="#555555")
        widget.tag_configure("md_mono", font=("Courier", 10), lmargin1=8, lmargin2=8, background="#f4f4f4", foreground="#333333")


class _HtmlToTk(html.parser.HTMLParser):
    _TAG_TO_TK = {
        "h1": "md_h1",
        "h2": "md_h2",
        "h3": "md_h2",
        "strong": "md_bold",
        "b": "md_bold",
        "em": "md_italic",
        "i": "md_italic",
        "blockquote": "md_quote",
    }
    _BLOCK_NL = frozenset({"h1", "h2", "h3", "p", "li", "blockquote", "pre", "div"})
    _LIST_TAGS = frozenset({"ul", "ol"})

    def __init__(self, widget: tk.Text) -> None:
        super().__init__(convert_charrefs=True)
        self.w = widget
        self._stack: list[str] = []
        self._in_pre = False
        self._li_depth = 0

    def _tk_tags(self) -> tuple[str, ...]:
        seen: set[str] = set()
        result: list[str] = []
        for tag in self._stack:
            tk_tag = (
                "md_mono"
                if tag == "code" and self._in_pre
                else "md_code"
                if tag == "code"
                else self._TAG_TO_TK.get(tag)
            )
            if tk_tag and tk_tag not in seen:
                seen.add(tk_tag)
                result.append(tk_tag)
        return tuple(result)

    def handle_starttag(self, tag: str, attrs: list) -> None:
        self._stack.append(tag)
        if tag == "pre":
            self._in_pre = True
        elif tag in self._LIST_TAGS:
            self._li_depth += 1
        elif tag == "li":
            indent = "  " * (self._li_depth - 1)
            self.w.insert(tk.END, f"{indent}  • ", ("md_bullet",))
        elif tag == "hr":
            self.w.insert(tk.END, "─" * 55 + "\n", ("md_rule",))
        elif tag == "br":
            self.w.insert(tk.END, "\n")

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index] == tag:
                self._stack.pop(index)
                break
        if tag == "pre":
            self._in_pre = False
            self.w.insert(tk.END, "\n")
        elif tag in self._BLOCK_NL:
            self.w.insert(tk.END, "\n")
        elif tag in self._LIST_TAGS:
            self._li_depth = max(0, self._li_depth - 1)
            if self._li_depth == 0:
                self.w.insert(tk.END, "\n")

    def handle_data(self, data: str) -> None:
        if not data:
            return
        if self._in_pre:
            self.w.insert(tk.END, data, ("md_mono",))
        else:
            if not data.strip():
                return
            self.w.insert(tk.END, data, self._tk_tags())


_MD_INLINE_RE = re.compile(r"\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`", re.DOTALL)


def _md_strip_inline(text: str) -> str:
    return _MD_INLINE_RE.sub(lambda match: match.group(1) or match.group(2) or match.group(3) or "", text)


def _md_render_inline(widget: tk.Text, text: str, extra: tuple[str, ...] = ()) -> None:
    pos = 0
    for match in _MD_INLINE_RE.finditer(text):
        if match.start() > pos:
            widget.insert(tk.END, text[pos:match.start()], extra)
        if match.group(1) is not None:
            widget.insert(tk.END, match.group(1), extra + ("md_bold",))
        elif match.group(2) is not None:
            widget.insert(tk.END, match.group(2), extra + ("md_italic",))
        elif match.group(3) is not None:
            widget.insert(tk.END, match.group(3), extra + ("md_code",))
        pos = match.end()
    if pos < len(text):
        widget.insert(tk.END, text[pos:], extra)


def _render_md_regex(widget: tk.Text, text: str) -> None:
    in_code = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code or line.startswith("    "):
            widget.insert(tk.END, line.lstrip() + "\n", "md_mono")
            continue
        if re.fullmatch(r"\s*---+\s*", line):
            widget.insert(tk.END, "─" * 55 + "\n", "md_rule")
            continue
        match = re.match(r"^## (.+)", line)
        if match:
            widget.insert(tk.END, _md_strip_inline(match.group(1)) + "\n", "md_h2")
            continue
        match = re.match(r"^# (.+)", line)
        if match:
            widget.insert(tk.END, _md_strip_inline(match.group(1)) + "\n", "md_h1")
            continue
        match = re.match(r"^> ?(.*)", line)
        if match:
            _md_render_inline(widget, match.group(1) + "\n", ("md_quote",))
            continue
        match = re.match(r"^[-*] (.+)", line)
        if match:
            widget.insert(tk.END, "  • ", "md_bullet")
            _md_render_inline(widget, match.group(1) + "\n")
            continue
        if not line.strip():
            widget.insert(tk.END, "\n")
            continue
        _md_render_inline(widget, line + "\n")


def render_md(widget: tk.Text, text: str) -> None:
    _md_setup_tags(widget)
    widget.configure(state="normal")
    widget.delete("1.0", tk.END)
    if _HAS_MARKDOWN:
        html_str = _markdown_lib.markdown(text, extensions=["nl2br", "sane_lists"])
        renderer = _HtmlToTk(widget)
        renderer.feed(html_str)
    else:
        _render_md_regex(widget, text)
    widget.configure(state="disabled")


COLORS = {
    "nodes": "#111111",
    "source": "#2a9d8f",
    "lagrange": "#6a4c93",
    "newton_first": "#00798c",
    "newton_second": "#30638e",
    "gauss_first": "#d1495b",
    "gauss_second": "#edae49",
}


@dataclass(frozen=True)
class MethodConfig:
    result_name: str
    tab_label: str
    graph_label: str
    color_key: str
    linestyle: Any
    linewidth: float


@dataclass
class MethodTab:
    config: MethodConfig
    report_text: tk.Text
    tree: ttk.Treeview
    graph_label: ttk.Label
    figure: Any = None
    axes: Any = None
    canvas: Any = None


METHOD_CONFIGS = [
    MethodConfig("Многочлен Лагранжа", "Лагранж", "Лагранж", "lagrange", "--", 1.8),
    MethodConfig("Ньютон, первая формула", "Ньютон 1", "Ньютон 1", "newton_first", "-", 2.0),
    MethodConfig("Ньютон, вторая формула", "Ньютон 2", "Ньютон 2", "newton_second", ":", 2.4),
    MethodConfig("Гаусс, первая формула", "Гаусс 1", "Гаусс 1", "gauss_first", "-.", 2.0),
    MethodConfig("Гаусс, вторая формула", "Гаусс 2", "Гаусс 2", "gauss_second", (0, (5, 1)), 2.0),
]


class Lab5App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ЛР5 — Интерполяция функций")
        self.geometry("1180x860")

        self.points: list[tuple[Decimal, Decimal]] = []
        self.analysis: InterpolationAnalysis | None = None

        self.figure: Any = None
        self.axes: Any = None
        self.figure_canvas: Any = None
        self.graph_message_label: ttk.Label | None = None
        self.method_tabs: list[MethodTab] = []

        self._build_ui()
        self._fill_demo_data()
        self._toggle_input_mode()

    def _build_ui(self) -> None:
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        calc_tab = ttk.Frame(self.notebook)
        graph_tab = ttk.Frame(self.notebook)
        self.notebook.add(calc_tab, text="Интерполяция")
        self.notebook.add(graph_tab, text="Все графики")

        self._build_calc_tab(calc_tab)
        self._build_graph_tab(graph_tab)

        for config in METHOD_CONFIGS:
            method_tab = ttk.Frame(self.notebook)
            self.notebook.add(method_tab, text=config.tab_label)
            self.method_tabs.append(self._build_method_tab(method_tab, config))

    def _build_calc_tab(self, tab: ttk.Frame) -> None:
        frame = ttk.Frame(tab)
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        for column in range(4):
            frame.columnconfigure(column, weight=1)

        ttk.Label(frame, text="Источник входных данных:").grid(
            row=0, column=0, sticky="w", padx=6, pady=4
        )
        self.input_mode = tk.StringVar(value="manual")
        self.input_mode.trace_add("write", lambda *_: self._toggle_input_mode())
        ttk.Radiobutton(
            frame, text="С клавиатуры", value="manual", variable=self.input_mode
        ).grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(
            frame, text="Из файла", value="file", variable=self.input_mode
        ).grid(row=0, column=2, sticky="w")
        ttk.Radiobutton(
            frame, text="По функции", value="function", variable=self.input_mode
        ).grid(row=0, column=3, sticky="w")

        ttk.Separator(frame, orient="horizontal").grid(
            row=1, column=0, columnspan=4, sticky="we", pady=6
        )

        self.manual_frame = self._build_manual_panel(frame)
        self.file_frame = self._build_file_panel(frame)
        self.function_frame = self._build_function_panel(frame)

        target_frame = ttk.LabelFrame(frame, text="  Точка интерполяции  ")
        target_frame.grid(row=3, column=0, columnspan=4, sticky="ew", padx=6, pady=6)
        target_frame.columnconfigure(1, weight=1)
        ttk.Label(target_frame, text="x =").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        self.target_x = ttk.Entry(target_frame, width=18)
        self.target_x.grid(row=0, column=1, sticky="w", padx=6, pady=6)

        self.plot_flag = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            target_frame, text="Построить график", variable=self.plot_flag
        ).grid(row=0, column=2, sticky="w", padx=6, pady=6)

        self.output_mode, self.output_file = self._build_output_panel(frame, row_start=4)

        ttk.Button(frame, text="Запустить расчёт", command=self.run_analysis).grid(
            row=6, column=0, columnspan=4, sticky="we", padx=6, pady=8
        )

        ttk.Label(frame, text="Таблица конечных разностей:").grid(
            row=7, column=0, columnspan=4, sticky="w", padx=6, pady=(4, 0)
        )
        self.diff_tree = ttk.Treeview(frame, show="headings", height=8)
        self.diff_tree.grid(row=8, column=0, columnspan=4, sticky="nsew", padx=6)
        diff_vsb = ttk.Scrollbar(frame, orient="vertical", command=self.diff_tree.yview)
        diff_vsb.grid(row=8, column=4, sticky="ns")
        diff_hsb = ttk.Scrollbar(frame, orient="horizontal", command=self.diff_tree.xview)
        diff_hsb.grid(row=9, column=0, columnspan=4, sticky="we", padx=6)
        self.diff_tree.configure(yscrollcommand=diff_vsb.set, xscrollcommand=diff_hsb.set)

        ttk.Label(frame, text="Отчёт:").grid(
            row=10, column=0, columnspan=4, sticky="w", padx=6, pady=(8, 0)
        )
        self.report_text = tk.Text(frame, height=16, wrap="word", state="disabled", font=("Courier", 11))
        self.report_text.grid(row=11, column=0, columnspan=4, sticky="nsew", padx=6, pady=(0, 6))
        frame.rowconfigure(11, weight=1)

    def _build_manual_panel(self, parent: ttk.Frame) -> ttk.Frame:
        panel = ttk.Frame(parent)
        panel.grid(row=2, column=0, columnspan=4, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)
        ttk.Label(panel, text="Точки (формат: x y, разделители: пробел, табуляция или ';'):").grid(
            row=0, column=0, sticky="w", padx=6, pady=4
        )
        self.input_text = tk.Text(panel, height=8, wrap="none", font=("Courier", 11))
        self.input_text.grid(row=1, column=0, sticky="nsew", padx=6)
        y_scroll = ttk.Scrollbar(panel, orient="vertical", command=self.input_text.yview)
        y_scroll.grid(row=1, column=1, sticky="ns")
        x_scroll = ttk.Scrollbar(panel, orient="horizontal", command=self.input_text.xview)
        x_scroll.grid(row=2, column=0, sticky="we", padx=6)
        self.input_text.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        ttk.Label(panel, text="Допустимо от 2 до 20 узлов. Для Ньютона и Гаусса нужен постоянный шаг.").grid(
            row=3, column=0, sticky="w", padx=6, pady=4
        )
        return panel

    def _build_file_panel(self, parent: ttk.Frame) -> ttk.Frame:
        panel = ttk.Frame(parent)
        panel.columnconfigure(1, weight=1)
        ttk.Label(panel, text="Файл входных данных:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.input_file = ttk.Entry(panel, width=42)
        self.input_file.grid(row=0, column=1, sticky="we", padx=6, pady=4)
        ttk.Button(panel, text="Обзор", command=lambda: self._pick_input_file(self.input_file)).grid(
            row=0, column=2, padx=6, pady=4
        )
        ttk.Label(panel, text="Формат файла такой же: пары `x y`.").grid(
            row=1, column=0, columnspan=3, sticky="w", padx=6, pady=4
        )
        return panel

    def _build_function_panel(self, parent: ttk.Frame) -> ttk.Frame:
        panel = ttk.LabelFrame(parent, text="  Формирование таблицы по функции  ")
        for column in range(6):
            panel.columnconfigure(column, weight=1)

        ttk.Label(panel, text="Функция:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.function_name = tk.StringVar(value=FUNCTIONS[0].name)
        self.function_combo = ttk.Combobox(
            panel,
            textvariable=self.function_name,
            values=[function.name for function in FUNCTIONS],
            state="readonly",
            width=18,
        )
        self.function_combo.grid(row=0, column=1, sticky="we", padx=6, pady=4)

        ttk.Label(panel, text="a =").grid(row=0, column=2, sticky="e", padx=6, pady=4)
        self.interval_start = ttk.Entry(panel, width=12)
        self.interval_start.grid(row=0, column=3, sticky="we", padx=6, pady=4)
        ttk.Label(panel, text="b =").grid(row=0, column=4, sticky="e", padx=6, pady=4)
        self.interval_end = ttk.Entry(panel, width=12)
        self.interval_end.grid(row=0, column=5, sticky="we", padx=6, pady=4)

        ttk.Label(panel, text="Количество точек:").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        self.point_count = ttk.Spinbox(panel, from_=2, to=20, width=8)
        self.point_count.grid(row=1, column=1, sticky="w", padx=6, pady=4)
        ttk.Label(panel, text="Узлы строятся равномерно на выбранном интервале.").grid(
            row=1, column=2, columnspan=4, sticky="w", padx=6, pady=4
        )
        return panel

    def _build_output_panel(self, parent: ttk.Frame, row_start: int) -> tuple[tk.StringVar, ttk.Entry]:
        ttk.Label(parent, text="Вывод результата:").grid(row=row_start, column=0, sticky="w", padx=6, pady=4)
        output_mode = tk.StringVar(value="screen")
        ttk.Radiobutton(parent, text="На экран", value="screen", variable=output_mode).grid(
            row=row_start, column=1, sticky="w"
        )
        ttk.Radiobutton(parent, text="В файл", value="file", variable=output_mode).grid(
            row=row_start, column=2, sticky="w"
        )

        ttk.Label(parent, text="Файл вывода:").grid(row=row_start + 1, column=0, sticky="w", padx=6, pady=4)
        output_entry = ttk.Entry(parent, width=42)
        output_entry.grid(row=row_start + 1, column=1, columnspan=2, sticky="we", padx=6, pady=4)
        ttk.Button(parent, text="Обзор", command=lambda: self._pick_output_file(output_entry)).grid(
            row=row_start + 1, column=3, padx=6, pady=4
        )
        return output_mode, output_entry

    def _build_graph_tab(self, tab: ttk.Frame) -> None:
        frame = ttk.Frame(tab)
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        ttk.Label(
            frame,
            text="Все графики исходной функции, узлов и интерполяционных многочленов",
        ).grid(row=0, column=0, sticky="w", padx=6, pady=(0, 6))

        graph_area = ttk.Frame(frame)
        graph_area.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        graph_area.columnconfigure(0, weight=1)
        graph_area.rowconfigure(0, weight=1)

        if Figure is None or FigureCanvasTkAgg is None:
            self.graph_message_label = ttk.Label(
                graph_area,
                text="Для построения графика нужен пакет matplotlib.\nУстановите его командой: pip install matplotlib",
                justify="center",
                foreground="#666666",
            )
            self.graph_message_label.grid(row=0, column=0, sticky="nsew")
        else:
            self.figure = Figure(figsize=(9.2, 5.8), dpi=100)
            self.axes = self.figure.add_subplot(111)
            self.figure_canvas = FigureCanvasTkAgg(self.figure, master=graph_area)
            self.figure_canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
            self._show_empty_graph_message()

    def _build_method_tab(self, tab: ttk.Frame, config: MethodConfig) -> MethodTab:
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)

        report_frame = ttk.LabelFrame(tab, text=f"  {config.graph_label}: результат  ")
        report_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        report_frame.columnconfigure(0, weight=1)

        report_text = tk.Text(
            report_frame,
            height=8,
            wrap="word",
            state="disabled",
            font=("Courier", 11),
        )
        report_text.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        render_md(report_text, "После расчёта здесь появится результат метода.")

        table_frame = ttk.LabelFrame(tab, text="  Узлы интерполяции  ")
        table_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=4)
        table_frame.columnconfigure(0, weight=1)
        columns = ("i", "xi", "yi")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=6)
        for column, heading in zip(columns, ("i", "x_i", "y_i")):
            tree.heading(column, text=heading)
        tree.column("i", anchor="center", width=44, stretch=False)
        tree.column("xi", anchor="e", width=180)
        tree.column("yi", anchor="e", width=220)
        y_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=y_scroll.set)
        tree.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        y_scroll.grid(row=0, column=1, sticky="ns", pady=6)

        graph_frame = ttk.LabelFrame(tab, text=f"  График: {config.graph_label}  ")
        graph_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=(4, 8))
        graph_frame.columnconfigure(0, weight=1)
        graph_frame.rowconfigure(0, weight=1)

        graph_label = ttk.Label(
            graph_frame,
            text="После расчёта здесь появится график метода.",
            foreground="#666666",
            font=("Helvetica", 11),
            anchor="center",
        )
        graph_label.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

        fig = ax = canvas = None
        if Figure is not None and FigureCanvasTkAgg is not None:
            fig = Figure(figsize=(8.6, 4.2), dpi=100)
            ax = fig.add_subplot(111)
            canvas = FigureCanvasTkAgg(fig, master=graph_frame)
            canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
            canvas.get_tk_widget().grid_remove()
        else:
            graph_label.configure(text="Для построения графика нужен пакет matplotlib.")

        return MethodTab(
            config=config,
            report_text=report_text,
            tree=tree,
            graph_label=graph_label,
            figure=fig,
            axes=ax,
            canvas=canvas,
        )

    def _fill_demo_data(self) -> None:
        demo = "\n".join(["0 1", "1 3", "2 7", "3 13", "4 21", "5 31"])
        self.input_text.delete("1.0", tk.END)
        self.input_text.insert("1.0", demo)
        self.target_x.delete(0, tk.END)
        self.target_x.insert(0, "2.5")
        self.interval_start.insert(0, "0")
        self.interval_end.insert(0, "3.14159")
        self.point_count.insert(0, "8")

    def _toggle_input_mode(self) -> None:
        for panel in (self.manual_frame, self.file_frame, self.function_frame):
            panel.grid_remove()
        mode = self.input_mode.get()
        if mode == "manual":
            self.manual_frame.grid(row=2, column=0, columnspan=4, sticky="nsew")
        elif mode == "file":
            self.file_frame.grid(row=2, column=0, columnspan=4, sticky="ew")
        else:
            self.function_frame.grid(row=2, column=0, columnspan=4, sticky="ew", padx=6, pady=4)

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

    def _read_points(self) -> tuple[list[tuple[Decimal, Decimal]], str | None]:
        mode = self.input_mode.get()
        if mode == "manual":
            return parse_points(self.input_text.get("1.0", tk.END)), None
        if mode == "file":
            path = self.input_file.get().strip()
            if not path:
                raise InterpolationError("Для чтения входных данных из файла необходимо указать путь.")
            try:
                return parse_points(Path(path).read_text(encoding="utf-8")), None
            except OSError as exc:
                raise InterpolationError(f"Не удалось прочитать входной файл: {exc}") from exc

        start = parse_decimal(self.interval_start.get(), "a")
        end = parse_decimal(self.interval_end.get(), "b")
        try:
            count = int(self.point_count.get())
        except ValueError as exc:
            raise InterpolationError("Количество точек должно быть целым числом.") from exc
        return generate_function_points(self.function_name.get(), start, end, count), self.function_name.get()

    def run_analysis(self) -> None:
        try:
            points, source_function_name = self._read_points()
            x_value = parse_decimal(self.target_x.get(), "x")
            analysis = analyze_interpolation(points, x_value, source_function_name)
            report = format_report(analysis)
        except InterpolationError as exc:
            self._clear_results()
            messagebox.showerror("Ошибка", str(exc))
            return

        self.points = analysis.points
        self.analysis = analysis
        self._fill_difference_table(analysis)
        self._show_report(report)
        self._populate_method_tabs(analysis)
        if self.plot_flag.get():
            self.draw_graph()
            self.notebook.select(1)
        else:
            self._show_empty_graph_message("Построение графика отключено.")

        if self.output_mode.get() == "file":
            output_path = self.output_file.get().strip()
            if not output_path:
                messagebox.showerror("Ошибка записи", "Для записи результата укажите путь к файлу.")
                return
            try:
                Path(output_path).write_text(report + "\n", encoding="utf-8")
            except OSError as exc:
                messagebox.showerror("Ошибка записи", f"Не удалось записать результат в файл: {exc}")
                return
            messagebox.showinfo("Сохранено", f"Результат успешно сохранён в файл:\n{output_path}")

    def _clear_results(self) -> None:
        self.points = []
        self.analysis = None
        self._set_tree_columns([])
        self._show_report("")
        self._show_empty_graph_message()
        for method_tab in self.method_tabs:
            self._reset_method_tab(method_tab)

    def _fill_difference_table(self, analysis: InterpolationAnalysis) -> None:
        count = len(analysis.points)
        columns = ["i", "x_i", "y_i"] + [f"d{order}" for order in range(1, count)]
        labels = ["i", "x_i", "y_i"] + [f"Δ^{order} y_i" for order in range(1, count)]
        self._set_tree_columns(columns)
        for col, label in zip(columns, labels):
            self.diff_tree.heading(col, text=label)
            width = 52 if col == "i" else 120
            self.diff_tree.column(col, width=width, minwidth=width, anchor="e", stretch=False)
        self.diff_tree.column("i", anchor="center")

        for index, (x_value, _) in enumerate(analysis.points):
            values = [index, format_number(x_value), format_number(analysis.finite_differences[0][index])]
            for order in range(1, count):
                if index < len(analysis.finite_differences[order]):
                    values.append(format_number(analysis.finite_differences[order][index]))
                else:
                    values.append("")
            self.diff_tree.insert("", "end", values=values)

    def _set_tree_columns(self, columns: list[str]) -> None:
        for row in self.diff_tree.get_children():
            self.diff_tree.delete(row)
        self.diff_tree["columns"] = columns

    def _show_report(self, text: str) -> None:
        render_md(self.report_text, text)

    def _populate_method_tabs(self, analysis: InterpolationAnalysis) -> None:
        results_by_name = {result.name: result for result in analysis.results}
        for method_tab in self.method_tabs:
            result = results_by_name.get(method_tab.config.result_name)
            if result is None:
                self._show_unavailable_method(method_tab, analysis)
                continue
            self._populate_method_tab(method_tab, analysis, result)

    def _populate_method_tab(
        self,
        method_tab: MethodTab,
        analysis: InterpolationAnalysis,
        result: Any,
    ) -> None:
        error_line = ""
        if analysis.exact_value is not None:
            error_line = (
                f"\n**Абсолютная ошибка относительно исходной функции:** "
                f"`{format_number(abs(result.value - analysis.exact_value))}`"
            )
        extrapolation = (
            "\n> **Предупреждение:** точка находится вне интервала узлов, это экстраполяция."
            if analysis.is_extrapolation
            else ""
        )
        report = (
            f"# {result.name}\n\n"
            f"**Формула:** `{result.formula}`\n"
            f"**Точка вычисления:** `x = {format_number(analysis.x_value)}`\n"
            f"**Значение метода:** `{format_number(result.value)}`"
            f"{error_line}"
            f"{extrapolation}\n\n"
            "## Краткий анализ\n"
            "Интерполяционный многочлен проходит через все заданные узлы. "
            "Сравнивайте график метода с общей вкладкой, чтобы увидеть, насколько линии совпадают на выбранной сетке."
        )
        render_md(method_tab.report_text, report)

        for row in method_tab.tree.get_children():
            method_tab.tree.delete(row)
        for index, (x_value, y_value) in enumerate(analysis.points):
            method_tab.tree.insert(
                "",
                "end",
                values=(index, format_number(x_value), format_number(y_value)),
            )

        self._draw_method_graph(method_tab)

    def _show_unavailable_method(
        self,
        method_tab: MethodTab,
        analysis: InterpolationAnalysis,
    ) -> None:
        issue_text = "\n".join(f"- {issue}" for issue in analysis.issues)
        if not issue_text:
            issue_text = "- Метод не был построен для текущего набора данных."
        render_md(
            method_tab.report_text,
            f"# {method_tab.config.result_name}\n\n"
            "Метод недоступен для текущих данных.\n\n"
            "## Причины\n"
            f"{issue_text}",
        )
        for row in method_tab.tree.get_children():
            method_tab.tree.delete(row)
        method_tab.graph_label.configure(text="Метод недоступен для текущих данных.")
        method_tab.graph_label.grid()
        if method_tab.canvas is not None:
            method_tab.canvas.get_tk_widget().grid_remove()

    def _reset_method_tab(self, method_tab: MethodTab) -> None:
        render_md(method_tab.report_text, "После расчёта здесь появится результат метода.")
        for row in method_tab.tree.get_children():
            method_tab.tree.delete(row)
        method_tab.graph_label.configure(text="После расчёта здесь появится график метода.")
        method_tab.graph_label.grid()
        if method_tab.canvas is not None:
            method_tab.canvas.get_tk_widget().grid_remove()

    def draw_graph(self) -> None:
        if self.figure_canvas is None or self.figure is None or self.axes is None:
            if self.graph_message_label is not None:
                self.graph_message_label.configure(
                    text="Для построения графика нужен пакет matplotlib.\nУстановите его командой: pip install matplotlib"
                )
            return
        if self.analysis is None:
            self._show_empty_graph_message()
            return

        analysis = self.analysis
        ax = self.axes
        ax.clear()
        ax.set_facecolor("white")
        ax.grid(True, color="#e6e6e6", linewidth=0.9, zorder=0)

        x_values = [float(x) for x, _ in analysis.points]
        y_values = [float(y) for _, y in analysis.points]
        x_min, x_max = min(x_values), max(x_values)
        span = (x_max - x_min) or 1.0
        graph_x_min = x_min - 0.12 * span
        graph_x_max = x_max + 0.12 * span
        samples = self._sample_x(graph_x_min, graph_x_max, 260)

        all_y = list(y_values)
        if analysis.source_function_name:
            function = get_function(analysis.source_function_name)
            source_points = self._sample_source_function(function.name, samples)
            if source_points:
                sx, sy = zip(*source_points)
                all_y.extend(sy)
                ax.plot(sx, sy, color=COLORS["source"], linewidth=2.4, label=f"f(x) = {function.label}", zorder=2)

        for config in METHOD_CONFIGS:
            method_points = self._sample_interpolant(samples, config.result_name)
            if method_points:
                sx, sy = zip(*method_points)
                all_y.extend(sy)
                ax.plot(
                    sx,
                    sy,
                    color=COLORS[config.color_key],
                    linewidth=config.linewidth,
                    linestyle=config.linestyle,
                    label=config.graph_label,
                    zorder=3,
                )

        ax.scatter(x_values, y_values, color=COLORS["nodes"], s=34, label="Узлы", zorder=4)
        ax.scatter(
            [float(analysis.x_value)],
            [float(analysis.results[0].value)],
            color="#edae49",
            s=46,
            label="Точка x",
            zorder=5,
        )

        y_min, y_max = min(all_y), max(all_y)
        y_span = (y_max - y_min) or 1.0
        ax.set_xlim(graph_x_min, graph_x_max)
        ax.set_ylim(y_min - 0.15 * y_span, y_max + 0.15 * y_span)
        if y_min - 0.15 * y_span <= 0 <= y_max + 0.15 * y_span:
            ax.axhline(0.0, color="#555555", linewidth=1.0, zorder=1)
        if graph_x_min <= 0 <= graph_x_max:
            ax.axvline(0.0, color="#555555", linewidth=1.0, zorder=1)
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.set_title("Интерполяция функции")
        ax.legend(loc="best", fontsize=9)
        self.figure.tight_layout()
        self.figure_canvas.draw_idle()

    def _draw_method_graph(self, method_tab: MethodTab) -> None:
        if self.analysis is None:
            return
        if method_tab.canvas is None or method_tab.figure is None or method_tab.axes is None:
            method_tab.graph_label.configure(text="Для построения графика нужен пакет matplotlib.")
            method_tab.graph_label.grid()
            return

        method_points_exist = any(
            result.name == method_tab.config.result_name
            for result in self.analysis.results
        )
        if not method_points_exist:
            method_tab.graph_label.configure(text="Метод недоступен для текущих данных.")
            method_tab.graph_label.grid()
            method_tab.canvas.get_tk_widget().grid_remove()
            return

        analysis = self.analysis
        ax = method_tab.axes
        ax.clear()
        ax.set_facecolor("white")
        ax.grid(True, color="#e6e6e6", linewidth=0.9, zorder=0)
        method_tab.graph_label.grid_remove()
        method_tab.canvas.get_tk_widget().grid()

        x_values = [float(x) for x, _ in analysis.points]
        y_values = [float(y) for _, y in analysis.points]
        x_min, x_max = min(x_values), max(x_values)
        span = (x_max - x_min) or 1.0
        graph_x_min = x_min - 0.12 * span
        graph_x_max = x_max + 0.12 * span
        samples = self._sample_x(graph_x_min, graph_x_max, 260)

        all_y = list(y_values)
        if analysis.source_function_name:
            function = get_function(analysis.source_function_name)
            source_points = self._sample_source_function(function.name, samples)
            if source_points:
                sx, sy = zip(*source_points)
                all_y.extend(sy)
                ax.plot(
                    sx,
                    sy,
                    color=COLORS["source"],
                    linewidth=2.0,
                    label=f"f(x) = {function.label}",
                    zorder=2,
                )

        method_points = self._sample_interpolant(samples, method_tab.config.result_name)
        if method_points:
            sx, sy = zip(*method_points)
            all_y.extend(sy)
            ax.plot(
                sx,
                sy,
                color=COLORS[method_tab.config.color_key],
                linewidth=method_tab.config.linewidth + 0.4,
                linestyle=method_tab.config.linestyle,
                label=method_tab.config.graph_label,
                zorder=3,
            )

        ax.scatter(x_values, y_values, color=COLORS["nodes"], s=30, label="Узлы", zorder=4)
        ax.scatter(
            [float(analysis.x_value)],
            [float(self._method_value(method_tab.config.result_name))],
            color="#edae49",
            s=44,
            label="Точка x",
            zorder=5,
        )

        y_min, y_max = min(all_y), max(all_y)
        y_span = (y_max - y_min) or 1.0
        ax.set_xlim(graph_x_min, graph_x_max)
        ax.set_ylim(y_min - 0.15 * y_span, y_max + 0.15 * y_span)
        if y_min - 0.15 * y_span <= 0 <= y_max + 0.15 * y_span:
            ax.axhline(0.0, color="#555555", linewidth=1.0, zorder=1)
        if graph_x_min <= 0 <= graph_x_max:
            ax.axvline(0.0, color="#555555", linewidth=1.0, zorder=1)
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.set_title(method_tab.config.result_name)
        ax.legend(loc="best", fontsize=9)
        method_tab.figure.tight_layout()
        method_tab.canvas.draw_idle()

    def _method_value(self, result_name: str) -> Decimal:
        if self.analysis is None:
            return Decimal("0")
        for result in self.analysis.results:
            if result.name == result_name:
                return result.value
        return Decimal("0")

    def _sample_interpolant(self, samples: list[Decimal], result_name: str) -> list[tuple[float, float]]:
        if self.analysis is None:
            return []
        points = self.analysis.points
        differences = self.analysis.finite_differences
        result_names = [result.name for result in self.analysis.results]
        if result_name not in result_names:
            return []
        result: list[tuple[float, float]] = []
        for x_decimal in samples:
            try:
                if result_name == "Многочлен Лагранжа":
                    y_decimal = lagrange_value(points, x_decimal)
                elif result_name == "Ньютон, первая формула":
                    y_decimal = newton_forward_value(points, differences, x_decimal).value
                elif result_name == "Ньютон, вторая формула":
                    y_decimal = newton_backward_value(points, differences, x_decimal).value
                elif result_name == "Гаусс, первая формула":
                    y_decimal = gauss_first_value(points, differences, x_decimal).value
                else:
                    y_decimal = gauss_second_value(points, differences, x_decimal).value
                y_float = float(y_decimal)
            except (DecimalException, InterpolationError, OverflowError, ValueError):
                continue
            if abs(y_float) <= 1e8:
                result.append((float(x_decimal), y_float))
        return result

    @staticmethod
    def _sample_source_function(function_name: str, samples: list[Decimal]) -> list[tuple[float, float]]:
        function = get_function(function_name)
        result: list[tuple[float, float]] = []
        for x_decimal in samples:
            try:
                y_float = float(function.evaluator(x_decimal))
            except (DecimalException, OverflowError, ValueError):
                continue
            if abs(y_float) <= 1e8:
                result.append((float(x_decimal), y_float))
        return result

    @staticmethod
    def _sample_x(x_min: float, x_max: float, count: int) -> list[Decimal]:
        if count <= 1:
            return [Decimal(str(x_min))]
        start = Decimal(str(x_min))
        end = Decimal(str(x_max))
        step = (end - start) / Decimal(count - 1)
        return [start + Decimal(index) * step for index in range(count)]

    def _show_empty_graph_message(self, text: str | None = None) -> None:
        if self.figure_canvas is None or self.figure is None or self.axes is None:
            if self.graph_message_label is not None:
                self.graph_message_label.configure(
                    text=text or "Для построения графика нужен пакет matplotlib.\nУстановите его командой: pip install matplotlib"
                )
            return

        self.axes.clear()
        self.axes.set_axis_off()
        self.axes.text(
            0.5,
            0.5,
            text or "После расчёта здесь появится график.",
            ha="center",
            va="center",
            transform=self.axes.transAxes,
            color="#666666",
            fontsize=12,
        )
        self.figure.tight_layout()
        self.figure_canvas.draw_idle()


def main() -> None:
    app = Lab5App()
    app.minsize(980, 720)
    app.mainloop()


if __name__ == "__main__":
    main()
