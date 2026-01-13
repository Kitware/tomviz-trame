from loguru import logger
from paraview import servermanager, simple
from trame_client.widgets.core import TrameComponent
from trame_dataclass.core import StateDataModel, field, get_instance, watch

from .core import RepresentationType, extract_arrays


class VolumeProperties(StateDataModel):
    Input: str  # id of SourceProxy
    Label: str
    Type: str
    Icon: str
    Visibility: bool
    View: str

    # Volume rep specific
    InterpolationType: str  # Nearest, Linear, Cubic
    Shade: bool
    GlobalIlluminationReach: float = 0  # [0-1]
    VolumetricScatteringBlending: float = 0  # [0-2]
    VolumeAnisotropy: float = 0  # [-1,1]

    # color-by panel
    color_preset_inverted: bool
    color_by: str | None
    color_range: tuple[float, float] = field(default=(0, 1000))
    color_range_bounds: tuple[float, float, float] = field(default=(0, 1000, 1))
    color_preset: str = "Fast"
    solid_color: int  # index in palette
    array_names: list[str]

    def pull(self):
        proxy = getattr(self, "proxy", None)
        if proxy is None:
            return

        # Update data related info
        source_proxy = proxy.Input
        source_proxy.UpdatePipeline()
        self.array_names = extract_arrays(source_proxy.GetPointDataInformation())

        # Update representation info
        self.Visibility = bool(proxy.Visibility)
        self.InterpolationType = str(proxy.InterpolationType)[1:-1]
        self.Shade = bool(proxy.Shade)
        self.GlobalIlluminationReach = float(proxy.GlobalIlluminationReach)
        self.VolumetricScatteringBlending = float(proxy.VolumetricScatteringBlending)
        self.VolumeAnisotropy = float(proxy.VolumeAnisotropy)

        # Update UI
        self.color_by = proxy.ColorArrayName[1]
        self.reset_color_range()

    def push(self):
        proxy = getattr(self, "proxy", None)
        if proxy is None:
            return

        proxy.InterpolationType = self.InterpolationType
        proxy.Shade = int(self.Shade)
        proxy.GlobalIlluminationReach = self.GlobalIlluminationReach
        proxy.VolumetricScatteringBlending = self.VolumetricScatteringBlending
        proxy.VolumeAnisotropy = self.VolumeAnisotropy

    @watch(
        "color_by",
        "color_range",
        "color_preset",
        "color_preset_inverted",
    )
    def _on_color_change(self, color_by, color_range, color_preset, invert):
        proxy = getattr(self, "proxy", None)
        if proxy is None:
            return

        if color_by:
            lut = simple.GetColorTransferFunction(color_by)
            pwf = simple.GetOpacityTransferFunction(color_by)
            pwf.Points = [
                color_range[0],  # scalar
                0.0,  # opacity
                0.5,  # bias 1
                0,  # bias 2
                color_range[1],  # scalar
                1.0,  # opacity
                0.5,  # bias 1
                0,  # bias 2
            ]

            simple.AssignFieldToColorPreset(color_by, color_preset)
            if invert:
                lut.InvertTransferFunction()

            lut.RescaleTransferFunction(*color_range)
            proxy.ColorArrayName = ("POINTS", color_by)
            proxy.LookupTable = lut
            proxy.ScalarOpacityFunction = pwf
        else:
            logger.error("volume rep must be colored by array")

        self.render()

    @watch("Visibility")
    def _on_visibility_change(self, visibility):
        proxy = getattr(self, "proxy", None)
        if proxy is None:
            return

        proxy.Visibility = int(visibility)
        self.render()

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

    def render(self):
        get_instance(self.View).render()

    def reset_camera(self):
        get_instance(self.View).render()

    def reset_color_range(self):
        proxy = getattr(self, "proxy", None)
        if proxy is None:
            return

        # Update data related info
        source_proxy = proxy.Input
        array = source_proxy.GetPointDataInformation().GetArray(self.color_by)
        self.color_range = array.GetRange()
        self.use_color_range_as_bounds()

    def use_color_range_as_bounds(self):
        v_min, v_max = self.color_range
        step = (v_max - v_min) / 255
        self.color_range_bounds = (v_min, v_max, step)


class VolumeRepresentation(TrameComponent):
    def __init__(self, pipeline_manager, source_info, view_info):
        source_id, source_proxy = source_info
        view_id, view_proxy = view_info
        super().__init__(server=pipeline_manager.server)
        self.props = VolumeProperties(
            self.server,
            Input=source_id,
            Label=RepresentationType.VOLUME.label,
            Type=RepresentationType.VOLUME.name,
            Icon=RepresentationType.VOLUME.icon,
            View=view_id,
        )
        self._pm = pipeline_manager
        self.proxy = servermanager._getPyProxy(
            self._pm.pxm.NewProxy(
                "representations",
                "UniformGridVolumeRepresentation",
            )
        )

        self.proxy.Input = source_proxy
        view_proxy.Representations = [*view_proxy.Representations, self.proxy]

        self.props.proxy = self.proxy
        self.props.pull()
        self.props.reset_camera()
