from __future__ import annotations

from paraview import servermanager
from trame_client.widgets.core import TrameComponent

from tomviz_trame.app import data_model
from tomviz_trame.app.pipelines.core import RepresentationType


class SliceRepresentation(TrameComponent):
    def __init__(
        self, pipeline_manager, source_proxy: data_model.SourceProxy, view_info
    ):
        source_id = source_proxy._id
        view_id, view_proxy = view_info
        super().__init__(server=pipeline_manager.server)
        self.props = data_model.SliceProperties(
            self.server,
            Input=source_id,
            Label=RepresentationType.SLICE.label,
            Type=RepresentationType.SLICE.name,
            Icon=RepresentationType.SLICE.icon,
            View=view_id,
        )
        self.props.source = source_proxy
        self._pm = pipeline_manager
        self.proxy = servermanager._getPyProxy(
            self._pm.pxm.NewProxy(
                "representations",
                "ImageSliceRepresentation",
            )
        )

        self.proxy.Input = source_proxy.proxy
        view_proxy.Representations = [*view_proxy.Representations, self.proxy]
        self.props.proxy = self.proxy
        coloropacity = data_model.create_default_coloropacity(source_proxy)
        self.props.coloropacity = coloropacity
        self.props._on_custom_coloropacity_change(
            False
        )  # default to using the upstream source colormap
        self.props.pull()
        self.props.reset_camera()
