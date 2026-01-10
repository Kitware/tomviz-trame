from loguru import logger
from paraview import servermanager, simple
from trame_client.widgets.core import TrameComponent
from trame_dataclass.core import StateDataModel, get_instance, watch

from .core import RepresentationType, extract_arrays


class SliceProperties(StateDataModel):
    Input: str  # id of SourceProxy
    Label: str
    Type: str
    Icon: str
    Visibility: bool
    View: str
    Dimensions: tuple[int, int, int] = (0, 0, 0)
    Slice: int
    SliceMax: int
    SliceDirection: str = "XY Plane"
    SliceDirections: tuple[str, str, str] = ("YZ Plane", "XZ Plane", "XY Plane")
    ColorArrayName: str
    ArrayNames: list[str]
    ColorPreset: str = "Fast"

    def pull(self):
        proxy = getattr(self, "proxy", None)
        if proxy is None:
            return

        # Update data related info
        source_proxy = proxy.Input
        source_proxy.UpdatePipeline()

        logger.debug("slice input {}", source_proxy)
        logger.debug("slice points info {}", source_proxy.GetPointDataInformation())

        self.ArrayNames = extract_arrays(source_proxy.GetPointDataInformation())
        extent = proxy.Input.GetDataInformation().DataInformation.GetExtent()
        self.Dimensions = (
            extent[1] - extent[0],
            extent[3] - extent[2],
            extent[5] - extent[4],
        )
        logger.debug("extent {}", extent)
        logger.debug("Dimensions {}", self.Dimensions)

        # Update representation info
        self.Visibility = bool(proxy.Visibility)
        self.Slice = proxy.Slice
        self.SliceDirection = proxy.SliceDirection
        self.ColorArrayName = proxy.ColorArrayName[1]

        # Update max slice
        self._on_direction_change(self.SliceDirection)

    def push(self):
        proxy = getattr(self, "proxy", None)
        if proxy is None:
            return

        proxy.SliceDirection = self.SliceDirection
        proxy.Slice = self.Slice

    @watch("SliceDirection")
    def _on_direction_change(self, direction):
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

    @watch("ColorArrayName", "ColorPreset")
    def _on_color_change(self, array_name, preset):
        proxy = getattr(self, "proxy", None)
        if proxy is None:
            return

        lut = simple.GetColorTransferFunction(array_name)
        simple.AssignFieldToColorPreset(array_name, preset)
        proxy.ColorArrayName = ("POINTS", array_name)  # FIXME points/cells?
        proxy.LookupTable = lut

        self.render()

    @watch("Visibility")
    def _on_visibility_change(self, visibility):
        proxy = getattr(self, "proxy", None)
        if proxy is None:
            return

        proxy.Visibility = int(visibility)
        self.render()

    def render(self):
        get_instance(self.View).render()

    def reset_camera(self):
        get_instance(self.View).render()


class SliceRepresentation(TrameComponent):
    def __init__(self, pipeline_manager, source_info, view_info):
        source_id, source_proxy = source_info
        view_id, view_proxy = view_info
        super().__init__(server=pipeline_manager.server)
        self.props = SliceProperties(
            self.server,
            Input=source_id,
            Label=RepresentationType.SLICE.label,
            Type=RepresentationType.SLICE.name,
            Icon=RepresentationType.SLICE.icon,
            View=view_id,
        )
        self._pm = pipeline_manager
        self.proxy = servermanager._getPyProxy(
            self._pm.pxm.NewProxy(
                "representations",
                "ImageSliceRepresentation",
            )
        )

        self.proxy.Input = source_proxy
        view_proxy.Representations = [*view_proxy.Representations, self.proxy]
        self.props.proxy = self.proxy
        self.props.pull()
        self.props.reset_camera()
