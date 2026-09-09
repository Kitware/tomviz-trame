from __future__ import annotations

from trame.app.dataclass import (
    ServerOnly,
    StateDataModel,
    Sync,
    watch,
)
from trame.widgets.vtk import VtkRemoteView

from tomviz_trame.app.pipeline.vtk.view import DEFAULT_BACKGROUND, View


class ViewModel(StateDataModel):
    """UI state of one render window, wrapping the VTK ``View`` and the
    ``VtkRemoteView`` widget that streams it.

    ``camera_initialized`` records whether the camera has been placed, by
    the first data that arrived (sinks reset the camera once) or by a
    loaded state; sinks leave a placed camera alone.
    """

    color = Sync(str)
    interactive_3d = Sync(bool, True)
    expanded = Sync(bool, False)
    orientation_axes_visibility = Sync(bool, True)
    center_axes_visibility = Sync(bool, False)
    background = Sync(tuple[float, float, float], DEFAULT_BACKGROUND)
    vtk_view = ServerOnly(View | None)
    widget_view = ServerOnly(VtkRemoteView)

    def __init__(self, server, **kwargs):
        self.camera_initialized = False
        super().__init__(server, **kwargs)

    @watch("interactive_3d")
    def _on_change(self, interactive_3d):
        if self.vtk_view is None or self.widget_view is None:
            return

        self.vtk_view.interaction_mode = "3D" if interactive_3d else "2D"
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

    @watch("background")
    def _on_background(self, background):
        if self.vtk_view is None or self.widget_view is None:
            return

        self.vtk_view.background = tuple(background)
        self.widget_view.update()

    def render(self):
        if self.widget_view is None:
            return
        self.widget_view.update()

    def reset_camera(self):
        if self.widget_view is None:
            return
        self.widget_view.reset_camera()

    def set_camera(self, camera: dict):
        """Place the camera from a state-file ``camera`` block (``position``,
        ``focalPoint``, ``viewUp``, ``viewAngle``, ``parallelScale``) and
        mark it initialized."""
        if self.vtk_view is None:
            return
        self.vtk_view.set_camera(
            position=camera.get("position"),
            focal_point=camera.get("focalPoint"),
            view_up=camera.get("viewUp"),
            view_angle=camera.get("viewAngle"),
            parallel_scale=camera.get("parallelScale"),
            parallel_projection=camera.get("parallelProjection"),
        )
        self.camera_initialized = True
        self.render()
