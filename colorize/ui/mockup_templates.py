"""SVG UI mockups filled with palette roles ($primary, $text, ...; see core.roles).

Plain SVG (no CSS, no scripts) so QtSvg renders it and it exports as a standalone file.
"""

from string import Template
from xml.sax.saxutils import escape

FONT = "Source Sans 3, Segoe UI, Arial, sans-serif"

_LANDING = Template(
    """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 800" width="1200" height="800" font-family="$font">
<rect width="1200" height="800" fill="$background"/>
<rect width="1200" height="76" fill="$surface"/>
<rect y="75" width="1200" height="1" fill="$border"/>
<circle cx="66" cy="38" r="15" fill="$primary"/>
<circle cx="78" cy="38" r="15" fill="$accent" opacity="0.85"/>
<text x="104" y="46" font-size="22" font-weight="700" fill="$text">$name</text>
<text x="700" y="44" font-size="16" fill="$muted">Product</text>
<text x="790" y="44" font-size="16" fill="$muted">Pricing</text>
<text x="876" y="44" font-size="16" fill="$muted">Customers</text>
<text x="986" y="44" font-size="16" fill="$text">Log in</text>
<rect x="1056" y="20" width="96" height="36" rx="18" fill="$primary"/>
<text x="1104" y="43" text-anchor="middle" font-size="15" font-weight="600" fill="$on_primary">Sign up</text>
<rect x="64" y="136" width="164" height="30" rx="15" fill="$surface" stroke="$border"/>
<circle cx="84" cy="151" r="5" fill="$accent"/>
<text x="98" y="156" font-size="14" fill="$muted">New: palettes 2.0</text>
<text x="64" y="240" font-size="58" font-weight="700" fill="$text">Color that works</text>
<text x="64" y="306" font-size="58" font-weight="700" fill="$primary">on every screen.</text>
<text x="64" y="362" font-size="20" fill="$muted">Build accessible palettes, check them for contrast and</text>
<text x="64" y="392" font-size="20" fill="$muted">color blindness, and ship them to code in one click.</text>
<rect x="64" y="430" width="168" height="52" rx="10" fill="$primary"/>
<text x="148" y="462" text-anchor="middle" font-size="17" font-weight="600" fill="$on_primary">Get started</text>
<rect x="248" y="430" width="168" height="52" rx="10" fill="$background" stroke="$secondary" stroke-width="2"/>
<text x="332" y="462" text-anchor="middle" font-size="17" font-weight="600" fill="$secondary">See the demo</text>
<rect x="690" y="124" width="446" height="368" rx="18" fill="$surface" stroke="$border"/>
<text x="722" y="170" font-size="16" font-weight="600" fill="$text">Weekly reach</text>
<text x="722" y="194" font-size="13" fill="$muted">Visitors by channel</text>
<rect x="722" y="226" width="382" height="1" fill="$border"/>
<rect x="722" y="306" width="382" height="1" fill="$border"/>
<rect x="722" y="386" width="382" height="1" fill="$border"/>
<rect x="736" y="296" width="40" height="160" rx="6" fill="$c0"/>
<rect x="796" y="246" width="40" height="210" rx="6" fill="$c1"/>
<rect x="856" y="336" width="40" height="120" rx="6" fill="$c2"/>
<rect x="916" y="270" width="40" height="186" rx="6" fill="$c3"/>
<rect x="976" y="316" width="40" height="140" rx="6" fill="$c4"/>
<rect x="1036" y="236" width="40" height="220" rx="6" fill="$c5"/>
<rect x="722" y="456" width="382" height="1" fill="$border"/>
<rect x="64" y="560" width="336" height="176" rx="14" fill="$surface" stroke="$border"/>
<rect x="432" y="560" width="336" height="176" rx="14" fill="$surface" stroke="$border"/>
<rect x="800" y="560" width="336" height="176" rx="14" fill="$surface" stroke="$border"/>
<rect x="88" y="584" width="44" height="44" rx="12" fill="$primary"/>
<rect x="456" y="584" width="44" height="44" rx="12" fill="$secondary"/>
<rect x="824" y="584" width="44" height="44" rx="12" fill="$accent"/>
<text x="88" y="664" font-size="19" font-weight="600" fill="$text">Harmony</text>
<text x="456" y="664" font-size="19" font-weight="600" fill="$text">Contrast</text>
<text x="824" y="664" font-size="19" font-weight="600" fill="$text">Export</text>
<text x="88" y="694" font-size="15" fill="$muted">Rules on a perceptual wheel.</text>
<text x="456" y="694" font-size="15" fill="$muted">WCAG and APCA, with fixes.</text>
<text x="824" y="694" font-size="15" fill="$muted">CSS, Tailwind and tokens.</text>
</svg>"""
)

