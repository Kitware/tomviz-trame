from collections.abc import Callable

from loguru import logger
from paraview import servermanager
from trame.app.dataclass import (
    ServerOnly,
    StateDataModel,
    Sync,
    TypeValidation,
    get_instance,
    watch,
)
from trame.widgets.paraview import VtkRemoteView

from tomviz_trame.app.utils import colors as util_colors
from tomviz_trame.app.utils import data


class ColorPreset(StateDataModel):
    name = Sync(str)
    colors = Sync(list[util_colors.Color], list)
    imgs = Sync(tuple[str, str], ("", ""))  # normal, inverted


class ColorMaps(StateDataModel):
    presets = Sync(dict[str, ColorPreset], dict, has_dataclass=True)


class SourceProxy(StateDataModel):
    # Data information to display
    name = Sync(str, "")
    expand_pipeline = Sync(bool, True)
    expand_representations = Sync(
        list[str], list
    )  # view_ids where reps are expanded ("WindowInternalState"?)
    dimensions = Sync(tuple[int, int, int], (0, 0, 0))
    bounds: tuple[float, float, float, float, float, float] = (0, -1, 0, -1, 0, -1)
    memory = Sync(int, 0)
    type = Sync(str, "")
    arrays = Sync(list[str], list)

    # ColorOpacity id associated with this Source
    ColorOpacityId = Sync(str, None)

    # Representations
    representations = Sync(
        dict[str, list[str]] | None, dict
    )  # { view_id: [rep_id, ...] }

    # Downstream pipelines
    pipelines = Sync(list[str], list)  # !(str -> SourceProxy) [source_proxy_id, ...]

    # Server only fields
    proxy = ServerOnly(servermanager.Proxy | None)
    coloropacity = ServerOnly(None, type_checking=TypeValidation.SKIP)

    def update_info(self):
        if self.proxy is None:
            return

        info = self.proxy.GetDataInformation()
        self.bounds = info.DataInformation.GetBounds()
        self.memory = info.DataInformation.GetMemorySize()
        self.type = info.GetDataSetTypeAsString()

        names = set()
        names.update(data.extract_arrays(self.proxy.GetPointDataInformation()))
        names.update(data.extract_arrays(self.proxy.GetCellDataInformation()))
        names.update(data.extract_arrays(self.proxy.GetFieldDataInformation()))
        self.arrays = list(names)


class WindowInternalState(StateDataModel):
    color = Sync(str)
    interactive_3d = Sync(bool, True)
    expanded = Sync(bool, False)
    orientation_axes_visibility = Sync(bool, True)
    center_axes_visibility = Sync(bool, False)
    pv_view = ServerOnly(servermanager.Proxy | None)
    widget_view = ServerOnly(VtkRemoteView)

    @watch("interactive_3d")
    def _on_change(self, interactive_3d):
        if self.pv_view is None or self.widget_view is None:
            return

        if interactive_3d:
            self.pv_view.InteractionMode = "3D"
        else:
            self.pv_view.InteractionMode = "2D"

        self.widget_view.update()

    @watch("orientation_axes_visibility")
    def _on_axes_visibility(self, orientation_axes_visibility):
        if self.pv_view is None or self.widget_view is None:
            return

        self.pv_view.OrientationAxesVisibility = int(orientation_axes_visibility)
        self.widget_view.update()

    @watch("center_axes_visibility")
    def _on_center_visibility(self, center_axes_visibility):
        if self.pv_view is None or self.widget_view is None:
            return

        self.pv_view.CenterAxesVisibility = int(center_axes_visibility)
        self.widget_view.update()

    def render(self):
        if self.widget_view is None:
            return
        self.widget_view.update()

    def reset_camera(self):
        if self.widget_view is None:
            return
        self.widget_view.reset_camera()


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


class Pipeline(StateDataModel):
    children = Sync(list[SourceProxy], list, has_dataclass=True)
    active_node = Sync(list[str], list)


class OutlineProperties(StateDataModel):
    source = ServerOnly(SourceProxy | None)
    proxy = ServerOnly(servermanager.Proxy | None)
    coloropacity = ServerOnly(ColorOpacity | None)
    coloropacity_unwatch_0 = ServerOnly(Callable | None)
    coloropacity_unwatch_1 = ServerOnly(Callable | None)
    Input = Sync(str)  # id of SourceProxy
    Label = Sync(str)
    Type = Sync(str)
    Icon = Sync(str)
    Visibility = Sync(bool, False)
    View = Sync(str)

    def pull(self):
        if self.proxy is None:
            return

        self.Visibility = bool(self.proxy.Visibility)

    @watch("Visibility")
    def _on_visibility_change(self, visibility):
        if self.proxy is None:
            return

        self.proxy.Visibility = int(visibility)
        self.render()

    def render(self, *_):
        get_instance(self.View).render()

    def reset_camera(self, *_):
        get_instance(self.View).render()


