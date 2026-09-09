from __future__ import annotations

from typing import TYPE_CHECKING

from trame.app.dataclass import ServerOnly, StateDataModel, Sync, watch
from trame_colormaps.core import presets

from tomviz_trame.app.pipeline.vtk.core import LookupTable, PiecewiseFunction
from tomviz_trame.app.utils import colors as util_colors
from tomviz_trame.app.utils import data

if TYPE_CHECKING:
    from .port import OutputPortModel

DEFAULT_PRESET = "Fast"
DEFAULT_RANGE = (0.0, 1.0)
# Samples of the transfer function shown as the editor's gradient.
GRADIENT_SAMPLES = 32
# Opacity control point defaults, as vtkPiecewiseFunction wants them.
DEFAULT_MIDPOINT = 0.5
DEFAULT_SHARPNESS = 0.0

# State-file spellings of vtkColorTransferFunction color spaces.
COLOR_SPACE_ALIASES = {"CIELAB": "Lab", "LAB": "Lab"}


def normalize_color_space(name: str) -> str:
    return COLOR_SPACE_ALIASES.get(name, name) if name else "RGB"


class ColorOpacityModel(StateDataModel):
    """Color map and opacity transfer function for the data on one output
    port.

    The truth is ``color_points`` (``[x, r, g, b]`` rows), ``opacity_points``
    (``[x, opacity, midpoint, sharpness]`` rows) and ``color_space``, all in
    data units, the same vocabulary as the desktop app's state files. A
    preset only fills ``color_points``; ``color_range`` is the x extent of
    the points and rescales both sets when changed. The editor works on
    normalized copies (``scaled_colors`` sampled from the VTK transfer
    function, ``scaled_opacities`` two-way) over ``data_range``.

    Not a mirror of a graph object. It reads array names, ranges and
    histograms from its ``port`` (an ``OutputPortModel`` carrying image
    data; other families have no color map) and never computes them itself;
    the port calls ``on_port_data_changed`` after every execution and
    ``on_port_statistics`` when lazily computed statistics land.

    A map only asks the port for statistics while it is *enabled*, that is
    while it has ``users``: sinks coloring through it (``acquire`` /
    ``release`` from the sink side) or the color editor showing it (the
    manager registers a ``UI_USER`` token). A port nobody displays therefore
    costs nothing.
    """

    UI_USER = "ui"

    data_arrays = Sync(list[str], list)
    active_data_array = Sync(str)

    data_range = Sync(tuple[float, float, float], (0, 255, 1))
    # A list: the client writes it (range slider, reset button) as a JS array.
    color_range = Sync(list[float], lambda: list(DEFAULT_RANGE))

    # The transfer functions, in data units
    color_points = Sync(list, list)  # [[x, r, g, b], ...]
    opacity_points = Sync(list, list)  # [[x, opacity, midpoint, sharpness], ...]
    color_space = Sync(str, "RGB")
    active_color_preset = Sync(str, DEFAULT_PRESET)  # "" once the points are custom
    invert_color_preset = Sync(bool, False)

    # Editor views, normalized over data_range
    scaled_colors = Sync(
        list[util_colors.ColorNode],
        lambda: [(0, (0, 0, 0)), (1, (1, 1, 1))],
    )
    scaled_opacities = Sync(list[util_colors.OpacityNode], lambda: [(0, 0), (1, 1)])
    scaled_histograms = Sync(list[util_colors.OpacityNode], lambda: [(0, 1), (1, 1)])
    histograms_range = Sync(tuple[float, float], (0, 1))

    solid_color = Sync(int, 0)  # index in palette

    # Server side
    port = ServerOnly(StateDataModel | None)  # the OutputPortModel being colored
    lut = ServerOnly(LookupTable | None)
    pwf = ServerOnly(PiecewiseFunction | None)

    def __init__(self, server, **kwargs):
        self.users: set[str] = set()
        self._applied: tuple[int, str] | None = None  # (data_version, array)
        self._points_range = DEFAULT_RANGE  # what the points currently span
        self._preserve_range = False  # a loaded map keeps its range once
        super().__init__(server, **kwargs)
        if not self.color_points:
            self.apply_preset()
        if not self.opacity_points:
            lo, hi = self.color_range
            self.opacity_points = [
                [lo, 0.0, DEFAULT_MIDPOINT, DEFAULT_SHARPNESS],
                [hi, 1.0, DEFAULT_MIDPOINT, DEFAULT_SHARPNESS],
            ]
        self._update_lut()
        self._update_pwf()
        if self.port is not None:
            self.port.add_consumer(self)

    # ---- users ------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return bool(self.users)

    def acquire(self, user_id: str):
        """Register a user (a sink model id or ``UI_USER``); the first one
        enables the map and fetches its statistics."""
        if user_id in self.users:
            return
        self.users.add(user_id)
        if len(self.users) == 1:
            self.pull()

    def release(self, user_id: str):
        self.users.discard(user_id)

    def bind(self, port: OutputPortModel):
        """Color the data of another port."""
        if self.port is port:
            return
        if self.port is not None:
            self.port.remove_consumer(self)
        self.port = port
        self._applied = None
        port.add_consumer(self)
        self.pull()

    # ---- transfer functions -------------------------------------------------

    def apply_preset(self):
        """Fill ``color_points`` from ``active_color_preset`` over the
        current color range. Unknown names (custom points) are left alone."""
        preset = presets.PRESET_REGISTRY.get(self.active_color_preset)
        if preset is None:
            return
        rows = _rows(preset["RGBPoints"], 4)
        if self.invert_color_preset:
            xs = [row[0] for row in rows]
            rows = [[xs[0] + xs[-1] - row[0], *row[1:]] for row in reversed(rows)]
        self.color_space = normalize_color_space(preset.get("ColorSpace", "RGB"))
        self.color_points = _rescale_rows(rows, self.color_range)

    def load_map(self, colors, points, color_space: str = "RGB"):
        """Install a state-file map: ``colors`` is the flat ``[x, r, g, b,
        ...]`` list, ``points`` the flat ``[x, opacity, midpoint, sharpness,
        ...]`` list, both in data units. The map keeps its own range when
        the data's statistics first arrive."""
        color_rows = _rows(colors, 4)
        if not color_rows:
            return
        xs = [row[0] for row in color_rows]
        self._points_range = (min(xs), max(xs))
        self.active_color_preset = ""
        self.color_space = normalize_color_space(color_space)
        self.color_points = color_rows
        opacity_rows = _rows(points, 4)
        if opacity_rows:
            self.opacity_points = opacity_rows
        self._preserve_range = True
        self.color_range = list(self._points_range)
        self._update_lut()
        self._update_pwf()

    def to_state(self) -> dict:
        """The map in the state-file vocabulary (see ``load_map``)."""
        return {
            "colorSpace": self.color_space,
            "colors": [v for row in self.color_points for v in row],
            "points": [v for row in self.opacity_points for v in row],
        }

    @watch("active_color_preset", "invert_color_preset")
    def _on_preset_change(self, *_):
        self.apply_preset()

    @watch("color_range")
    def _on_color_range_change(self, color_range):
        """Stretch both point sets from the range they span to the new one."""
        new_range = (float(color_range[0]), float(color_range[1]))
        old_range = self._points_range
        self._points_range = new_range
        if old_range == new_range:
            return
        if self.color_points:
            self.color_points = _rescale_rows(self.color_points, new_range, old_range)
        if self.opacity_points:
            self.opacity_points = _rescale_rows(
                self.opacity_points, new_range, old_range
            )

    @watch("color_points", "color_space", "data_range")
    def _on_colors_change(self, *_):
        self._update_lut()

    @watch("opacity_points", "data_range")
    def _on_opacities_change(self, *_):
        self._update_pwf()

    def update_from_client_state(self, partial_state):
        """Client writes. The editor's opacity nodes come back through
        here (and only through here: the model's own syncs never do, so
        there is no echo to guard against), converted to data units."""
        super().update_from_client_state(partial_state)
        if "scaled_opacities" in partial_state:
            self._on_scaled_opacities_edited(self.scaled_opacities)

    def _on_scaled_opacities_edited(self, scaled_opacities):
        """The editor moved opacity nodes: back to data units."""
        lo, hi = self.data_range[0], self.data_range[1]
        by_x = {round(row[0], 9): row for row in self.opacity_points}
        rows = []
        for x_norm, opacity in scaled_opacities:
            x = lo + x_norm * (hi - lo)
            previous = by_x.get(round(x, 9))
            midpoint = previous[2] if previous else DEFAULT_MIDPOINT
            sharpness = previous[3] if previous else DEFAULT_SHARPNESS
            rows.append([x, float(opacity), midpoint, sharpness])
        self.opacity_points = rows

    def _update_lut(self):
        if self.lut is not None and self.color_points:
            self.lut.set_points(self.color_points, self.color_space)
            self.scaled_colors = self._sample_gradient()

    def _update_pwf(self):
        if self.pwf is not None:
            self.pwf.Points = [v for row in self.opacity_points for v in row]
        lo, hi = self.data_range[0], self.data_range[1]
        span = hi - lo
        self.scaled_opacities = [
            ((row[0] - lo) / span if span else 0.0, row[1])
            for row in self.opacity_points
        ]

    def _sample_gradient(self):
        """The transfer function sampled across ``data_range`` as the
        editor's normalized color nodes."""
        lo, hi = self.data_range[0], self.data_range[1]
        rgb = [0.0, 0.0, 0.0]
        nodes = []
        for i in range(GRADIENT_SAMPLES):
            t = i / (GRADIENT_SAMPLES - 1)
            self.lut.ctf.GetColor(lo + t * (hi - lo), rgb)
            nodes.append((t, (round(rgb[0], 4), round(rgb[1], 4), round(rgb[2], 4))))
        return nodes

    # ---- data side --------------------------------------------------------

    def pull(self):
        """Refresh array names from the port and (re)apply the statistics of
        the displayed array."""
        port = self.port
        image = port.image if port is not None else None
        if image is None or not port.has_data:
            return

        self.data_arrays = list(image.scalars_names)
        if not self.data_arrays:
            self.active_data_array = ""
            return

        # Keep the user's selection when the array still exists.
        active = self.active_data_array
        if active not in self.data_arrays:
            active = (
                image.active_scalars
                if image.active_scalars in self.data_arrays
                else self.data_arrays[0]
            )
        if active != self.active_data_array:
            self.active_data_array = active  # its watcher applies the statistics
        else:
            self._apply_statistics()

    def on_port_data_changed(self):
        self.pull()

    def on_port_statistics(self, name: str):
        if name == self.active_data_array:
            self._apply_statistics()

    @watch("active_data_array")
    def _on_active_data_array_change(self, *_):
        self._apply_statistics()

    def _apply_statistics(self):
        """Take the port's statistics of the displayed array, once per
        (data version, array): data range and histogram, and unless a
        loaded map asked to keep its range, the color range too."""
        port = self.port
        name = self.active_data_array
        if port is None or not name or not self.enabled:
            return

        key = (port.data_version, name)
        if self._applied == key:
            return

        stats = port.statistics(name)  # None: computing, on_port_statistics follows
        if stats is None:
            return
        self._applied = key

        v_min, v_max = stats.range
        step = max((v_max - v_min) / 255, 1)
        self.data_range = (v_min, v_max, step)
        if self._preserve_range:
            self._preserve_range = False
        else:
            self.color_range = [v_min, v_max]

        # Log-scaled counts, x normalized over the data range like the color
        # and opacity nodes; the baseline stays at 0 so empty bins are empty.
        histograms = list(map(data.log10, stats.histogram))
        if histograms:
            self.histograms_range = (0, max(*histograms, 1))
            self.scaled_histograms = util_colors.make_linear_nodes(histograms, (0, 1))
        else:
            self.histograms_range = (0, 1)


def _rows(flat, width: int) -> list[list[float]]:
    values = [float(v) for v in (flat or [])]
    return [values[i : i + width] for i in range(0, len(values) - width + 1, width)]


def _rescale_rows(rows, new_range, old_range=None) -> list[list[float]]:
    """Map the x (first column) of ``rows`` from ``old_range`` (default: the
    rows' own extent) onto ``new_range``, keeping the other columns."""
    if not rows:
        return []
    if old_range is None:
        xs = [row[0] for row in rows]
        old_range = (min(xs), max(xs))
    old_lo, old_hi = old_range
    new_lo, new_hi = new_range
    old_span = old_hi - old_lo
    return [
        [
            new_lo
            + ((row[0] - old_lo) / old_span if old_span else 0.0) * (new_hi - new_lo),
            *row[1:],
        ]
        for row in rows
    ]


def create_color_opacity(port: OutputPortModel):
    """A color map for ``port`` with its own VTK lookup table and opacity
    function. It starts without users, so it costs nothing until a sink or
    the color editor acquires it."""
    return ColorOpacityModel(
        port.server,
        port=port,
        lut=LookupTable(),
        pwf=PiecewiseFunction(),
    )
