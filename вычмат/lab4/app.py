from __future__ import annotations

import html.parser
import re
import tkinter as tk
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
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

from approximation import (
    AnalysisResult,
    ApproximationError,
    ApproximationResult,
    analyze_points,
    best_result,
    format_full_report,
    format_number,
    parse_points,
)


COLORS = ["#d1495b", "#edae49", "#00798c", "#30638e", "#2a9d8f", "#6a4c93"]

_FUNC_NAMES = [
    "Линейная",
    "Полином 2-й степени",
    "Полином 3-й степени",
    "Экспоненциальная",
    "Логарифмическая",
    "Степенная",
]

_TAB_LABELS = [
    "Линейная",
    "Полином 2°",
    "Полином 3°",
    "Экспонента",
    "Логарифм",
    "Степенная",
]

def _is_dark(widget: tk.Text) -> bool:
    try:
        r, g, b = widget.winfo_rgb(widget.cget("background"))
        return (0.299 * r + 0.587 * g + 0.114 * b) / 65535 < 0.5
    except Exception:
        return False


def _md_setup_tags(widget: tk.Text) -> None:
    dark = _is_dark(widget)
    if dark:
        widget.tag_configure("md_h1",   font=("Helvetica", 15, "bold"),  spacing1=6, spacing3=4,  foreground="#ffffff")
        widget.tag_configure("md_h2",   font=("Helvetica", 13, "bold"),  spacing1=4, spacing3=2,  foreground="#e0e0e0")
        widget.tag_configure("md_bold", font=("Courier",   11, "bold"),                            foreground="#ffffff")
        widget.tag_configure("md_italic",font=("Courier",  11, "italic"),                          foreground="#cccccc")
        widget.tag_configure("md_code", font=("Courier",   11),                                    foreground="#e5c07b")
        widget.tag_configure("md_rule",                                                             foreground="#404040")
        widget.tag_configure("md_quote",font=("Courier",   11, "italic"), lmargin1=16, lmargin2=16,foreground="#56b6c2")
        widget.tag_configure("md_bullet",                                                           foreground="#888888")
        widget.tag_configure("md_mono", font=("Courier",   10),           lmargin1=8,  lmargin2=8,
                             background="#2a2a2a", foreground="#abb2bf")
    else:
        widget.tag_configure("md_h1",   font=("Helvetica", 15, "bold"),  spacing1=6, spacing3=4,  foreground="#1a1a1a")
        widget.tag_configure("md_h2",   font=("Helvetica", 13, "bold"),  spacing1=4, spacing3=2,  foreground="#2d2d2d")
        widget.tag_configure("md_bold", font=("Courier",   11, "bold"),                            foreground="#1a1a1a")
        widget.tag_configure("md_italic",font=("Courier",  11, "italic"))
        widget.tag_configure("md_code", font=("Courier",   11),           background="#f9f2f4",    foreground="#c7254e")
        widget.tag_configure("md_rule",                                                             foreground="#d0d0d0")
        widget.tag_configure("md_quote",font=("Courier",   11, "italic"), lmargin1=16, lmargin2=16,foreground="#2a9d8f")
        widget.tag_configure("md_bullet",                                                           foreground="#555555")
        widget.tag_configure("md_mono", font=("Courier",   10),           lmargin1=8,  lmargin2=8,
                             background="#f4f4f4", foreground="#333333")


class _HtmlToTk(html.parser.HTMLParser):
    _TAG_TO_TK = {
        "h1": "md_h1", "h2": "md_h2", "h3": "md_h2",
        "strong": "md_bold", "b": "md_bold",
        "em": "md_italic", "i": "md_italic",
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
        for t in self._stack:
            tk_tag = "md_mono" if (t == "code" and self._in_pre) else \
                     "md_code" if t == "code" else \
                     self._TAG_TO_TK.get(t)
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
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i] == tag:
                self._stack.pop(i)
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
    return _MD_INLINE_RE.sub(lambda m: m.group(1) or m.group(2) or m.group(3) or "", text)


def _md_render_inline(widget: tk.Text, text: str, extra: tuple[str, ...] = ()) -> None:
    pos = 0
    for m in _MD_INLINE_RE.finditer(text):
        if m.start() > pos:
            widget.insert(tk.END, text[pos:m.start()], extra)
        if m.group(1) is not None:
            widget.insert(tk.END, m.group(1), extra + ("md_bold",))
        elif m.group(2) is not None:
            widget.insert(tk.END, m.group(2), extra + ("md_italic",))
        elif m.group(3) is not None:
            widget.insert(tk.END, m.group(3), extra + ("md_code",))
        pos = m.end()
    if pos < len(text):
        widget.insert(tk.END, text[pos:], extra)


