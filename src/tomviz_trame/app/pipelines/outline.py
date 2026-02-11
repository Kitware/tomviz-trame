from paraview import servermanager
from trame_client.widgets.core import TrameComponent
from trame_dataclass.core import StateDataModel, get_instance, watch

from tomviz_trame.app.pipelines.source import SourceProxy
from tomviz_trame.app.pipelines.core import RepresentationProperties, RepresentationPropertiesContext, RepresentationType


class OutlineProperties(RepresentationProperties, StateDataModel):
    Input: str  # id of SourceProxy
    Label: str
    Type: str
    Icon: str
    Visibility: bool
    View: str

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.ctx = RepresentationPropertiesContext()

    def pull(self):
        proxy = self.ctx.proxy

        if proxy is None:
            return

        self.Visibility = bool(proxy.Visibility)

    @watch("Visibility")
    def _on_visibility_change(self, visibility):
        proxy = self.ctx.proxy

        if proxy is None:
            return

        proxy.Visibility = int(visibility)
        self.render()

    def render(self):
        get_instance(self.View).render()

    def reset_camera(self):
        get_instance(self.View).render()


class OutlineRepresentation(TrameComponent):
    def __init__(self, pipeline_manager, source_proxy: SourceProxy, view_info):
        source_id = source_proxy._id
        view_id, view_proxy = view_info
        super().__init__(server=pipeline_manager.server)
        self.props = OutlineProperties(
            self.server,
            Input=source_id,
            Label=RepresentationType.OUTLINE.label,
            Type=RepresentationType.OUTLINE.name,
            Icon=RepresentationType.OUTLINE.icon,
            View=view_id,
        )
        self.props.ctx.source = source_proxy
        self._pm = pipeline_manager
        self.proxy = servermanager._getPyProxy(
            self._pm.pxm.NewProxy(
                "representations",
                "OutlineRepresentation",
            )
        )

        self.proxy.Input = source_proxy.ctx.proxy
        view_proxy.Representations = [*view_proxy.Representations, self.proxy]

        self.props.ctx.proxy = self.proxy
        self.props.pull()
        self.props.reset_camera()
