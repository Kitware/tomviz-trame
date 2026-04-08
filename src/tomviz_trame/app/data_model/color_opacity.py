from paraview import servermanager
from trame.app.dataclass import (
    ServerOnly,
    StateDataModel,
    Sync,
    watch,
)

from tomviz_trame.app.utils import colors as util_colors
from tomviz_trame.app.utils import data

from .pipeline import SourceProxy


class ColorOpacity(StateDataModel):
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
    colors = Sync(list[util_colors.ColorNode], lambda: [(0, (0, 0, 0)), (1, (1, 1, 1))])
    opacities = Sync(list[util_colors.OpacityNode], lambda: [(0, 0), (1, 1)])
    histograms = Sync(list[int], lambda: [1, 1])

    histograms_range = Sync(tuple[float, float], (0, 1))

    solid_color = Sync(int, 0)  # index in palette

    # Server side
    source = ServerOnly(SourceProxy | None)
    lut = ServerOnly(servermanager.Proxy | None)
    pwf = ServerOnly(servermanager.Proxy | None)

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
            self.lut.ApplyPreset(active_color_preset)
            if invert_color_preset:
                self.lut.InvertTransferFunction()
            self.lut.RescaleTransferFunction(*color_range)

    @watch("active_data_array")
    def _on_active_data_array_change(self, *_):
        self.reset_color_range()

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

    def pull(self):
        if self.source is None:
            return

        pv_source_proxy = self.source.proxy

        if pv_source_proxy is None:
            return

        self.data_arrays = data.extract_arrays(
            pv_source_proxy.GetPointDataInformation()
        )
        histograms = []
        if len(self.data_arrays):
            self.active_data_array = self.data_arrays[0]
            histograms = data.extract_histograms(
                pv_source_proxy, self.active_data_array, 128, True
            )
        else:
            self.active_data_array = ""
            histograms = []

        if histograms:
            self.histograms_range = (min(histograms), max(histograms))
            self.scaled_histograms = util_colors.make_linear_nodes(histograms, (0, 1))
        else:
            self.histograms_range = (0, 1)

    def reset_color_range(self, *_):
        if self.source is None:
            return

        if self.source.proxy is None:
            return

        # Update data related info
        array = self.source.proxy.GetPointDataInformation().GetArray(
            self.active_data_array
        )
        data_range = array.GetRange()
        v_min, v_max = data_range
        step = max((v_max - v_min) / 255, 1)
        self.data_range = (v_min, v_max, step)
        self.color_range = (self.data_range[0], self.data_range[1])


def create_default_coloropacity(source: SourceProxy) -> ColorOpacity:
    coloropacity = ColorOpacity(
        source.server,
        source=source,
        lut=servermanager.rendering.PVLookupTable(),
        pwf=servermanager.piecewise_functions.PiecewiseFunction(),
    )
    coloropacity.pull()

    return coloropacity
