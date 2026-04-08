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

from .color_opacity import ColorOpacity, create_default_coloropacity


# -----------------------------------------------------------------------------
class ViewMixin:
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


# -----------------------------------------------------------------------------
class ColorOpacityMixin:
    def pre_init_color_opacity(self):
        self.coloropacity_unwatch_0: Callable | None = None
        self.coloropacity_unwatch_1: Callable | None = None

    def post_init_color_opacity(self):
        self.coloropacity: ColorOpacity = create_default_coloropacity(self.source)

    @property
    def source(self):
        return get_instance(self.Input)

    @watch("CustomColoropacity", eager=True)
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

        # Apply colors
        self.proxy.LookupTable = coloropacity.lut

        # Apply opacity (if available)
        if hasattr(self.proxy, "ScalarOpacityFunction"):
            self.proxy.ScalarOpacityFunction = coloropacity.pwf

        self.render()

    def on_coloropacity_active_array_change(self, active_data_array):
        if not active_data_array:
            return

        if self.proxy is None:
            return

        self.proxy.ColorArrayName = ("POINTS", active_data_array)


# -----------------------------------------------------------------------------
class OutlineProperties(ViewMixin, StateDataModel):
    # Core representation properties
    Input = Sync(str)  # id of SourceProxy
    Label = Sync(str)
    Type = Sync(str)
    Icon = Sync(str)
    Visibility = Sync(bool, False)
    View = Sync(str)
    proxy = ServerOnly(servermanager.Proxy | None)

    def __init__(self, server, **kwargs):
        super().__init__(server, **kwargs)
        self.pull()
        self.reset_camera()

    def pull(self):
        if self.proxy is None:
            return

        self.Visibility = bool(self.proxy.Visibility)


# -----------------------------------------------------------------------------
class VolumeProperties(ViewMixin, ColorOpacityMixin, StateDataModel):
    # Core representation properties
    Input = Sync(str)  # id of SourceProxy
    Label = Sync(str)
    Type = Sync(str)
    Icon = Sync(str)
    Visibility = Sync(bool, False)
    View = Sync(str)
    proxy = ServerOnly(servermanager.Proxy | None)

    # Color/Opacity properties
    ColorOpacityId = Sync(str)  # id of the active coloropacity for this representation
    CustomColoropacity = Sync(bool, False)  # use local/source coloropacity

    # Volume specific
    InterpolationType = Sync(str, "Nearest")  # Nearest, Linear, Cubic
    Shade = Sync(bool, False)
    GlobalIlluminationReach = Sync(float, 0)  # [0-1]
    VolumetricScatteringBlending = Sync(float, 0)  # [0-2]
    VolumeAnisotropy = Sync(float, 0)  # [-1,1]

    def __init__(self, server, **kwargs):
        self.pre_init_color_opacity()
        super().__init__(server, **kwargs)
        self.post_init_color_opacity()
        self.pull()
        self.reset_camera()

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


# -----------------------------------------------------------------------------
class SliceProperties(ViewMixin, ColorOpacityMixin, StateDataModel):
    # Core representation properties
    Input = Sync(str)  # id of SourceProxy
    Label = Sync(str)
    Type = Sync(str)
    Icon = Sync(str)
    Visibility = Sync(bool, False)
    View = Sync(str)
    proxy = ServerOnly(servermanager.Proxy | None)

    # Color/Opacity properties
    ColorOpacityId = Sync(str)  # id of the active coloropacity for this representation
    CustomColoropacity = Sync(bool, False)  # use local/source coloropacity

    # Slice specific
    Dimensions = Sync(tuple[int, int, int], (0, 0, 0))
    Slice = Sync(int, 0)
    SliceMax = Sync(int, 0)
    SliceDirection = Sync(str, "XY Plane", type_checking=TypeValidation.SKIP)
    SliceDirections = Sync(tuple[str, str, str], ("YZ Plane", "XZ Plane", "XY Plane"))

    def __init__(self, server, **kwargs):
        self.pre_init_color_opacity()
        super().__init__(server, **kwargs)
        self.post_init_color_opacity()
        self.pull()
        self.reset_camera()

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


# -----------------------------------------------------------------------------
REPRESENTATIONS = (
    OutlineProperties,
    SliceProperties,
    VolumeProperties,
)
