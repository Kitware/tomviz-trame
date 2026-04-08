from __future__ import annotations

from paraview import servermanager
from trame_client.widgets.core import TrameComponent

from tomviz_trame.app import data_model
from tomviz_trame.app.pipelines.core import RepresentationType


class SliceRepresentation(TrameComponent):
    def __init__(
        self,
        pipeline_manager,
        source_proxy: data_model.SourceProxy,
        view: data_model.WindowInternalState,
    ):
        view_proxy = view.pv_view
        super().__init__(server=pipeline_manager.server)

        self._pm = pipeline_manager
        self.proxy = servermanager._getPyProxy(
            self._pm.pxm.NewProxy(
                "representations",
                "ImageSliceRepresentation",
            )
        )
        self.proxy.Input = source_proxy.proxy
        view_proxy.Representations = [*view_proxy.Representations, self.proxy]

        self.props = data_model.SliceProperties(
            self.server,
            input=source_proxy,
            view=view,
            proxy=self.proxy,
            **RepresentationType.SLICE.props,
        )


RepresentationType.SLICE.register_class(SliceRepresentation)
