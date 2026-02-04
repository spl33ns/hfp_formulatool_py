from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path

if importlib.util.find_spec("PySide6") is not None:  # pragma: no cover - optional dependency
    from PySide6 import QtCore, QtWidgets
else:  # pragma: no cover - fallback path
    QtCore = None
    QtWidgets = None

from core.pipeline import process_excel

logger = logging.getLogger(__name__)


class PipelineWorker(QtCore.QThread):
    progress = QtCore.Signal(str)
    finished = QtCore.Signal(dict)

    def __init__(self, input_path: Path, output_root: Path, max_rules: int):
        super().__init__()
        self.input_path = input_path
        self.output_root = output_root
        self.max_rules = max_rules

    def run(self) -> None:
        try:
            self.progress.emit("Starting processing...")
            results = process_excel(self.input_path, self.output_root, self.max_rules)
            self.progress.emit("Processing completed")
            self.finished.emit(results)
        except Exception as exc:  # pragma: no cover - UI error feedback
            self.progress.emit(f"Error: {exc}")
            self.finished.emit({})


class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Truth Table Generator")
        self.resize(800, 600)

        self.input_path_edit = QtWidgets.QLineEdit()
        self.output_path_edit = QtWidgets.QLineEdit()
        self.max_rules_edit = QtWidgets.QSpinBox()
        self.max_rules_edit.setRange(1, 100000)
        self.max_rules_edit.setValue(2000)

        self.log_view = QtWidgets.QTextEdit()
        self.log_view.setReadOnly(True)

        self.run_button = QtWidgets.QPushButton("Run")
        self.open_output_button = QtWidgets.QPushButton("Open Output Folder")
        self.open_output_button.setEnabled(False)

        self._setup_layout()
        self._set_defaults()

        self.run_button.clicked.connect(self.run_pipeline)
        self.open_output_button.clicked.connect(self.open_output_folder)

        self.worker: PipelineWorker | None = None
        self.output_root = None

    def _setup_layout(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        layout.addLayout(self._build_row("Input Excel", self.input_path_edit, self.browse_input))
        layout.addLayout(self._build_row("Output Folder", self.output_path_edit, self.browse_output))

        max_row = QtWidgets.QHBoxLayout()
        max_row.addWidget(QtWidgets.QLabel("MAX_RULES_PER_SECTION"))
        max_row.addWidget(self.max_rules_edit)
        layout.addLayout(max_row)

        layout.addWidget(self.run_button)
        layout.addWidget(self.open_output_button)
        layout.addWidget(self.log_view)

    def _build_row(self, label_text, line_edit, handler):
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel(label_text))
        row.addWidget(line_edit)
        button = QtWidgets.QPushButton("Browse")
        button.clicked.connect(handler)
        row.addWidget(button)
        return row

    def _set_defaults(self) -> None:
        fixtures = Path(__file__).resolve().parents[1] / "fixtures"
        default_input = fixtures / "Formel_extrakt.xlsx"
        if default_input.exists():
            self.input_path_edit.setText(str(default_input))
        self.output_path_edit.setText(str(Path.cwd() / "output"))

    def browse_input(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Input Excel", "", "Excel Files (*.xlsx)")
        if path:
            self.input_path_edit.setText(path)

    def browse_output(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if path:
            self.output_path_edit.setText(path)

    def run_pipeline(self) -> None:
        input_path = Path(self.input_path_edit.text()).expanduser()
        output_root = Path(self.output_path_edit.text()).expanduser()
        max_rules = int(self.max_rules_edit.value())

        self.output_root = output_root
        self.log_view.clear()
        self.run_button.setEnabled(False)
        self.open_output_button.setEnabled(False)

        self.worker = PipelineWorker(input_path, output_root, max_rules)
        self.worker.progress.connect(self.log_view.append)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_finished(self, results: dict) -> None:
        total = sum(len(sections) for sections in results.values()) if results else 0
        succeeded = sum(len([s for s in sections if s.status == "OK"]) for sections in results.values()) if results else 0
        failed = total - succeeded
        self.log_view.append(f"Summary: total={total}, succeeded={succeeded}, failed={failed}")
        self.run_button.setEnabled(True)
        self.open_output_button.setEnabled(True)

    def open_output_folder(self) -> None:
        if not self.output_root:
            return
        QtWidgets.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(self.output_root)))


def run_app() -> None:
    logging.basicConfig(level=logging.INFO)
    if QtWidgets is None:  # pragma: no cover
        import threading
        import tkinter as tk
        from tkinter import filedialog, messagebox

        root = tk.Tk()
        root.title("Truth Table Generator")

        input_var = tk.StringVar()
        output_var = tk.StringVar(value=str(Path.cwd() / "output"))
        max_rules_var = tk.IntVar(value=2000)
        log_text = tk.Text(root, height=20, width=80)

        def browse_input():
            path = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx")])
            if path:
                input_var.set(path)

        def browse_output():
            path = filedialog.askdirectory()
            if path:
                output_var.set(path)

        def run_pipeline():
            def task():
                try:
                    results = process_excel(
                        Path(input_var.get()),
                        Path(output_var.get()),
                        int(max_rules_var.get()),
                    )
                    total = sum(len(sections) for sections in results.values())
                    succeeded = sum(len([s for s in sections if s.status == "OK"]) for sections in results.values())
                    failed = total - succeeded
                    log_text.insert(tk.END, f"Summary: total={total}, succeeded={succeeded}, failed={failed}\n")
                except Exception as exc:
                    messagebox.showerror("Error", str(exc))

            threading.Thread(target=task, daemon=True).start()

        tk.Label(root, text="Input Excel").grid(row=0, column=0, sticky="w")
        tk.Entry(root, textvariable=input_var, width=60).grid(row=0, column=1)
        tk.Button(root, text="Browse", command=browse_input).grid(row=0, column=2)

        tk.Label(root, text="Output Folder").grid(row=1, column=0, sticky="w")
        tk.Entry(root, textvariable=output_var, width=60).grid(row=1, column=1)
        tk.Button(root, text="Browse", command=browse_output).grid(row=1, column=2)

        tk.Label(root, text="MAX_RULES_PER_SECTION").grid(row=2, column=0, sticky="w")
        tk.Entry(root, textvariable=max_rules_var, width=10).grid(row=2, column=1, sticky="w")

        tk.Button(root, text="Run", command=run_pipeline).grid(row=3, column=0, columnspan=3, pady=5)
        log_text.grid(row=4, column=0, columnspan=3)

        root.mainloop()
        return

    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
