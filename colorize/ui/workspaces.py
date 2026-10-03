"""Built-in workspaces: which panels are open and how they are grouped.

Each workspace is a top-to-bottom list of tab groups in the right dock column.
Panels not listed are closed. User workspaces are stored as ADS perspectives.
"""

PANEL_WIDTH = 290
# At this width a tab group holds about three tabs; more scroll and cut off the first name.

WORKSPACES = {
    "essentials": (
        ("color", "swatches", "harmony"),
        ("contrast", "cvd"),
        ("history", "export", "library"),
    ),
    "palette": (
        ("swatches", "library", "export"),
        ("color", "harmony", "scale"),
        ("gradient", "print", "match"),
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
    "palette": (32, 43, 25),
    "accessibility": (48, 34, 18),
}

WORKSPACE_LABELS = {
    "essentials": "Essentials",
    "palette": "Palette",
    "accessibility": "Accessibility",
}

CUSTOM_PREFIX = "custom:"
