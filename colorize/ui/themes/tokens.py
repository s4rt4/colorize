"""Color tokens for the three interface brightness levels.

Every gray is neutral (R == G == B) so the chrome never tints how palette colors
are perceived. Only the accent tokens carry hue. Values are a first pass, to be
tuned side by side with Photoshop.
"""

THEME_ORDER = ("dark", "gray", "light")  # darkest to lightest, for Shift+F1 / Shift+F2
DEFAULT_THEME = "gray"

THEME_LABELS = {
    "dark": "Dark",
    "gray": "Medium Gray",
    "light": "Light",
}

ACCENT_KEYS = ("accent", "accent_hover", "accent_text")

THEMES = {
    "dark": {
        "bg_app": "#1E1E1E",
        "bg_panel": "#323232",
        "bg_header": "#282828",
        "bg_input": "#1E1E1E",
        "bg_hover": "#3E3E3E",
        "bg_selected": "#4A4A4A",
        "border": "#1A1A1A",
        "border_input": "#474747",
        "text": "#E0E0E0",
        "text_muted": "#9A9A9A",
        "text_disabled": "#6A6A6A",
        "scroll_handle": "#555555",
        "accent": "#378EF0",
        "accent_hover": "#4B9CF5",
        "accent_text": "#FFFFFF",
    },
    "gray": {
        "bg_app": "#3C3C3C",
        "bg_panel": "#535353",
        "bg_header": "#474747",
        "bg_input": "#3A3A3A",
        "bg_hover": "#5E5E5E",
        "bg_selected": "#6B6B6B",
        "border": "#3A3A3A",
        "border_input": "#2E2E2E",
        "text": "#F0F0F0",
        "text_muted": "#B8B8B8",
        "text_disabled": "#8A8A8A",
        "scroll_handle": "#757575",
        "accent": "#378EF0",
        "accent_hover": "#4B9CF5",
        "accent_text": "#FFFFFF",
    },
    "light": {
        "bg_app": "#D6D6D6",
        "bg_panel": "#F0F0F0",
        "bg_header": "#E2E2E2",
        "bg_input": "#FFFFFF",
        "bg_hover": "#DCDCDC",
        "bg_selected": "#CFCFCF",
        "border": "#C4C4C4",
        "border_input": "#B3B3B3",
        "text": "#1F1F1F",
        "text_muted": "#6E6E6E",
        "text_disabled": "#A8A8A8",
        "scroll_handle": "#BDBDBD",
        "accent": "#1473E6",
        "accent_hover": "#0D66D0",
        "accent_text": "#FFFFFF",
    },
}
