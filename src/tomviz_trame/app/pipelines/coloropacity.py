from dataclasses import dataclass

from paraview import servermanager
from trame_dataclass.core import StateDataModel, field, watch

from tomviz_trame.app.pipelines.source import (
    SourceProxy,
    extract_arrays,
    extract_histograms,
)
from tomviz_trame.app.utils.colors import (
    Color,
    ColorNode,
    OpacityNode,
    make_linear_nodes,
    rescale_nodes,
)


@dataclass
class ColorOpacityContext:
    source: SourceProxy | None = None
    lut: servermanager.Proxy | None = None
    pwf: servermanager.Proxy | None = None


class ColorOpacity(StateDataModel):
    data_arrays: list[str]
    active_data_array: str

    data_range: tuple[float, float, float] = field(default=(0, 255, 1))
    color_range: tuple[float, float] = field(default=(0, 255))

    active_color_preset: str = "Fast"
    invert_color_preset: bool = False

    scaled_colors: list[ColorNode] = [(0, (0, 0, 0)), (1, (1, 1, 1))]
    scaled_opacities: list[OpacityNode] = [(0, 0), (1, 1)]
    scaled_histograms: list[OpacityNode] = [(0, 1), (1, 1)]
    colors: list[ColorNode] = [(0, (0, 0, 0)), (1, (1, 1, 1))]
    opacities: list[OpacityNode] = [(0, 0), (1, 1)]
    histograms: list[int] = [1, 1]

    histograms_range: tuple[float, float] = (0, 1)

    solid_color: int  # index in palette

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.ctx = ColorOpacityContext()

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

        colors: list[Color] = self.server.context.colormaps.presets[
            active_color_preset
        ].colors

        data_range = (self.data_range[0], self.data_range[1])
        data_delta = data_range[1] - data_range[0]
        scaled_color_range = (
            (color_range[0] - data_range[0]) / data_delta,
            (color_range[1] - data_range[0]) / data_delta,
        )

        if invert_color_preset:
            color_nodes = make_linear_nodes(colors[::-1], scaled_color_range)
        else:
            color_nodes = make_linear_nodes(colors, scaled_color_range)

        self.scaled_colors = color_nodes

        if self.ctx.lut:
            self.ctx.lut.ApplyPreset(active_color_preset)
            if invert_color_preset:
                self.ctx.lut.InvertTransferFunction()
            self.ctx.lut.RescaleTransferFunction(*color_range)

    @watch("active_data_array")
    def _on_active_data_array_change(self, *_):
        self.reset_color_range()

    @watch("scaled_opacities", "data_range")
    def _on_scaled_opacities_change(self, *_):
        opacities = rescale_nodes(
            self.scaled_opacities, (self.data_range[0], self.data_range[1])
        )

        if self.ctx.pwf:
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

            self.ctx.pwf.Points = pwf_points

        self.opacities = opacities

    def pull(self):
        source_proxy = self.ctx.source

        if source_proxy is None:
            return

        pv_source_proxy = source_proxy.ctx.proxy

        if pv_source_proxy is None:
            return

        self.data_arrays = extract_arrays(pv_source_proxy.GetPointDataInformation())
        histograms = []
        if len(self.data_arrays):
            self.active_data_array = self.data_arrays[0]
            histograms = extract_histograms(
                pv_source_proxy, self.active_data_array, 128, True
            )
        else:
            self.active_data_array = ""
            histograms = []

        if len(histograms):
            self.histograms_range = (min(histograms), max(histograms))
            self.scaled_histograms = make_linear_nodes(histograms, (0, 1))
        else:
            self.histograms_range = (0, 1)

    def reset_color_range(self, *_):
        source_proxy = self.ctx.source

        if source_proxy is None:
            return

        pv_source_proxy = source_proxy.ctx.proxy

        if pv_source_proxy is None:
            return

        # Update data related info
        array = pv_source_proxy.GetPointDataInformation().GetArray(
            self.active_data_array
        )
        data_range = array.GetRange()
        v_min, v_max = data_range
        step = max((v_max - v_min) / 255, 1)
        self.data_range = (v_min, v_max, step)
        self.color_range = (self.data_range[0], self.data_range[1])


def create_default_coloropacity(source: SourceProxy) -> ColorOpacity:
    coloropacity = ColorOpacity(source.server)
    coloropacity.ctx.source = source
    coloropacity.ctx.lut = servermanager.rendering.PVLookupTable()
    coloropacity.ctx.pwf = servermanager.piecewise_functions.PiecewiseFunction()
    coloropacity.pull()

    return coloropacity
