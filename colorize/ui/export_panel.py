"""Export panel: pick a format, preview the output live, copy it or save a file."""

from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont, QFontDatabase, QGuiApplication
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from colorize.formats import EXPORTERS
from colorize.formats.text_formats import SYNTAX_LABELS, SYNTAXES, slugify


class ExportPanel(QWidget):
    exported = pyqtSignal(str)  # path written

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._doc = None

        self.format = QComboBox()
        for key, exporter in EXPORTERS.items():
            self.format.addItem(exporter.label, key)
        self.syntax = QComboBox()
        for syntax in SYNTAXES:
            self.syntax.addItem(SYNTAX_LABELS[syntax], syntax)
        for combo in (self.format, self.syntax):  # let the form shrink in a narrow dock
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(8)
        self.prefix = QLineEdit()
        self.prefix.setToolTip("Swatch names become <prefix>-1, <prefix>-2, …")
        self._select(self.format, settings.value("export/format", "css", type=str))
        self._select(self.syntax, settings.value("export/syntax", "hex", type=str))

        form = QFormLayout()
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(6)
        form.addRow("Format", self.format)
        form.addRow("Colors as", self.syntax)
        form.addRow("Name prefix", self.prefix)

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono.setPixelSize(12)
        self.preview.setFont(QFont(mono))

        self.copy_button = QPushButton("Copy")
        self.copy_button.clicked.connect(self.copy)
        self.export_button = QPushButton("Export…")
        self.export_button.setProperty("accent", True)
        self.export_button.clicked.connect(lambda: self.export_file())
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.copy_button)
        buttons.addWidget(self.export_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addLayout(form)
        layout.addWidget(self.preview, 1)
        layout.addLayout(buttons)

        self.format.currentIndexChanged.connect(self._options_changed)
        self.syntax.currentIndexChanged.connect(self._options_changed)
        self.prefix.textChanged.connect(self.refresh)
        self.refresh()

    @staticmethod
    def _select(combo: QComboBox, key: str) -> None:
        index = combo.findData(key)
        if index >= 0:
            combo.setCurrentIndex(index)

    # ----- document -----

    def set_document(self, doc) -> None:
        if self._doc is not None:
            self._doc.palette.changed.disconnect(self.refresh)
            self._doc.palette.renamed.disconnect(self.refresh)
        self._doc = doc
        if doc is not None:
            doc.palette.changed.connect(self.refresh)
            doc.palette.renamed.connect(self.refresh)
        self.refresh()

    # ----- output -----

    @property
    def exporter(self):
        return EXPORTERS[self.format.currentData()]

    def prefix_value(self) -> str:
        default = slugify(self._doc.palette.name) if self._doc is not None else "color"
        return slugify(self.prefix.text(), default) if self.prefix.text().strip() else default

    def render(self):
        palette = self._doc.palette
        return self.exporter.render(palette.name, list(palette.colors), self.prefix_value(), self.syntax.currentData())

    def _options_changed(self, *_args) -> None:
        self._settings.setValue("export/format", self.format.currentData())
        self._settings.setValue("export/syntax", self.syntax.currentData())
        self.refresh()

    def refresh(self, *_args) -> None:
        exporter = self.exporter
        self.syntax.setEnabled(exporter.uses_syntax)
        has_colors = self._doc is not None and len(self._doc.palette) > 0
        self.prefix.setPlaceholderText(self.prefix_value())
        self.copy_button.setEnabled(has_colors and not exporter.binary)
        self.export_button.setEnabled(has_colors)
        if not has_colors:
            self.preview.setPlainText("Open a palette with at least one color to export it.")
            return
        output = self.render()
        if exporter.binary:
            self.preview.setPlainText(
                f"Binary file, {len(output)} bytes\n{len(self._doc.palette)} swatches in group “{self._doc.palette.name}”."
            )
        else:
            self.preview.setPlainText(output)

    def copy(self) -> None:
        if self.copy_button.isEnabled():
            QGuiApplication.clipboard().setText(self.render())

    def export_file(self, path: str | None = None) -> str | None:
        if not self.export_button.isEnabled():
            return None
        exporter = self.exporter
        if path is None:
            folder = self._settings.value("files/lastDir", str(Path.home()), type=str)
            start = str(Path(folder) / f"{self.prefix_value()}{exporter.suffix}")
            path, _ = QFileDialog.getSaveFileName(self, "Export Palette", start, f"{exporter.label} (*{exporter.suffix})")
            if not path:
                return None
            if not path.lower().endswith(exporter.suffix):
                path += exporter.suffix
        output = self.render()
        try:
            if exporter.binary:
                Path(path).write_bytes(output)
            else:
                Path(path).write_text(output, encoding="utf-8", newline="\n")
        except OSError as exc:
            QMessageBox.warning(self, "Export Palette", f"Could not write “{Path(path).name}”:\n{exc}")
            return None
        self._settings.setValue("files/lastDir", str(Path(path).parent))
        self.exported.emit(path)
        return path
