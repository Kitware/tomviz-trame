from __future__ import annotations

from typing import TYPE_CHECKING

from trame.app.dataclass import ServerOnly, StateDataModel, Sync, watch

from tomviz_trame.app.pipeline.vtk.core import LookupTable, PiecewiseFunction
from tomviz_trame.app.utils import colors as util_colors
from tomviz_trame.app.utils import data

if TYPE_CHECKING:
    from .port import OutputPortModel


class ColorOpacityModel(StateDataModel):
    """Color map and opacity transfer function for the data on one output
    port.

    Not a mirror of a graph object. It reads array names, ranges and
    histograms from its ``port`` (an ``OutputPortModel`` carrying image
    data; other families have no color map) and never computes them itself;
    the port calls ``on_port_data_changed`` after every execution and
    ``on_port_statistics`` when lazily computed statistics land. Its watchers
    drive the VTK ``LookupTable`` / ``PiecewiseFunction`` the representations
    use.

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
    color_range = Sync(tuple[float, float], (0, 0))

    active_color_preset = Sync(str, "Fast")
    invert_color_preset = Sync(bool, False)

    scaled_colors = Sync(
        list[util_colors.ColorNode],
        lambda: [(0, (0, 0, 0)), (1, (1, 1, 1))],
    )
    scaled_opacities = Sync(list[util_colors.OpacityNode], lambda: [(0, 0), (1, 1)])
    scaled_histograms = Sync(list[util_colors.OpacityNode], lambda: [(0, 1), (1, 1)])
    opacities = Sync(list[util_colors.OpacityNode], lambda: [(0, 0), (1, 1)])

    histograms_range = Sync(tuple[float, float], (0, 1))

    solid_color = Sync(int, 0)  # index in palette

    # Server side
    port = ServerOnly(StateDataModel | None)  # the OutputPortModel being colored
    lut = ServerOnly(LookupTable | None)
    pwf = ServerOnly(PiecewiseFunction | None)

    def __init__(self, server, **kwargs):
        self.users: set[str] = set()
        self._applied: tuple[int, str] | None = None  # (data_version, array)
        super().__init__(server, **kwargs)
        if self.port is not None:
            self.port.add_consumer(self)

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

    # ---- VTK side ---------------------------------------------------------

    @watch(
        "color_range",
        "active_color_preset",
        "invert_color_preset",
    )
    def _on_color_preset_change(
        self, color_range, active_color_preset, invert_color_preset
    ):
        if self.server is None:
            return

        colors: list[util_colors.Color] = self.server.context.colormaps.presets[
            active_color_preset
        ].colors

        data_range = (self.data_range[0], self.data_range[1])
        data_delta = data_range[1] - data_range[0]
        scaled_color_range = (
            (color_range[0] - data_range[0]) / data_delta,
            (color_range[1] - data_range[0]) / data_delta,
        )

        if invert_color_preset:
            color_nodes = util_colors.make_linear_nodes(
                colors[::-1], scaled_color_range
            )
        else:
            color_nodes = util_colors.make_linear_nodes(colors, scaled_color_range)

        self.scaled_colors = color_nodes

        if self.lut:
            self.lut.apply_preset(active_color_preset)
            if invert_color_preset:
                self.lut.invert()
            self.lut.rescale(*color_range)

    @watch("scaled_opacities", "data_range")
    def _on_scaled_opacities_change(self, *_):
        opacities = util_colors.rescale_nodes(
            self.scaled_opacities, (self.data_range[0], self.data_range[1])
        )

        if self.pwf:
            pwf_points = []

            for scalar, opacity in opacities:
                pwf_points.extend(
                    (
                        scalar,
                        opacity,
                        0.5,  # bias 1
                        0,  # bias 2
                    )
                )

            self.pwf.Points = pwf_points

        self.opacities = opacities

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
        """Reset ranges and histogram from the port's statistics of the
        displayed array, once per (data version, array)."""
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
        self.color_range = (v_min, v_max)

        # Log-scaled counts, x normalized over the data range like the color
        # and opacity nodes; the baseline stays at 0 so empty bins are empty.
        histograms = list(map(data.log10, stats.histogram))
        if histograms:
            self.histograms_range = (0, max(*histograms, 1))
            self.scaled_histograms = util_colors.make_linear_nodes(histograms, (0, 1))
        else:
            self.histograms_range = (0, 1)


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