_DASHBOARD = Template(
    """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 800" width="1200" height="800" font-family="$font">
<rect width="1200" height="800" fill="$background"/>
<rect width="236" height="800" fill="$primary"/>
<circle cx="48" cy="48" r="14" fill="$on_primary" opacity="0.9"/>
<text x="72" y="55" font-size="20" font-weight="700" fill="$on_primary">$name</text>
<rect x="20" y="104" width="196" height="40" rx="8" fill="$on_primary" opacity="0.16"/>
<text x="44" y="130" font-size="15" font-weight="600" fill="$on_primary">Overview</text>
<text x="44" y="178" font-size="15" fill="$on_primary" opacity="0.8">Campaigns</text>
<text x="44" y="218" font-size="15" fill="$on_primary" opacity="0.8">Audience</text>
<text x="44" y="258" font-size="15" fill="$on_primary" opacity="0.8">Reports</text>
<text x="44" y="298" font-size="15" fill="$on_primary" opacity="0.8">Settings</text>
<text x="276" y="68" font-size="28" font-weight="700" fill="$text">Overview</text>
<text x="276" y="96" font-size="15" fill="$muted">Last 30 days</text>
<rect x="976" y="40" width="184" height="40" rx="8" fill="$accent"/>
<text x="1068" y="66" text-anchor="middle" font-size="15" font-weight="600" fill="$on_accent">New campaign</text>
<rect x="276" y="128" width="276" height="120" rx="12" fill="$surface" stroke="$border"/>
<rect x="580" y="128" width="276" height="120" rx="12" fill="$surface" stroke="$border"/>
<rect x="884" y="128" width="276" height="120" rx="12" fill="$surface" stroke="$border"/>
<text x="300" y="164" font-size="14" fill="$muted">Visitors</text>
<text x="604" y="164" font-size="14" fill="$muted">Conversion</text>
<text x="908" y="164" font-size="14" fill="$muted">Revenue</text>
<text x="300" y="210" font-size="34" font-weight="700" fill="$text">48,210</text>
<text x="604" y="210" font-size="34" font-weight="700" fill="$text">3.8%</text>
<text x="908" y="210" font-size="34" font-weight="700" fill="$text">$$92.4k</text>
<rect x="452" y="186" width="76" height="26" rx="13" fill="$secondary"/>
<text x="490" y="204" text-anchor="middle" font-size="13" font-weight="600" fill="$on_secondary">+12%</text>
<rect x="276" y="276" width="580" height="336" rx="12" fill="$surface" stroke="$border"/>
<text x="300" y="312" font-size="17" font-weight="600" fill="$text">Traffic by channel</text>
<rect x="300" y="370" width="532" height="1" fill="$border"/>
<rect x="300" y="450" width="532" height="1" fill="$border"/>
<rect x="300" y="530" width="532" height="1" fill="$border"/>
<rect x="320" y="420" width="48" height="160" rx="6" fill="$c0"/>
<rect x="404" y="380" width="48" height="200" rx="6" fill="$c1"/>
<rect x="488" y="460" width="48" height="120" rx="6" fill="$c2"/>
<rect x="572" y="400" width="48" height="180" rx="6" fill="$c3"/>
<rect x="656" y="440" width="48" height="140" rx="6" fill="$c4"/>
<rect x="740" y="390" width="48" height="190" rx="6" fill="$c5"/>
<rect x="300" y="580" width="532" height="1" fill="$border"/>
<rect x="884" y="276" width="276" height="336" rx="12" fill="$surface" stroke="$border"/>
<text x="908" y="312" font-size="17" font-weight="600" fill="$text">Top campaigns</text>
<circle cx="916" cy="356" r="7" fill="$c0"/><text x="934" y="361" font-size="15" fill="$text">Spring launch</text>
<circle cx="916" cy="400" r="7" fill="$c1"/><text x="934" y="405" font-size="15" fill="$text">Newsletter</text>
<circle cx="916" cy="444" r="7" fill="$c2"/><text x="934" y="449" font-size="15" fill="$text">Partner promo</text>
<circle cx="916" cy="488" r="7" fill="$c3"/><text x="934" y="493" font-size="15" fill="$text">Retargeting</text>
<rect x="908" y="548" width="228" height="40" rx="8" fill="$background" stroke="$primary" stroke-width="2"/>
<text x="1022" y="574" text-anchor="middle" font-size="15" font-weight="600" fill="$primary">View all</text>
<rect x="276" y="640" width="884" height="120" rx="12" fill="$surface" stroke="$border"/>
<text x="300" y="676" font-size="17" font-weight="600" fill="$text">Goal progress</text>
<rect x="300" y="700" width="836" height="14" rx="7" fill="$border"/>
<rect x="300" y="700" width="560" height="14" rx="7" fill="$accent"/>
<text x="300" y="740" font-size="14" fill="$muted">67% of the quarterly target reached</text>
</svg>"""
)

TEMPLATES = {
    "landing": ("Landing Page", _LANDING),
    "dashboard": ("Dashboard", _DASHBOARD),
}


def render_svg(template: str, roles, name: str) -> str:
    """Fill a template with a RoleSet."""
    chart = list(roles.chart) or [roles.colors["primary"]]
    values = dict(roles.colors)
    values.update(
        {f"c{i}": chart[i % len(chart)] for i in range(6)},
        on_primary=roles.on("primary"),
        on_secondary=roles.on("secondary"),
        on_accent=roles.on("accent"),
        name=escape(name or "Colorize"),
        font=FONT,
    )
    return TEMPLATES[template][1].substitute(values)
