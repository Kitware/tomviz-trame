from __future__ import annotations

from trame.app.dataclass import (
    ServerOnly,
    StateDataModel,
    Sync,
    watch,
)
from trame.widgets.vtk import VtkRemoteView

from tomviz_trame.app.pipeline.vtk.view import View


class ViewModel(StateDataModel):
    """UI state of one render window, wrapping the VTK ``View`` and the
    ``VtkRemoteView`` widget that streams it."""

    color = Sync(str)
    interactive_3d = Sync(bool, True)
    expanded = Sync(bool, False)
    orientation_axes_visibility = Sync(bool, True)
    center_axes_visibility = Sync(bool, False)
    vtk_view = ServerOnly(View | None)
    widget_view = ServerOnly(VtkRemoteView)

    @watch("interactive_3d")
    def _on_change(self, interactive_3d):
        if self.vtk_view is None or self.widget_view is None:
            return

        if interactive_3d:
            self.vtk_view.interaction_mode = "3D"
        else:
            self.vtk_view.interaction_mode = "2D"

        self.widget_view.update()

    @watch("orientation_axes_visibility")
    def _on_axes_visibility(self, orientation_axes_visibility):
        if self.vtk_view is None or self.widget_view is None:
            return

        self.vtk_view.orientation_axes_visibility = bool(orientation_axes_visibility)
        self.widget_view.update()

    @watch("center_axes_visibility")
    def _on_center_visibility(self, center_axes_visibility):
        if self.vtk_view is None or self.widget_view is None:
            return

        self.vtk_view.center_axes_visibility = bool(center_axes_visibility)
        self.widget_view.update()

    def render(self):
        if self.widget_view is None:
            return
        self.widget_view.update()

    def reset_camera(self):
        if self.widget_view is None:
            return
        self.widget_view.reset_camera()