def _render_md_regex(widget: tk.Text, text: str) -> None:
    for line in text.splitlines():
        if re.fullmatch(r"\s*---+\s*", line):
            widget.insert(tk.END, "─" * 55 + "\n", "md_rule")
            continue
        m = re.match(r"^## (.+)", line)
        if m:
            widget.insert(tk.END, _md_strip_inline(m.group(1)) + "\n", "md_h2")
            continue
        m = re.match(r"^# (.+)", line)
        if m:
            widget.insert(tk.END, _md_strip_inline(m.group(1)) + "\n", "md_h1")
            continue
        m = re.match(r"^> ?(.*)", line)
        if m:
            _md_render_inline(widget, m.group(1) + "\n", ("md_quote",))
            continue
        m = re.match(r"^[-*] (.+)", line)
        if m:
            widget.insert(tk.END, "  • ", "md_bullet")
            _md_render_inline(widget, m.group(1) + "\n")
            continue
        if line.startswith("    ") or line.startswith("\t"):
            widget.insert(tk.END, line.lstrip() + "\n", "md_mono")
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
        html_str = _markdown_lib.markdown(
            text,
            extensions=["nl2br", "sane_lists"],
        )
        renderer = _HtmlToTk(widget)
        renderer.feed(html_str)
    else:
        _render_md_regex(widget, text)

    widget.configure(state="disabled")


@dataclass
class _FuncTab:
    stats_text: tk.Text
    tree: ttk.Treeview
    graph_label: ttk.Label
    figure: Any = None
    axes: Any = None
    canvas: Any = None


