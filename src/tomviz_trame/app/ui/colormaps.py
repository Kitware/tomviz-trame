from trame_colormaps.core import presets

from tomviz_trame.app import data_model
from tomviz_trame.app.utils.colors import Color

COLOR_PALETTE = [
    "#4CAF50",
    "#FB8C00",
    "#E82D2D",
    "#2196F3",
    "#ffffff",
    "#000000",
]


def color_to_float_rgb(color: str) -> Color:
    red = int(color[1:3], 16)
    green = int(color[3:5], 16)
    blue = int(color[5:7], 16)
    return (red / 255, green / 255, blue / 255)


# Colors sampled per preset. The color-opacity editor paints its background
# (and the histogram silhouette) as a gradient through these nodes, evenly
# spaced over the color range, so they must follow the preset's interpolation
# (its color space) rather than its raw control points.
PRESET_COLOR_SAMPLES = 32


def sample_preset_colors(name: str, count: int = PRESET_COLOR_SAMPLES) -> list[Color]:
    ctf = presets.get_preset_ctf(name)
    if ctf is None:
        return []
    low, high = ctf.GetRange()
    rgb = [0.0, 0.0, 0.0]
    colors = []
    for i in range(count):
        ctf.GetColor(low + (high - low) * i / max(count - 1, 1), rgb)
        colors.append((round(rgb[0], 4), round(rgb[1], 4), round(rgb[2], 4)))
    return colors


def generate_colormaps(server):
    color_maps = {}
    for name, imgs in presets.COLORBAR_CACHE.items():
        color_maps[name] = {
            "name": name,
            "colors": sample_preset_colors(name),
            "imgs": tuple(imgs.values()),
        }

    server.state.palette = COLOR_PALETTE

    return data_model.ColorMaps(
        server,
        presets={k: data_model.ColorPreset(server, **v) for k, v in color_maps.items()},
    )
