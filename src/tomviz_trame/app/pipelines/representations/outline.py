from __future__ import annotations

from paraview import servermanager
from trame_client.widgets.core import TrameComponent

from tomviz_trame.app import data_model
from tomviz_trame.app.pipelines.core import RepresentationType


class OutlineRepresentation(TrameComponent):
    def __init__(
        self, pipeline_manager, source_proxy: data_model.SourceProxy, view_info
    ):
        source_id = source_proxy._id
        view_id, view_proxy = view_info
        super().__init__(server=pipeline_manager.server)
        self.props = data_model.OutlineProperties(
            self.server,
            Input=source_id,
            Label=RepresentationType.OUTLINE.label,
            Type=RepresentationType.OUTLINE.name,
            Icon=RepresentationType.OUTLINE.icon,
            View=view_id,
            source=source_proxy,
        )
        self._pm = pipeline_manager
        self.proxy = servermanager._getPyProxy(
            self._pm.pxm.NewProxy(
                "representations",
                "OutlineRepresentation",
            )
        )

        self.proxy.Input = source_proxy.proxy
        view_proxy.Representations = [*view_proxy.Representations, self.proxy]

        self.props.proxy = self.proxy
        self.props.pull()
        self.props.reset_camera()


RepresentationType.OUTLINE.register_class(OutlineRepresentation)
