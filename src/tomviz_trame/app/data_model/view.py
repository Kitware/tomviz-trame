from paraview import servermanager
from trame.app.dataclass import (
    ServerOnly,
    StateDataModel,
    Sync,
    watch,
)
from trame.widgets.paraview import VtkRemoteView


class WindowInternalState(StateDataModel):
    color = Sync(str)
    interactive_3d = Sync(bool, True)
    expanded = Sync(bool, False)
    orientation_axes_visibility = Sync(bool, True)
    center_axes_visibility = Sync(bool, False)
    pv_view = ServerOnly(servermanager.Proxy | None)
    widget_view = ServerOnly(VtkRemoteView)

    @watch("interactive_3d")
    def _on_change(self, interactive_3d):
        if self.pv_view is None or self.widget_view is None:
            return

        if interactive_3d:
            self.pv_view.InteractionMode = "3D"
        else:
            self.pv_view.InteractionMode = "2D"

        self.widget_view.update()

    @watch("orientation_axes_visibility")
    def _on_axes_visibility(self, orientation_axes_visibility):
        if self.pv_view is None or self.widget_view is None:
            return

        self.pv_view.OrientationAxesVisibility = int(orientation_axes_visibility)
        self.widget_view.update()

    @watch("center_axes_visibility")
    def _on_center_visibility(self, center_axes_visibility):
        if self.pv_view is None or self.widget_view is None:
            return

        self.pv_view.CenterAxesVisibility = int(center_axes_visibility)
        self.widget_view.update()

    def render(self):
        if self.widget_view is None:
            return
        self.widget_view.update()

    def reset_camera(self):
        if self.widget_view is None:
            return
        self.widget_view.reset_camera()