class VolumeProperties(StateDataModel):
    source = ServerOnly(SourceProxy | None)
    proxy = ServerOnly(servermanager.Proxy | None)
    coloropacity = ServerOnly(ColorOpacity | None)
    coloropacity_unwatch_0 = ServerOnly(Callable | None)
    coloropacity_unwatch_1 = ServerOnly(Callable | None)
    Input = Sync(str)  # id of SourceProxy
    Label = Sync(str)
    Type = Sync(str)
    Icon = Sync(str)
    Visibility = Sync(bool, False)
    View = Sync(str)
    ColorOpacityId = Sync(str)  # id of the active coloropacity for this representation
    # use this representation's coloropacity or the source's coloropacity
    CustomColoropacity = Sync(bool, False)
    # Volume rep specific
    InterpolationType = Sync(str, "Nearest")  # Nearest, Linear, Cubic
    Shade = Sync(bool, False)
    GlobalIlluminationReach = Sync(float, 0)  # [0-1]
    VolumetricScatteringBlending = Sync(float, 0)  # [0-2]
    VolumeAnisotropy = Sync(float, 0)  # [-1,1]

    def pull(self):
        if self.proxy is None:
            return

        # Update representation info
        self.Visibility = bool(self.proxy.Visibility)
        self.InterpolationType = str(self.proxy.InterpolationType)[1:-1]
        self.Shade = bool(self.proxy.Shade)
        self.GlobalIlluminationReach = float(self.proxy.GlobalIlluminationReach)
        self.VolumetricScatteringBlending = float(
            self.proxy.VolumetricScatteringBlending
        )
        self.VolumeAnisotropy = float(self.proxy.VolumeAnisotropy)

    def push(self):
        if self.proxy is None:
            return

        self.proxy.InterpolationType = self.InterpolationType
        self.proxy.Shade = int(self.Shade)
        self.proxy.GlobalIlluminationReach = self.GlobalIlluminationReach
        self.proxy.VolumetricScatteringBlending = self.VolumetricScatteringBlending
        self.proxy.VolumeAnisotropy = self.VolumeAnisotropy

    @watch("CustomColoropacity")
    def _on_custom_coloropacity_change(self, custom):
        # unsubscribe from the current coloropacity
        if self.coloropacity_unwatch_0 is not None:
            self.coloropacity_unwatch_0()
            self.coloropacity_unwatch_0 = None

        if self.coloropacity_unwatch_1 is not None:
            self.coloropacity_unwatch_1()
            self.coloropacity_unwatch_1 = None

        coloropacity: ColorOpacity | None = (
            self.coloropacity if custom else self.source.coloropacity
        )

        if coloropacity is None:
            self.ColorOpacityId = ""
            return

        active_coloropacity_id = self.server.state.active_coloropacity_id

        # Update active color opacity if already active
        if active_coloropacity_id == self.ColorOpacityId:
            with self.server.state as s:
                s.active_coloropacity_id = coloropacity._id

        # Update current selection
        self.ColorOpacityId = coloropacity._id

        self.coloropacity_unwatch_0 = coloropacity.watch(
            ["active_data_array"],
            self.on_coloropacity_active_array_change,
        )

        # can this rerender happen automatically when the lut/pwf is modified?
        self.coloropacity_unwatch_1 = coloropacity.watch(
            ["color_range", "opacities", "active_color_preset", "invert_color_preset"],
            self.render,
        )

        self.on_coloropacity_active_array_change(coloropacity.active_data_array)

        if self.proxy is None:
            return

        self.proxy.LookupTable = coloropacity.lut
        self.proxy.ScalarOpacityFunction = coloropacity.pwf

        self.render()

    def on_coloropacity_active_array_change(self, active_data_array):
        if not active_data_array:
            return

        if self.proxy is None:
            return

        self.proxy.ColorArrayName = ("POINTS", active_data_array)

    @watch(
        "InterpolationType",
        "Shade",
        "GlobalIlluminationReach",
        "VolumetricScatteringBlending",
        "VolumeAnisotropy",
    )
    def _on_prop_change(self, *_):
        self.push()
        self.render()

    @watch("Visibility")
    def _on_visibility_change(self, visibility):
        if self.proxy is None:
            return

        self.proxy.Visibility = int(visibility)
        self.render()

    def render(self, *_):
        get_instance(self.View).render()

    def reset_camera(self, *_):
        get_instance(self.View).render()


