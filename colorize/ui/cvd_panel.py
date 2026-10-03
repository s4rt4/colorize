"""Color blindness panel: the active palette as seen with each vision type, with
'hard to tell apart' warnings, and the proof (canvas simulation) controls."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from colorize.core.cvd import CVD_LABELS, CVD_TYPES, confusable_pairs, cvd_name, simulate_hex_cached
from colorize.ui.widgets import ColorStrip


def type_combo(state) -> QComboBox:
    combo = QComboBox()
    for kind in CVD_TYPES:
        combo.addItem(CVD_LABELS[kind], kind)
    combo.setCurrentIndex(CVD_TYPES.index(state.cvd_type))
    combo.currentIndexChanged.connect(lambda i: state.set_cvd(kind=CVD_TYPES[i]))
    state.cvdChanged.connect(lambda: combo.setCurrentIndex(CVD_TYPES.index(state.cvd_type)))
    return combo


def severity_slider(state) -> QSlider:
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(0, 100)
    slider.setValue(round(state.cvd_severity * 100))
    slider.setToolTip("Severity: below 100% is the milder -anomaly form")
    slider.valueChanged.connect(lambda v: state.set_cvd(severity=v / 100))
    state.cvdChanged.connect(lambda: slider.setValue(round(state.cvd_severity * 100)))
    return slider


def proof_checkbox(state) -> QCheckBox:
    box = QCheckBox("Proof canvas")
    box.setToolTip("Show palettes and images as seen with the selected type (View › Proof Colors, Ctrl+Y)")
    box.setChecked(state.proof)
    box.toggled.connect(state.set_proof)
    state.proofChanged.connect(box.setChecked)
    return box


class CvdPanel(QWidget):
    def __init__(self, theme, state, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._state = state
        self._doc = None

        self.severity = severity_slider(state)
        self.severity_value = QLabel()
        self.severity_value.setProperty("role", "muted")
        self.severity_value.setMinimumWidth(40)
        severity_row = QHBoxLayout()
        severity_row.addWidget(QLabel("Severity"))
        severity_row.addWidget(self.severity, 1)
        severity_row.addWidget(self.severity_value)

        self.rows = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        self.normal_strip = ColorStrip(theme, 22)
        self.normal_strip.colorClicked.connect(state.set_foreground)
        grid.addWidget(QLabel("Normal vision"), 0, 0, 1, 2)
        grid.addWidget(self.normal_strip, 1, 0, 1, 2)
        for i, kind in enumerate(CVD_TYPES):
            radio = QRadioButton()
            radio.setToolTip("Use this type for Proof canvas")
            radio.toggled.connect(lambda on, k=kind: on and state.set_cvd(kind=k))
            title = QLabel()
            status = QLabel()
            status.setWordWrap(True)
            strip = ColorStrip(theme, 22)
            header = QHBoxLayout()
            header.setSpacing(6)
            header.addWidget(radio)
            header.addWidget(title, 1)
            row = 2 + i * 3
            grid.addLayout(header, row, 0, 1, 2)
            grid.addWidget(strip, row + 1, 0, 1, 2)
            grid.addWidget(status, row + 2, 0, 1, 2)
            self.rows[kind] = (radio, title, strip, status)

        self.proof = proof_checkbox(state)
        self.empty = QLabel("Open a palette to check it.")
        self.empty.setProperty("role", "muted")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        layout.addLayout(severity_row)
        layout.addWidget(self.empty)
        layout.addLayout(grid)
        layout.addWidget(self.proof)
        layout.addStretch(1)

        state.cvdChanged.connect(self._refresh)
        self._refresh()

    def set_document(self, doc) -> None:
        if self._doc is not None:
            self._doc.palette.changed.disconnect(self._refresh)
        self._doc = doc
        if doc is not None:
            doc.palette.changed.connect(self._refresh)
        self._refresh()

    def _refresh(self) -> None:
        severity = self._state.cvd_severity
        self.severity_value.setText(f"{severity * 100:.0f}%")
        colors = list(self._doc.palette.colors) if self._doc is not None else []
        self.empty.setVisible(not colors)
        self.normal_strip.set_colors(colors)
        for kind, (radio, title, strip, status) in self.rows.items():
            radio.blockSignals(True)
            radio.setChecked(kind == self._state.cvd_type)
            radio.blockSignals(False)
            title.setText(cvd_name(kind, severity))
            strip.set_colors([simulate_hex_cached(c, kind, severity) for c in colors])
            if len(colors) < 2:
                status.setText("")
                continue
            pairs = confusable_pairs(colors, kind, severity)
            if pairs:
                status.setText(f"⚠ {len(pairs)} pair{'s' if len(pairs) > 1 else ''} hard to tell apart")
                status.setProperty("role", "fail")
                status.setToolTip("\n".join(f"{colors[i]} and {colors[j]}" for i, j in pairs))
            else:
                status.setText("✓ All colors stay distinguishable")
                status.setProperty("role", "pass")
                status.setToolTip("")
            status.style().unpolish(status)
            status.style().polish(status)

    def conflicts(self, kind: str) -> str:
        return self.rows[kind][3].text()
