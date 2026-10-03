"""Built-in workspaces: which panels are open and how they are grouped.

Each workspace is a top-to-bottom list of tab groups in the right dock column.
Panels not listed are closed. User workspaces are stored as ADS perspectives.
"""

PANEL_WIDTH = 290

WORKSPACES = {
    "essentials": (
        ("color", "swatches", "harmony"),
        ("contrast", "cvd"),
        ("history", "export"),
    ),
    "palette": (
        ("swatches", "export"),
        ("color", "harmony"),
    ),
    "accessibility": (
        ("contrast",),
        ("cvd",),
        ("color", "swatches"),
    ),
}

WORKSPACE_LABELS = {
    "essentials": "Essentials",
    "palette": "Palette",
    "accessibility": "Accessibility",
}

CUSTOM_PREFIX = "custom:"
