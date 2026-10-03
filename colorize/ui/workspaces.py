"""Built-in workspaces: which panels are open and how they are grouped.

Each workspace is a top-to-bottom list of tab groups in the right dock column.
Panels not listed are closed. User workspaces are stored as ADS perspectives.
"""

PANEL_WIDTH = 290

WORKSPACES = {
    "essentials": (
        ("color", "swatches", "harmony", "scale"),
        ("contrast", "cvd"),
        ("history", "export", "library", "gradient"),
    ),
    "palette": (
        ("swatches", "library", "export", "print"),
        ("color", "harmony", "scale", "gradient"),
    ),
    "accessibility": (
        ("contrast",),
        ("cvd", "print"),
        ("color", "swatches"),
    ),
}

# Relative heights of the tab groups above (same order).
WORKSPACE_HEIGHTS = {
    "essentials": (52, 33, 15),
    "palette": (45, 55),
    "accessibility": (48, 34, 18),
}

WORKSPACE_LABELS = {
    "essentials": "Essentials",
    "palette": "Palette",
    "accessibility": "Accessibility",
}

CUSTOM_PREFIX = "custom:"
