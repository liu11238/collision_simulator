"""Live appearance tokens. Physics state is independent of appearance."""
import json
from pathlib import Path

PALETTES = json.loads(Path(__file__).with_name('themes.json').read_text())
NAMES = {'green': '绿色', 'blue': '蓝色', 'dark': '黑色', 'light': '白色'}
current = 'blue'

def __getattr__(name):
    if name in PALETTES[current]:
        return tuple(PALETTES[current][name])
    raise AttributeError(name)

def color(value):
    """Adapt legacy secondary surfaces while keeping transparent effects intact."""
    r, g, b = value
    high, low = max(value), min(value)
    if high < 135 and high - low < 65:
        level = sum(value) / 3
        if current == 'light':
            shade = int(255 - level * .85)
            return (shade, shade, min(255, shade + 3))
        if current == 'dark':
            shade = int(level)
            return (shade, shade, min(255, shade + 2))
        if current == 'blue':
            return (max(0, int(level*.65)), int(level*.85), min(255, int(level*1.3)))
    if current == 'light' and high > 140 and high-low > 65:
        return tuple(int(v*.68) for v in value)
    return value

def select(key):
    global current
    if key not in PALETTES:
        raise ValueError(key)
    current = key
    # These renderers retain semantic groups at module scope.
    import sys
    energy = sys.modules.get('render.energy.energy_renderer')
    if energy:
        palette = PALETTES[key]
        for name, token in {'ROD_ENERGY': 'ACCENT_2', 'BALL_ENERGY': 'ACCENT',
                            'POTENTIAL_ENERGY': 'MUTED', 'COLLISION_LOSS': 'RED',
                            'FRICTION_HEAT': 'ACCENT_2'}.items():
            setattr(energy, name, tuple(palette[token]))
    impact = sys.modules.get('presentation.impact_panel')
    if impact:
        impact.COLORS = tuple(tuple(PALETTES[key][n]) for n in ('ACCENT_2','ACCENT_3','RED'))
