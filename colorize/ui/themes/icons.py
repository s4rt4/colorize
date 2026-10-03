"""Monochrome SVG icons, drawn for Colorize (no Adobe assets).

Bodies use ``C`` as the color placeholder; ``svg_for`` swaps in a theme color.
"""

_STROKE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="C" '
    'stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
)

ICONS = {
    # Tools
    "select": '<path d="M6.5 3.5l11 7-5 1.3-2.6 5.7z" fill="C"/>',
    "eyedropper": (
        '<path d="M16 4.5a2.1 2.1 0 0 1 3 3l-1.8 1.8-3-3z" fill="C"/>'
        '<path d="M13.4 7l3.6 3.6"/><path d="M14.5 8.2l-8.5 8.5V19h2.3l8.5-8.5"/>'
    ),
    "harmony": (
        '<circle cx="12" cy="12" r="8.5"/>'
        '<circle cx="12" cy="5.5" r="1.9" fill="C"/>'
        '<circle cx="17.6" cy="15.2" r="1.9" fill="C"/>'
        '<circle cx="6.4" cy="15.2" r="1.9" fill="C"/>'
    ),
    "extract": (
        '<rect x="3.5" y="5" width="17" height="14" rx="1.5"/>'
        '<circle cx="9" cy="10" r="1.6"/><path d="M4 17.5l5-4.5 3.5 3 3-2.5 4.5 4"/>'
    ),
    "contrast": '<circle cx="12" cy="12" r="8.5"/><path d="M12 3.5a8.5 8.5 0 0 1 0 17z" fill="C"/>',
    "cvd": (
        '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/>'
        '<circle cx="12" cy="12" r="3"/>'
    ),
    "hand": (
        '<path d="M8 12.5V6.5a1.5 1.5 0 0 1 3 0V11"/><path d="M11 11V4.5a1.5 1.5 0 0 1 3 0V11"/>'
        '<path d="M14 11V6.5a1.5 1.5 0 0 1 3 0v7c0 3.6-2.4 6.5-5.8 6.5-2.3 0-3.6-1-4.8-2.9'
        'L4.8 13.6a1.5 1.5 0 0 1 2.4-1.8L8 13"/>'
    ),
    "zoom": '<circle cx="10.5" cy="10.5" r="6"/><path d="M15 15l5 5"/>',
    # Panels
    "color": '<path d="M12 3.5s6 6.4 6 10.5a6 6 0 0 1-12 0C6 9.9 12 3.5 12 3.5z"/>',
    "swatches": (
        '<rect x="4" y="4" width="7" height="7" rx="1"/><rect x="13" y="4" width="7" height="7" rx="1"/>'
        '<rect x="4" y="13" width="7" height="7" rx="1"/><rect x="13" y="13" width="7" height="7" rx="1" fill="C"/>'
    ),
    "scale": (
        '<rect x="4" y="3.5" width="16" height="4" rx="1" fill="C"/><rect x="4" y="10" width="16" height="4" rx="1"/>'
        '<rect x="4" y="16.5" width="16" height="4" rx="1"/><path d="M8 12h8"/>'
    ),
    "gradient": (
        '<rect x="3.5" y="5" width="17" height="14" rx="1.5"/>'
        '<path d="M7 5v14" stroke-opacity="1"/><path d="M11 5v14" stroke-opacity=".7"/>'
        '<path d="M15 5v14" stroke-opacity=".45"/><path d="M18.5 5v14" stroke-opacity=".2"/>'
    ),
    "print": (
        '<path d="M7 9V4h10v5"/><rect x="3.5" y="9" width="17" height="8" rx="1.5"/>'
        '<path d="M7 14h10v6H7z"/><path d="M17 12h.01"/>'
    ),
    "history": '<path d="M4 12a8 8 0 1 0 2.4-5.7"/><path d="M4 4v4h4"/><path d="M12 8v4l3 2"/>',
    "export": '<path d="M12 15V4"/><path d="M8 8l4-4 4 4"/><path d="M5 13v6h14v-6"/>',
    "library": '<rect x="3.5" y="4" width="4.5" height="16" rx="1"/><rect x="9.5" y="4" width="4.5" height="16" rx="1"/>'
    '<path d="M15.6 5.6l3.4-.9 3.4 14.6-3.4.9z"/>',
    # Commands and chrome
    "new": '<path d="M6 3.5h8l4 4v13H6z"/><path d="M14 3.5v4h4"/><path d="M12 11v6M9 14h6"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "trash": '<path d="M5 7h14"/><path d="M10 7V5h4v2"/><path d="M7 7l1 12h8l1-12"/>',
    "swap": '<path d="M7 7h8a3 3 0 0 1 3 3v8"/><path d="M15 15l3 3 3-3"/><path d="M10 4L7 7l3 3"/>',
    "close": '<path d="M7 7l10 10M17 7L7 17"/>',
    "menu": '<path d="M5 7h14M5 12h14M5 17h14"/>',
    "undock": '<rect x="4" y="9" width="11" height="11" rx="1"/><path d="M10 4h10v10"/>',
    "collapse": '<path d="M6 7l5 5-5 5M13 7l5 5-5 5"/>',
    "expand": '<path d="M11 7l-5 5 5 5M18 7l-5 5 5 5"/>',
    "minimize": '<path d="M6 12h12"/>',
    "chevron-down": '<path d="M6 9l6 6 6-6"/>',
    "chevron-up": '<path d="M6 15l6-6 6 6"/>',
    "chevron-right": '<path d="M9 6l6 6-6 6"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7"/>',
    "warning": '<path d="M12 3.5L21.5 20h-19z"/><path d="M12 10v4.5"/><path d="M12 17.2v.3"/>',
    "target": '<circle cx="12" cy="12" r="3.5" fill="C"/><circle cx="12" cy="12" r="8"/>',
}

# Small glyphs used at 8-12 px need a heavier stroke to stay legible.
_HEAVY = {"chevron-down", "chevron-up", "chevron-right", "check", "close"}


def svg_for(name: str, color: str) -> str:
    width = "2.4" if name in _HEAVY else "1.6"
    return _STROKE.format(width=width, body=ICONS[name]).replace('"C"', f'"{color}"')
