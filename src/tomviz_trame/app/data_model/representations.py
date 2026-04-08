from __future__ import annotations

from collections.abc import Callable

from loguru import logger
from paraview import servermanager
from trame.app.dataclass import (
    ServerOnly,
    StateDataModel,
    Sync,
    TypeValidation,
    watch,
)

from tomviz_trame.app.data_model.pipeline import SourceProxy

from .pipeline import ColorOpacity, create_default_color_opacity
from .view import WindowInternalState


# -----------------------------------------------------------------------------
class ViewMixin:
    @watch("Visibility")
    def _on_visibility_change(self, visibility):
        if self.proxy is None:
            return

        self.proxy.Visibility = int(visibility)
        self.render()

    def render(self, *_):
        self.view.render()

    def reset_camera(self, *_):
        self.view.reset_camera()


# -----------------------------------------------------------------------------
class ColorOpacityMixin:
    """
    color_opacity = Sync(ColorOpacity, has_dataclass=True)
    use_internal_color_opacity
    """

    def pre_init_color_opacity(self):
        self._color_opacity_unwatch_0: Callable | None = None
        self._color_opacity_unwatch_1: Callable | None = None

    def post_init_color_opacity(self):
        self._internal_color_opacity: ColorOpacity = create_default_color_opacity(
            self.input
        )

    @property
    def active_color_opacity_id(self):
        return self.server.state.active_color_opacity_id

    @active_color_opacity_id.setter
    def active_color_opacity_id(self, value):
        with self.server.state as s:
            s.active_color_opacity_id = value

    @watch("use_internal_color_opacity", eager=True)
    def _on_custom_color_opacity_change(self, use_internal):
        # unsubscribe from the current color_opacity
        if self._color_opacity_unwatch_0 is not None:
            self._color_opacity_unwatch_0()
            self._color_opacity_unwatch_0 = None

        if self._color_opacity_unwatch_1 is not None:
            self._color_opacity_unwatch_1()
            self._color_opacity_unwatch_1 = None

        active = (
            self._internal_color_opacity if use_internal else self.input.color_opacity
        )

        if (
            self.color_opacity
            and self.active_color_opacity_id == self.color_opacity._id
        ):
            self.active_color_opacity_id = active._id

        self.color_opacity = active

        self._color_opacity_unwatch_0 = active.watch(
            ["active_data_array"],
            self.on_color_opacity_active_array_change,
        )

        # can this rerender happen automatically when the lut/pwf is modified?
        self._color_opacity_unwatch_1 = active.watch(
            ["color_range", "opacities", "active_color_preset", "invert_color_preset"],
            self.render,
        )

        self.on_color_opacity_active_array_change(active.active_data_array)

        if self.proxy is None:
            return

        # Apply colors
        self.proxy.LookupTable = active.lut

        # Apply opacity (if available)
        if hasattr(self.proxy, "ScalarOpacityFunction"):
            self.proxy.ScalarOpacityFunction = active.pwf

        self.render()

    def on_color_opacity_active_array_change(self, active_data_array):
        if not active_data_array:
            return

        if self.proxy is None:
            return

        self.proxy.ColorArrayName = ("POINTS", active_data_array)


# -----------------------------------------------------------------------------
class OutlineProperties(ViewMixin, StateDataModel):
    # Core representation properties
    proxy = ServerOnly(servermanager.Proxy | None)
    input = Sync(SourceProxy, has_dataclass=True)
    view = Sync(WindowInternalState, has_dataclass=True)
    label = Sync(str)
    name = Sync(str)
    icon = Sync(str)

    # Outline specific
    Visibility = Sync(bool, False)

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
    proxy = ServerOnly(servermanager.Proxy | None)
    input = Sync(SourceProxy, has_dataclass=True)
    view = Sync(WindowInternalState, has_dataclass=True)
    label = Sync(str)
    name = Sync(str)
    icon = Sync(str)

    # Color/Opacity properties
    color_opacity = Sync(ColorOpacity, has_dataclass=True)
    use_internal_color_opacity = Sync(bool, False)

    # Volume specific
    Visibility = Sync(bool, False)
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
    input = Sync(SourceProxy, has_dataclass=True)
    view = Sync(WindowInternalState, has_dataclass=True)
    proxy = ServerOnly(servermanager.Proxy | None)
    label = Sync(str)
    name = Sync(str)
    icon = Sync(str)

    # Color/Opacity properties
    color_opacity = Sync(ColorOpacity, has_dataclass=True)
    use_internal_color_opacity = Sync(bool, False)

    # Slice specific
    Visibility = Sync(bool, False)
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