class SliceProperties(StateDataModel):
    source = ServerOnly(SourceProxy | None)
    proxy = ServerOnly(servermanager.Proxy | None)
    coloropacity = ServerOnly(ColorOpacity | None)
    coloropacity_unwatch_0 = ServerOnly(Callable | None)
    coloropacity_unwatch_1 = ServerOnly(Callable | None)
    Input = Sync(str)  # id of SourceProxy
    Label = Sync(str)
    Type = Sync(str)
    Icon = Sync(str)
    Visibility = Sync(bool, False)
    View = Sync(str)
    ColorOpacityId = Sync(str)  # id of the active coloropacity for this representation
    CustomColoropacity = Sync(
        bool,
        False,  # use this representation's coloropacity or the source's coloropacity
    )

    Dimensions = Sync(tuple[int, int, int], (0, 0, 0))
    Slice = Sync(int, 0)
    SliceMax = Sync(int, 0)
    SliceDirection = Sync(str, "XY Plane", type_checking=TypeValidation.SKIP)
    SliceDirections = Sync(tuple[str, str, str], ("YZ Plane", "XZ Plane", "XY Plane"))

    def pull(self):
        if self.proxy is None:
            return

        extent = self.proxy.Input.GetDataInformation().DataInformation.GetExtent()
        self.Dimensions = (
            extent[1] - extent[0],
            extent[3] - extent[2],
            extent[5] - extent[4],
        )
        logger.debug("extent {}", extent)
        logger.debug("Dimensions {}", self.Dimensions)

        # Update representation info
        self.Visibility = bool(self.proxy.Visibility)
        self.Slice = self.proxy.Slice
        self.SliceDirection = self.proxy.SliceDirection

        # Update max slice
        self._on_direction_change(self.SliceDirection)

    def push(self):
        if self.proxy is None:
            return

        self.proxy.SliceDirection = self.SliceDirection
        self.proxy.Slice = self.Slice

    @watch("CustomColoropacity")
    def _on_custom_coloropacity_change(self, custom):
        # unsubscribe from the current coloropacity
        if self.coloropacity_unwatch_0 is not None:
            self.coloropacity_unwatch_0()
            self.coloropacity_unwatch_0 = None

        if self.coloropacity_unwatch_1 is not None:
            self.coloropacity_unwatch_1()
            self.coloropacity_unwatch_1 = None

        coloropacity: ColorOpacity | None = (
            self.coloropacity if custom else self.source.coloropacity
        )

        if coloropacity is None:
            self.ColorOpacityId = ""
            return

        active_coloropacity_id = self.server.state.active_coloropacity_id

        if active_coloropacity_id == self.ColorOpacityId:
            with self.server.state as s:
                s.active_coloropacity_id = coloropacity._id

        self.ColorOpacityId = coloropacity._id

        self.coloropacity_unwatch_0 = coloropacity.watch(
            ["active_data_array"], self.on_coloropacity_active_array_change
        )

        # can this rerender happen automatically when the lut/pwf is modified?
        self.coloropacity_unwatch_1 = coloropacity.watch(
            ["color_range", "active_color_preset", "invert_color_preset"], self.render
        )

        self.on_coloropacity_active_array_change(coloropacity.active_data_array)

        if self.proxy is None:
            return

        self.proxy.LookupTable = coloropacity.lut

        self.render()

    def on_coloropacity_active_array_change(self, active_data_array):
        if not active_data_array:
            return

        if self.proxy is None:
            return

        self.proxy.ColorArrayName = ("POINTS", active_data_array)

    @watch("SliceDirection")
    def _on_direction_change(self, direction):
        if direction is None:
            return
        self.SliceMax = self.Dimensions[self.SliceDirections.index(direction)]
        logger.debug("SliceMax {}", self.SliceMax)
        if self.Slice >= self.SliceMax:
            self.Slice = 0

        self.push()
        self.render()

    @watch("Slice")
    def _on_slice_change(self, _):
        logger.debug("Slice {}", self.Slice)
        self.push()
        self.render()

    @watch("Visibility")
    def _on_visibility_change(self, visibility):
        if self.proxy is None:
            return

        self.proxy.Visibility = int(visibility)
        self.render()

    def render(self, *_):
        get_instance(self.View).render()

    def reset_camera(self, *_):
        get_instance(self.View).render()


REPRESENTATIONS = (OutlineProperties, SliceProperties, VolumeProperties)


def create_default_coloropacity(source: SourceProxy) -> ColorOpacity:
    coloropacity = ColorOpacity(
        source.server,
        source=source,
        lut=servermanager.rendering.PVLookupTable(),
        pwf=servermanager.piecewise_functions.PiecewiseFunction(),
    )
    coloropacity.pull()

    return coloropacity
