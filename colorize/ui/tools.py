"""Toolbar tool definitions (order = toolbar order; None = separator)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Tool:
    key: str
    label: str
    icon: str
    shortcut: str

    @property
    def tooltip(self) -> str:
        return f"{self.label} Tool ({self.shortcut})"


_TOOL_LIST = (
    Tool("select", "Select", "select", "V"),
    None,
    Tool("eyedropper", "Eyedropper", "eyedropper", "I"),
    Tool("harmony", "Harmony", "harmony", "W"),
    Tool("extract", "Extract from Image", "extract", "E"),
    None,
    Tool("contrast", "Contrast Check", "contrast", "C"),
    Tool("cvd", "Color Blindness Preview", "cvd", "B"),
    None,
    Tool("hand", "Hand", "hand", "H"),
    Tool("zoom", "Zoom", "zoom", "Z"),
)

TOOL_LAYOUT = _TOOL_LIST
TOOLS = {tool.key: tool for tool in _TOOL_LIST if tool is not None}