class Lab4App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ЛР4 — Аппроксимация функции методом наименьших квадратов")
        self.geometry("1180x860")

        self.points: list[tuple[Decimal, Decimal]] = []
        self.analysis: AnalysisResult | None = None
        self.results: list[ApproximationResult] = []

        self.figure: Any = None
        self.axes: Any = None
        self.figure_canvas: Any = None
        self.graph_message_label: ttk.Label | None = None

        self._func_tabs: list[_FuncTab] = []

        self._build_ui()
        self._fill_demo_data()

    def _build_ui(self) -> None:
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        calc_tab = ttk.Frame(self.notebook)
        all_graphs_tab = ttk.Frame(self.notebook)
        self.notebook.add(calc_tab, text="Аппроксимация")
        self.notebook.add(all_graphs_tab, text="Все графики")

        self._build_calc_tab(calc_tab)
        self._build_all_graphs_tab(all_graphs_tab)

        for label, func_name, color in zip(_TAB_LABELS, _FUNC_NAMES, COLORS):
            tab_frame = ttk.Frame(self.notebook)
            self.notebook.add(tab_frame, text=label)
            self._func_tabs.append(self._build_func_tab(tab_frame, func_name, color))

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

        ttk.Separator(frame, orient="horizontal").grid(
            row=1, column=0, columnspan=4, sticky="we", pady=6
        )

        self.file_frame = ttk.Frame(frame)
        self.file_frame.columnconfigure(1, weight=1)
        ttk.Label(self.file_frame, text="Файл входных данных:").grid(
            row=0, column=0, sticky="w", padx=6, pady=4
        )
        self.input_file = ttk.Entry(self.file_frame, width=42)
        self.input_file.grid(row=0, column=1, sticky="we", padx=6, pady=4)
        ttk.Button(
            self.file_frame,
            text="Обзор",
            command=lambda: self._pick_input_file(self.input_file),
        ).grid(row=0, column=2, padx=6, pady=4)

        self.manual_frame = ttk.Frame(frame)
        for column in range(4):
            self.manual_frame.columnconfigure(column, weight=1)

        ttk.Label(
            self.manual_frame,
            text="Точки (по одной в строке, формат: x y):",
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=6, pady=4)

        self.input_text = tk.Text(self.manual_frame, height=12, wrap="none", font=("Courier", 11))
        self.input_text.grid(
            row=1, column=0, columnspan=4, sticky="nsew", padx=6, pady=(0, 4)
        )
        self.manual_frame.rowconfigure(1, weight=1)
        input_y_scroll = ttk.Scrollbar(
            self.manual_frame, orient="vertical", command=self.input_text.yview
        )
        input_y_scroll.grid(row=1, column=4, sticky="ns", pady=(0, 4))
        input_x_scroll = ttk.Scrollbar(
            self.manual_frame, orient="horizontal", command=self.input_text.xview
        )
        input_x_scroll.grid(row=2, column=0, columnspan=4, sticky="we", padx=6)
        self.input_text.configure(
            yscrollcommand=input_y_scroll.set, xscrollcommand=input_x_scroll.set
        )

        ttk.Label(
            self.manual_frame,
            text="Допустимо от 8 до 12 точек. Разделители: пробел, табуляция или ';'.",
        ).grid(row=3, column=0, columnspan=4, sticky="w", padx=6, pady=4)

        self.manual_frame.grid(row=2, column=0, columnspan=4, sticky="nsew")

        self.plot_flag = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            frame, text="Построить график", variable=self.plot_flag
        ).grid(row=3, column=0, columnspan=2, sticky="w", padx=6, pady=4)

        self.output_mode, self.output_file = self._build_output_panel(frame, row_start=4)

        ttk.Button(frame, text="Запустить расчёт", command=self.run_analysis).grid(
            row=6, column=0, columnspan=4, sticky="we", padx=6, pady=8
        )

        ttk.Label(frame, text="Краткий итог:").grid(
            row=7, column=0, sticky="w", padx=6, pady=(4, 0)
        )
        self.summary_text = tk.Text(frame, height=7, wrap="word", state="disabled")
        self.summary_text.grid(
            row=8, column=0, columnspan=4, sticky="nsew", padx=6, pady=(0, 6)
        )

        ttk.Label(frame, text="Подробный отчёт:").grid(
            row=9, column=0, sticky="w", padx=6, pady=(4, 0)
        )
        self.report_text = tk.Text(frame, height=16, wrap="word", state="disabled")
        self.report_text.grid(
            row=10, column=0, columnspan=4, sticky="nsew", padx=6, pady=(0, 6)
        )
        frame.rowconfigure(10, weight=1)

    def _build_all_graphs_tab(self, tab: ttk.Frame) -> None:
        frame = ttk.Frame(tab)
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        ttk.Label(
            frame,
            text="График исходных точек и аппроксимирующих функций",
        ).grid(row=0, column=0, sticky="w", padx=6, pady=(0, 6))

        graph_area = ttk.Frame(frame)
        graph_area.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        graph_area.columnconfigure(0, weight=1)
        graph_area.rowconfigure(0, weight=1)

        if Figure is None or FigureCanvasTkAgg is None:
            self.graph_message_label = ttk.Label(
                graph_area,
                text=(
                    "Для построения графика нужен пакет matplotlib.\n"
                    "Установите его командой: pip install matplotlib"
                ),
                justify="center",
                foreground="#666666",
            )
            self.graph_message_label.grid(row=0, column=0, sticky="nsew")
        else:
            self.figure = Figure(figsize=(8.6, 5.2), dpi=100)
            self.axes = self.figure.add_subplot(111)
            self.figure_canvas = FigureCanvasTkAgg(self.figure, master=graph_area)
            self.figure_canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        ttk.Label(frame, text="Обозначения:").grid(
            row=2, column=0, sticky="w", padx=6, pady=(6, 2)
        )
        self.legend_canvas = tk.Canvas(
            frame,
            height=160,
            bg="white",
            highlightthickness=1,
            highlightbackground="#cfcfcf",
        )
        self.legend_canvas.grid(row=3, column=0, sticky="ew", padx=6, pady=(0, 6))
        self.legend_canvas.bind("<Configure>", lambda _event: self._fill_legend())

        self._fill_legend()
        self._show_empty_graph_message()

    def _build_func_tab(self, tab: ttk.Frame, func_name: str, color: str) -> _FuncTab:
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)

        stats_lf = ttk.LabelFrame(tab, text=f"  {func_name}  ")
        stats_lf.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        stats_lf.columnconfigure(0, weight=1)

        stats_text = tk.Text(
            stats_lf,
            height=7,
            wrap="word",
            font=("Courier", 11),
            relief="flat",
            bg=self.cget("bg"),
            state="disabled",
            cursor="arrow",
        )
        stats_text.pack(fill="x", padx=6, pady=(4, 6))
        stats_text.tag_configure("val", font=("Courier", 11, "bold"))
        stats_text.tag_configure("interp", foreground="#2a9d8f", font=("Courier", 11, "italic"))
        stats_text.tag_configure("muted", foreground="#888888")
        _set_stats_placeholder(stats_text)

        table_lf = ttk.LabelFrame(tab, text="  Таблица значений  ")
        table_lf.grid(row=1, column=0, sticky="ew", padx=8, pady=4)
        table_lf.columnconfigure(0, weight=1)

        cols = ("i", "xi", "yi", "phi", "eps")
        tree = ttk.Treeview(table_lf, columns=cols, show="headings", height=8)
        for col, hdr in zip(cols, ("i", "xi", "yi", "φ(xi)", "εi")):
            tree.heading(col, text=hdr)
        tree.column("i", anchor="center", width=40, stretch=False)
        for col in ("xi", "yi", "phi", "eps"):
            tree.column(col, anchor="e", width=130)

        vsb = ttk.Scrollbar(table_lf, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="ew", padx=6, pady=4)
        vsb.grid(row=0, column=1, sticky="ns", pady=4)

        graph_lf = ttk.LabelFrame(tab, text="  График  ")
        graph_lf.grid(row=2, column=0, sticky="nsew", padx=8, pady=(4, 8))
        graph_lf.columnconfigure(0, weight=1)
        graph_lf.rowconfigure(0, weight=1)

        graph_label = ttk.Label(
            graph_lf,
            text="После расчёта здесь появится график.",
            foreground="#666666",
            font=("Helvetica", 11),
            anchor="center",
        )
        graph_label.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

        fig = ax = canvas = None
        if Figure is not None and FigureCanvasTkAgg is not None:
            fig = Figure(figsize=(8, 3.8), dpi=100)
            ax = fig.add_subplot(111)
            canvas = FigureCanvasTkAgg(fig, master=graph_lf)
            canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
            canvas.get_tk_widget().grid_remove()
        else:
            graph_label.configure(text="Установите matplotlib: pip install matplotlib")

        return _FuncTab(
            stats_text=stats_text,
            tree=tree,
            graph_label=graph_label,
            figure=fig,
            axes=ax,
            canvas=canvas,
        )

    def _build_output_panel(
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

    def _fill_demo_data(self) -> None:
        demo = "\n".join(
            ["1 2.5", "2 3.7", "3 5.4", "4 7.8", "5 10.2", "6 13.1", "7 16.9", "8 20.4"]
        )
        self.input_text.delete("1.0", tk.END)
        self.input_text.insert("1.0", demo)

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

    def _toggle_input_mode(self) -> None:
        if self.input_mode.get() == "manual":
            self.file_frame.grid_remove()
            self.manual_frame.grid(row=2, column=0, columnspan=4, sticky="nsew")
        else:
            self.manual_frame.grid_remove()
            self.file_frame.grid(row=2, column=0, columnspan=4, sticky="we")

    def _read_input_text(self) -> str:
        if self.input_mode.get() == "file":
            path = self.input_file.get().strip()
            if not path:
                raise ValueError(
                    "Для чтения входных данных из файла необходимо указать путь к файлу."
                )
            try:
                return Path(path).read_text(encoding="utf-8")
            except OSError as exc:
                raise ValueError(f"Не удалось прочитать входной файл: {exc}") from exc
        return self.input_text.get("1.0", tk.END)

    def _show_output(self, report: str) -> None:
        render_md(self.report_text, report)
        if self.output_mode.get() == "file":
            output_path = self.output_file.get().strip()
            if not output_path:
                raise ValueError(
                    "Для записи результата в файл необходимо указать путь к выходному файлу."
                )
            try:
                Path(output_path).write_text(report + "\n", encoding="utf-8")
            except OSError as exc:
                raise ValueError(f"Не удалось записать результат в файл: {exc}") from exc
            messagebox.showinfo(
                "Сохранено",
                f"Результат успешно сохранён в файл:\n{output_path}",
            )

    def run_analysis(self) -> None:
        try:
            raw_text = self._read_input_text()
            points = parse_points(raw_text)
            analysis = analyze_points(points)
            report = format_full_report(points, analysis)
        except (ApproximationError, ValueError) as exc:
            self._clear_results()
            messagebox.showerror("Ошибка", str(exc))
            return

        self.points = points
        self.analysis = analysis
        self.results = analysis.results
        self._fill_summary()
        self._fill_legend()

        x_values = [p[0] for p in points]
        y_values = [p[1] for p in points]
        results_by_name = {r.name: r for r in analysis.results}
        issues_by_name = {i.name: i.message for i in analysis.issues}

        for ft, func_name, color in zip(self._func_tabs, _FUNC_NAMES, COLORS):
            self._populate_func_tab(
                ft,
                results_by_name.get(func_name),
                issues_by_name.get(func_name),
                x_values,
                y_values,
                color,
            )

        if self.plot_flag.get():
            self.draw_graph()
        else:
            self._show_empty_graph_message("Построение графика отключено.")

        try:
            self._show_output(report)
        except ValueError as exc:
            messagebox.showerror("Ошибка записи", str(exc))

    def _clear_results(self) -> None:
        self.points = []
        self.analysis = None
        self.results = []
        for w in (self.summary_text, self.report_text):
            w.configure(state="normal")
            w.delete("1.0", tk.END)
            w.configure(state="disabled")
        self._fill_legend()
        self._show_empty_graph_message()
        for ft in self._func_tabs:
            _reset_func_tab(ft)

    def _populate_func_tab(
        self,
        ft: _FuncTab,
        result: ApproximationResult | None,
        error: str | None,
        x_values: list[Decimal],
        y_values: list[Decimal],
        color: str,
    ) -> None:
        st = ft.stats_text
        st.configure(state="normal")
        st.delete("1.0", tk.END)

        if result is None:
            msg = error or "Функция не применима для данного набора точек."
            st.insert(tk.END, "Функция не построена:\n", "muted")
            st.insert(tk.END, msg, "muted")
            st.configure(state="disabled")
            for row in ft.tree.get_children():
                ft.tree.delete(row)
            ft.graph_label.configure(text=f"Функция не применима:\n{msg}")
            ft.graph_label.grid()
            if ft.canvas is not None:
                ft.canvas.get_tk_widget().grid_remove()
            return

        def line(label: str, value: str) -> None:
            st.insert(tk.END, label)
            st.insert(tk.END, value + "\n", "val")

        line("S  (сумма кв. откл.):  ", format_number(result.sse))
        line("δ  (ср. кв. откл.):    ", format_number(result.sigma))
        line("R² (коэф. детерм.):    ", format_number(result.r_squared))
        st.insert(tk.END, f"   ✓ {result.r_squared_message}\n", "interp")
        if result.pearson is not None:
            line("r  (Пирсон):           ", format_number(result.pearson))
        coeff_str = ", ".join(
            f"{n}={format_number(v)}" for n, v in result.coefficients.items()
        )
        line("Коэффициенты:          ", coeff_str)
        st.insert(tk.END, f"Формула: {result.formula}\n")
        st.configure(state="disabled")

        for row in ft.tree.get_children():
            ft.tree.delete(row)
        for idx, (x, y, phi, eps) in enumerate(
            zip(x_values, y_values, result.predictions, result.residuals), start=1
        ):
            ft.tree.insert(
                "",
                "end",
                values=(
                    idx,
                    format_number(x),
                    format_number(y),
                    format_number(phi),
                    format_number(eps),
                ),
            )

        if ft.canvas is None or ft.figure is None or ft.axes is None:
            return

        ft.graph_label.grid_remove()
        ft.canvas.get_tk_widget().grid()

        ax = ft.axes
        ax.clear()
        ax.set_facecolor("white")
        ax.grid(True, color="#e6e6e6", linewidth=0.9, zorder=0)

        fx = [float(v) for v in x_values]
        fy = [float(v) for v in y_values]
        x_min, x_max = min(fx), max(fx)
        x_span = (x_max - x_min) or 1.0
        gx_min = x_min - 0.12 * x_span
        gx_max = x_max + 0.12 * x_span

        curve_x: list[float] = []
        curve_y: list[float] = []
        step = (gx_max - gx_min) / 239
        for k in range(240):
            xv = gx_min + k * step
            if result.name in {"Логарифмическая", "Степенная"} and xv <= 0:
                continue
            try:
                yv = self._evaluate_formula(result, xv)
            except (OverflowError, ValueError):
                continue
            if abs(yv) > 1e8:
                continue
            curve_x.append(xv)
            curve_y.append(yv)

        all_y = fy + curve_y
        y_min = min(all_y) if all_y else 0.0
        y_max = max(all_y) if all_y else 1.0
        y_span = (y_max - y_min) or 1.0

        ax.plot(curve_x, curve_y, color=color, linewidth=2,
                label=f"φ(x) — {result.name}", zorder=2)
        ax.scatter(fx, fy, color="#111111", s=30, zorder=3, label="Исходные точки")
        ax.set_xlim(gx_min, gx_max)
        ax.set_ylim(y_min - 0.15 * y_span, y_max + 0.15 * y_span)
        if (y_min - 0.15 * y_span) <= 0 <= (y_max + 0.15 * y_span):
            ax.axhline(0.0, color="#555555", linewidth=1.0, zorder=1)
        if gx_min <= 0 <= gx_max:
            ax.axvline(0.0, color="#555555", linewidth=1.0, zorder=1)
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.legend(loc="best", fontsize=9)
        ft.figure.tight_layout()
        ft.canvas.draw_idle()

    def _fill_summary(self) -> None:
        best = best_result(self.results)
        coeff_str = ", ".join(f"{n} = {format_number(v)}" for n, v in best.coefficients.items())
        lines = [
            f"**Точек:** {len(self.points)}  ·  **Лучшая функция:** {best.name}",
            f"**Формула:** `{best.formula}`",
            f"**Коэффициенты:** {coeff_str}",
            f"**δ =** {format_number(best.sigma)}  ·  **R² =** {format_number(best.r_squared)}",
            f"**Оценка:** {best.r_squared_message}",
        ]
        if best.pearson is not None:
            lines.append(f"**Коэффициент Пирсона:** {format_number(best.pearson)}")
        if self.analysis and self.analysis.issues:
            lines.append("")
            lines.append("**Модели с ошибками:**")
            for issue in self.analysis.issues:
                lines.append(f"> **{issue.name}:** {issue.message}")
        render_md(self.summary_text, "\n".join(lines))

    def _fill_legend(self) -> None:
        canvas = self.legend_canvas
        canvas.delete("all")

        if not self.results:
            canvas.create_text(
                12, 24, anchor="w",
                text="После расчёта здесь появится соответствие цветов и функций.",
                fill="#666666", font=("Helvetica", 11),
            )
            return

        best_name = best_result(self.results).name
        row_height = 22
        y = 20

        canvas.create_oval(20, y - 5, 30, y + 5, fill="#111111", outline="")
        canvas.create_text(
            38, y, anchor="w", text="Исходные точки",
            fill="#222222", font=("Helvetica", 11),
        )
        y += row_height

        for index, result in enumerate(self.results):
            color = COLORS[index % len(COLORS)]
            line_width = 4 if result.name == best_name else 3
            canvas.create_line(16, y, 44, y, fill=color, width=line_width)
            label = result.name + (" (лучшая)" if result.name == best_name else "")
            canvas.create_text(
                52, y, anchor="w", text=label, fill="#222222",
                font=("Helvetica", 11, "bold" if result.name == best_name else "normal"),
            )
            y += row_height

    def draw_graph(self) -> None:
        if self.figure_canvas is None or self.figure is None or self.axes is None:
            self._show_empty_graph_message(
                "Для построения графика нужен пакет matplotlib.\n"
                "Установите его командой: pip install matplotlib"
            )
            return

        if not self.points or not self.results:
            self._show_empty_graph_message()
            return

        axes = self.axes
        axes.clear()
        axes.set_facecolor("white")
        axes.grid(True, color="#e6e6e6", linewidth=0.9, zorder=0)

        x_values = [float(x_value) for x_value, _ in self.points]
        y_values = [float(y_value) for _, y_value in self.points]
        all_y_values = list(y_values)

        x_min = min(x_values)
        x_max = max(x_values)
        x_span = x_max - x_min if x_max != x_min else 1.0
        graph_x_min = x_min - 0.12 * x_span
        graph_x_max = x_max + 0.12 * x_span

        samples: list[tuple[ApproximationResult, list[tuple[float, float]]]] = []
        for result in self.results:
            result_samples = self._sample_result(result, graph_x_min, graph_x_max, 240)
            samples.append((result, result_samples))
            all_y_values.extend(y_value for _, y_value in result_samples)

        graph_y_min = min(all_y_values)
        graph_y_max = max(all_y_values)
        graph_y_span = (graph_y_max - graph_y_min) or 1.0
        graph_y_min -= 0.15 * graph_y_span
        graph_y_max += 0.15 * graph_y_span

        best_name = best_result(self.results).name
        for index, (result, result_samples) in enumerate(samples):
            if result_samples:
                sample_x, sample_y = zip(*result_samples)
                axes.plot(
                    sample_x, sample_y,
                    color=COLORS[index % len(COLORS)],
                    linewidth=3 if result.name == best_name else 2,
                    zorder=2,
                )

        axes.scatter(x_values, y_values, color="#111111", s=28, zorder=3)
        axes.set_xlim(graph_x_min, graph_x_max)
        axes.set_ylim(graph_y_min, graph_y_max)
        if graph_y_min <= 0 <= graph_y_max:
            axes.axhline(0.0, color="#555555", linewidth=1.2, zorder=1)
        if graph_x_min <= 0 <= graph_x_max:
            axes.axvline(0.0, color="#555555", linewidth=1.2, zorder=1)
        axes.set_xlabel("X")
        axes.set_ylabel("Y")
        axes.set_title("График исходных точек и аппроксимирующих функций")
        self.figure.tight_layout()
        self.figure_canvas.draw_idle()

    def _show_empty_graph_message(self, text: str | None = None) -> None:
        if self.figure_canvas is None or self.figure is None or self.axes is None:
            if self.graph_message_label is not None:
                self.graph_message_label.configure(
                    text=text or (
                        "Для построения графика нужен пакет matplotlib.\n"
                        "Установите его командой: pip install matplotlib"
                    )
                )
            return

        self.axes.clear()
        self.axes.set_axis_off()
        self.axes.text(
            0.5, 0.5,
            text or "После расчёта здесь появится график.",
            ha="center", va="center",
            transform=self.axes.transAxes,
            color="#666666", fontsize=12,
        )
        self.figure.tight_layout()
        self.figure_canvas.draw_idle()

    def _sample_result(
        self,
        result: ApproximationResult,
        x_min: float,
        x_max: float,
        count: int,
    ) -> list[tuple[float, float]]:
        samples: list[tuple[float, float]] = []
        step = (x_max - x_min) / max(count - 1, 1)
        for index in range(count):
            x_value = x_min + index * step
            if result.name in {"Логарифмическая", "Степенная"} and x_value <= 0:
                continue
            try:
                y_value = self._evaluate_formula(result, x_value)
            except (OverflowError, ValueError):
                continue
            if abs(y_value) > 1e8:
                continue
            samples.append((x_value, y_value))
        return samples

    @staticmethod
    def _evaluate_formula(result: ApproximationResult, x_value: float) -> float:
        coefficients = result.coefficients
        x_decimal = Decimal(str(x_value))
        if result.name == "Линейная":
            return float(coefficients["a0"] + coefficients["a1"] * x_decimal)
        if result.name == "Полином 2-й степени":
            return float(
                coefficients["a0"]
                + coefficients["a1"] * x_decimal
                + coefficients["a2"] * (x_decimal ** 2)
            )
        if result.name == "Полином 3-й степени":
            return float(
                coefficients["a0"]
                + coefficients["a1"] * x_decimal
                + coefficients["a2"] * (x_decimal ** 2)
                + coefficients["a3"] * (x_decimal ** 3)
            )
        if result.name == "Экспоненциальная":
            return float(coefficients["a"] * (coefficients["b"] * x_decimal).exp())
        if result.name == "Логарифмическая":
            return float(coefficients["a"] * x_decimal.ln() + coefficients["b"])
        return float(coefficients["a"] * (coefficients["b"] * x_decimal.ln()).exp())

def _set_stats_placeholder(widget: tk.Text) -> None:
    widget.configure(state="normal")
    widget.delete("1.0", tk.END)
    widget.insert(tk.END, "После расчёта здесь появятся результаты.", "muted")
    widget.configure(state="disabled")


def _reset_func_tab(ft: _FuncTab) -> None:
    _set_stats_placeholder(ft.stats_text)
    for row in ft.tree.get_children():
        ft.tree.delete(row)
    ft.graph_label.configure(text="После расчёта здесь появится график.")
    ft.graph_label.grid()
    if ft.canvas is not None:
        ft.canvas.get_tk_widget().grid_remove()


def main() -> None:
    app = Lab4App()
    app.minsize(980, 720)
    app.mainloop()


if __name__ == "__main__":
    main()
