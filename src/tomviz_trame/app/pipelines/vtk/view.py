import vtkmodules.vtkRenderingOpenGL2  # noqa: F401
from loguru import logger
from vtkmodules.vtkInteractionStyle import vtkInteractorStyleSwitch  # noqa: F401
from vtkmodules.vtkInteractionWidgets import vtkOrientationMarkerWidget
from vtkmodules.vtkRenderingAnnotation import vtkAxesActor
from vtkmodules.vtkRenderingCore import (
    vtkRenderer,
    vtkRenderWindow,
    vtkRenderWindowInteractor,
)


class View:
    ID = 0

    def __init__(self):
        View.ID += 1
        self._id = f"{View.ID}"
        self._interaction_mode = "3D"
        self._orientation_axes = True
        self._center_axes_visibility = False
        self._representations = set()

        self.renderer = vtkRenderer(background=(0.8, 0.8, 0.8))
        self.interactor = vtkRenderWindowInteractor()
        self.render_window = vtkRenderWindow(off_screen_rendering=1)

        self.render_window.AddRenderer(self.renderer)
        self.interactor.SetRenderWindow(self.render_window)
        self.interactor.GetInteractorStyle().SetCurrentStyleToTrackballCamera()

        self.interactor.Initialize()

        axes_actor = vtkAxesActor()
        self.orientation_marker_widget = vtkOrientationMarkerWidget()
        self.orientation_marker_widget.SetOrientationMarker(axes_actor)
        self.orientation_marker_widget.SetInteractor(self.interactor)
        self.orientation_marker_widget.SetViewport(0.85, 0, 1, 0.15)
        self.orientation_marker_widget.EnabledOn()
        self.orientation_marker_widget.InteractiveOff()

    @property
    def id(self):
        return self._id

    def adjust_roll(self, angle):
        logger.critical("adjust_roll {}", angle)

    def apply_isometric_view(self):
        logger.critical("apply_isometric_view")

    def reset_active_camera_to_positive_x(self):
        logger.critical("reset_active_camera_to_positive_x")

    def reset_active_camera_to_positive_y(self):
        logger.critical("reset_active_camera_to_positive_y")

    def reset_active_camera_to_positive_z(self):
        logger.critical("reset_active_camera_to_positive_z")

    @property
    def interaction_mode(self):
        return self._interaction_mode

    @interaction_mode.setter
    def interaction_mode(self, mode):
        self._interaction_mode = mode
        logger.critical("interaction_mode {}", mode)
        # FIXME swap style

    @property
    def orientation_axes_visibility(self):
        return self._orientation_axes

    @orientation_axes_visibility.setter
    def orientation_axes_visibility(self, on_off):
        self._orientation_axes = on_off
        # FIXME swap style
        logger.critical("orientation_axes_visibility {}", on_off)

    @property
    def center_axes_visibility(self):
        return self._center_axes_visibility

    @center_axes_visibility.setter
    def center_axes_visibility(self, on_off):
        self._center_axes_visibility = on_off
        # FIXME swap style
        logger.critical("center_axes_visibility {}", on_off)

    @property
    def representations(self):
        return list(self._representations)

    def add_representation(self, representation):
        if representation not in self._representations:
            self._representations.add(representation)
            self.renderer.AddViewProp(representation.actor)

    def remove_representation(self, representation):
        if representation in self._representations:
            self._representations.discard(representation)
            self.renderer.RemoveViewProp(representation.actor)

    def clear(self):
        for rep in list(self._representations):
            self.remove_representation(rep)
