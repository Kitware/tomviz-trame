from __future__ import annotations

from vtkmodules.vtkCommonDataModel import vtkPlane
from vtkmodules.vtkFiltersCore import vtkFlyingEdgesPlaneCutter
from vtkmodules.vtkRenderingCore import (
    vtkActor,
    vtkPolyDataMapper,
)

from tomviz_trame.app import data_model
from tomviz_trame.app.pipeline.representations.core import (
    Representation,
    RepresentationType,
)

# Axis index for each entry of SliceSinkNodeModel.SliceDirections
AXIS_BY_DIRECTION = {
    "YZ Plane": 0,
    "XZ Plane": 1,
    "XY Plane": 2,
}


class SliceRepresentation(Representation):
    def __init__(
        self,
        pipeline_manager,
        source_port: data_model.OutputPortModel,
        view: data_model.ViewModel,
    ):
        super().__init__(pipeline_manager.server)

        self._slice = 0
        self._slice_direction = "XY Plane"

        self.plane = vtkPlane()
        self.extract = vtkFlyingEdgesPlaneCutter(plane=self.plane)
        self.mapper = vtkPolyDataMapper()
        self.actor = vtkActor(mapper=self.mapper)
        self.producer >> self.extract >> self.mapper
        self.attach(view.vtk_view)

        self.model = data_model.SliceSinkNodeModel(
            self.server,
            source_port=source_port,
            view=view,
            representation=self,
            **RepresentationType.SLICE.model_kwargs,
        )

    def set_input(self, image):
        super().set_input(image)
        self._update_plane()

    @property
    def Slice(self):
        return self._slice

    @Slice.setter
    def Slice(self, value):
        self._slice = value
        self._update_plane()

    @property
    def SliceDirection(self):
        return self._slice_direction

    @SliceDirection.setter
    def SliceDirection(self, value):
        self._slice_direction = value
        self._update_plane()

    def _update_plane(self):
        image = self.image
        if image is None:
            return

        axis = AXIS_BY_DIRECTION[self._slice_direction]
        extent = image.GetExtent()
        spacing = image.GetSpacing()
        data_origin = image.GetOrigin()

        origin = list(image.GetCenter())
        origin[axis] = (
            data_origin[axis] + (extent[axis * 2] + self._slice) * spacing[axis]
        )

        normal = [0, 0, 0]
        normal[axis] = 1

        self.plane.origin = origin
        self.plane.normal = normal


RepresentationType.SLICE.register_class(SliceRepresentation)
