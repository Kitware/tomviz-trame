from paraview import servermanager
from trame_client.widgets.core import TrameComponent
from trame_dataclass.core import StateDataModel, get_instance, watch

from .core import RepresentationType


class OutlineProperties(StateDataModel):
    Input: str  # id of SourceProxy
    Label: str
    Type: str
    Icon: str
    Visibility: bool
    View: str

    def pull(self):
        proxy = getattr(self, "proxy", None)
        if proxy is None:
            return

        self.Visibility = bool(proxy.Visibility)

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


class OutlineRepresentation(TrameComponent):
    def __init__(self, pipeline_manager, source_info, view_info):
        source_id, source_proxy = source_info
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
        self._pm = pipeline_manager
        self.proxy = servermanager._getPyProxy(
            self._pm.pxm.NewProxy(
                "representations",
                "OutlineRepresentation",
            )
        )

        self.proxy.Input = source_proxy
        view_proxy.Representations = [*view_proxy.Representations, self.proxy]

        self.props.proxy = self.proxy
        self.props.pull()
        self.props.reset_camera()
