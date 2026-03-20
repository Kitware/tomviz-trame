from paraview import servermanager
from trame_client.widgets.core import TrameComponent
from trame_dataclass.core import StateDataModel, get_instance, watch

from tomviz_trame.app.pipelines.core import RepresentationProperties, RepresentationPropertiesContext, RepresentationType
from tomviz_trame.app.pipelines.source import SourceProxy
from tomviz_trame.app.pipelines.coloropacity import ColorOpacity, create_default_coloropacity


class VolumeProperties(RepresentationProperties, StateDataModel):
    Input: str  # id of SourceProxy
    Label: str
    Type: str
    Icon: str
    Visibility: bool
    View: str

    ColorOpacityId: str # id of the active coloropacity for this representation
    CustomColoropacity: bool # use this representation's coloropacity or the source's coloropacity

    # Volume rep specific
    InterpolationType: str  # Nearest, Linear, Cubic
    Shade: bool
    GlobalIlluminationReach: float = 0  # [0-1]
    VolumetricScatteringBlending: float = 0  # [0-2]
    VolumeAnisotropy: float = 0  # [-1,1]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.ctx = RepresentationPropertiesContext()

    def pull(self):
        proxy = self.ctx.proxy

        if proxy is None:
            return

        # Update representation info
        self.Visibility = bool(proxy.Visibility)
        self.InterpolationType = str(proxy.InterpolationType)[1:-1]
        self.Shade = bool(proxy.Shade)
        self.GlobalIlluminationReach = float(proxy.GlobalIlluminationReach)
        self.VolumetricScatteringBlending = float(proxy.VolumetricScatteringBlending)
        self.VolumeAnisotropy = float(proxy.VolumeAnisotropy)

    def push(self):
        proxy = self.ctx.proxy

        if proxy is None:
            return

        proxy.InterpolationType = self.InterpolationType
        proxy.Shade = int(self.Shade)
        proxy.GlobalIlluminationReach = self.GlobalIlluminationReach
        proxy.VolumetricScatteringBlending = self.VolumetricScatteringBlending
        proxy.VolumeAnisotropy = self.VolumeAnisotropy

    @watch("CustomColoropacity")
    def _on_custom_coloropacity_change(self, custom):
        # unsubscribe from the current coloropacity
        if self.ctx.coloropacity_unwatch_0 is not None:
            self.ctx.coloropacity_unwatch_0()
            self.ctx.coloropacity_unwatch_0 = None

        if self.ctx.coloropacity_unwatch_1 is not None:
            self.ctx.coloropacity_unwatch_1()
            self.ctx.coloropacity_unwatch_1 = None

        coloropacity: ColorOpacity | None

        if custom:
            coloropacity = self.ctx.coloropacity
        else:
            coloropacity = self.ctx.source.ctx.coloropacity

        if coloropacity is None:
            self.ColorOpacityId = ""
            return

        active_coloropacity_id = self.server.state.active_coloropacity_id      

        if active_coloropacity_id == self.ColorOpacityId:
            with self.server.state as s:
                s.active_coloropacity_id = coloropacity._id

        self.ColorOpacityId = coloropacity._id

        self.ctx.coloropacity_unwatch_0 = coloropacity.watch(["active_data_array"], self.on_coloropacity_active_array_change)

        # can this rerender happen automatically when the lut/pwf is modified?
        self.ctx.coloropacity_unwatch_1 = coloropacity.watch(["color_range", "opacities", "active_color_preset", "invert_color_preset"], self.render)

        self.on_coloropacity_active_array_change(coloropacity.active_data_array)

        proxy = self.ctx.proxy

        if proxy is None:
            return

        proxy.LookupTable = coloropacity.ctx.lut
        proxy.ScalarOpacityFunction = coloropacity.ctx.pwf

        self.render()

    def on_coloropacity_active_array_change(self, active_data_array):
        if not active_data_array:
            return

        proxy = self.ctx.proxy

        if proxy is None:
            return
    
        proxy.ColorArrayName = ("POINTS", active_data_array)

    @watch("Visibility")
    def _on_visibility_change(self, visibility):
        proxy = self.ctx.proxy

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

    def render(self, *args):
        get_instance(self.View).render()

    def reset_camera(self):
        get_instance(self.View).render()


class VolumeRepresentation(TrameComponent):
    def __init__(self, pipeline_manager, source_proxy: SourceProxy, view_info):
        source_id = source_proxy._id
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

        self.proxy.Input = source_proxy.ctx.proxy
        view_proxy.Representations = [*view_proxy.Representations, self.proxy]
        self.props.ctx.proxy = self.proxy
        self.props.ctx.source = source_proxy
        coloropacity = create_default_coloropacity(source_proxy)
        self.props.ctx.coloropacity = coloropacity
        self.props._on_custom_coloropacity_change(False) # default to using the upstream source colormap
        self.props.pull()
        self.props.reset_camera()
