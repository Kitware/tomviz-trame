from paraview import simple
from trame.widgets import paraview as pvw
from trame.widgets import vuetify3 as v3
from trame_dataclass.core import StateDataModel, watch

VIEW_COLORS = [
    "#2196F3",  # blue
    "#4CAF50",  # green
    "#009688",  # teal
    "#FF9800",  # orange
]


def color_generator():
    while True:
        yield from VIEW_COLORS


COLOR_GENERTOR = color_generator()


def next_color():
    return next(COLOR_GENERTOR)


class WindowInternalState(StateDataModel):
    color: str
    interactive_3d: bool = True
    expanded: bool = False
    orientation_axes_visibility: bool = True
    center_axes_visibility: bool = False
    # pv_view: object | None = field(mode=FieldMode.SERVER_ONLY)
    # widget_view: object | None = field(mode=FieldMode.SERVER_ONLY)

    @watch("interactive_3d")
    def _on_change(self, interactive_3d):
        pv_view = getattr(self, "pv_view", None)
        widget_view = getattr(self, "widget_view", None)
        if pv_view is None or widget_view is None:
            return

        if interactive_3d:
            pv_view.InteractionMode = "3D"
        else:
            pv_view.InteractionMode = "2D"

        widget_view.update()

    @watch("orientation_axes_visibility")
    def _on_axes_visibility(self, orientation_axes_visibility):
        pv_view = getattr(self, "pv_view", None)
        widget_view = getattr(self, "widget_view", None)
        if pv_view is None or widget_view is None:
            return

        pv_view.OrientationAxesVisibility = int(orientation_axes_visibility)
        widget_view.update()

    @watch("center_axes_visibility")
    def _on_center_visibility(self, center_axes_visibility):
        pv_view = getattr(self, "pv_view", None)
        widget_view = getattr(self, "widget_view", None)
        if pv_view is None or widget_view is None:
            return

        pv_view.CenterAxesVisibility = int(center_axes_visibility)
        widget_view.update()

    def render(self):
        view = getattr(self, "widget_view", None)
        if view is None:
            return
        view.update()

    def reset_camera(self):
        view = getattr(self, "widget_view", None)
        if view is None:
            return
        view.reset_camera()


class RenderWindow(v3.VCard):
    def __init__(self, **kwargs):
        super().__init__(
            tile=True,
            classes="w-100 h-100 position-relative pl-1",
            **kwargs,
        )
        self.pv_view = simple.CreateRenderView()
        self.pv_view.GetRenderWindow().SetOffScreenRendering(True)
        self.local_state = WindowInternalState(self.server, color=next_color())
        self.style = f"background: {self.local_state.color};"

        # Make new view active by default
        self.state.active_view_id = self.local_state._id

        with self:
            with self.local_state.provide_as("rw_data"):
                self.window = pvw.VtkRemoteView(
                    self.pv_view,
                    interactive_ratio=1,
                    interactor_events=("['EndAnimation', 'LeftButtonPress']",),
                    LeftButtonPress="active_view_id = rw_data._id",
                )
                with v3.VCard(
                    style=(
                        "`right:1rem;top:1rem;z-index:1;width:${rw_data.expanded ? '4.5' : '2.25'}rem;background:${rw_data.color}`",
                    ),
                    classes="position-absolute",
                    rounded="lg",
                ):
                    with v3.VRow(
                        dense=True,
                        classes="pa-1",
                        v_if="rw_data_available",
                    ):
                        for icon, action, add_on, add_on_btn in self.tools:
                            with v3.VCol(
                                cols=("rw_data.expanded ? 6 : 12",),
                                align_self="center",
                                classes="d-flex justify-center",
                                **add_on,
                            ):
                                v3.VBtn(
                                    icon=icon,
                                    density="compact",
                                    click=action,
                                    **{
                                        "classes": "rounded",
                                        "variant": "plain",
                                        **add_on_btn,
                                    },
                                )

                    v3.VBtn(
                        icon=(
                            "rw_data.expanded ? 'mdi-chevron-up' : 'mdi-chevron-down'",
                        ),
                        block=True,
                        tile=True,
                        variant="plain",
                        density="compact",
                        size="x-small",
                        click="rw_data.expanded = !rw_data.expanded",
                    )

        # Attach pv + widget on state
        self.local_state.pv_view = self.pv_view
        self.local_state.widget_view = self.window

    @property
    def tools(self):
        ALWAYS = EMPTY = {}
        EXPANDED = {"v_if": "rw_data.expanded"}
        return [
            ("mdi-crop-free", self.reset_camera, ALWAYS, EMPTY),
            (
                ("rw_data?.interactive_3d ? 'mdi-rotate-orbit' : 'mdi-pan'",),
                "rw_data.interactive_3d = !rw_data.interactive_3d",
                EXPANDED,
                EMPTY,
            ),
            (
                "mdi-axis",
                "rw_data.orientation_axes_visibility = !rw_data.orientation_axes_visibility",
                EXPANDED,
                {
                    "classes": "rounded border-thin",
                    "variant": (
                        "rw_data.orientation_axes_visibility ? 'tonal' : 'plain'",
                    ),
                },
            ),
            (
                "mdi-image-filter-center-focus",
                "rw_data.center_axes_visibility = !rw_data.center_axes_visibility",
                EXPANDED,
                {
                    "classes": "rounded border-thin",
                    "variant": ("rw_data.center_axes_visibility ? 'tonal' : 'plain'",),
                },
            ),
            ("mdi-rotate-left", (self.rotate, "[90]"), EXPANDED, EMPTY),
            ("mdi-rotate-right", (self.rotate, "[-90]"), EXPANDED, EMPTY),
            (
                "mdi-axis-arrow",
                (self.reset_camera_orientation, "['ApplyIsometricView']"),
                EXPANDED,
                EMPTY,
            ),
            (
                "mdi-axis-x-arrow",
                (self.reset_camera_orientation, "['ResetActiveCameraToPositiveX']"),
                EXPANDED,
                EMPTY,
            ),
            (
                "mdi-axis-y-arrow",
                (self.reset_camera_orientation, "['ResetActiveCameraToPositiveY']"),
                EXPANDED,
                EMPTY,
            ),
            (
                "mdi-axis-z-arrow",
                (self.reset_camera_orientation, "['ResetActiveCameraToPositiveZ']"),
                EXPANDED,
                EMPTY,
            ),
        ]

    def reset_camera(self):
        self.window.reset_camera()

    def render(self):
        self.window.update()

    def rotate(self, angle):
        self.pv_view.AdjustRoll(angle)
        self.render()

    def reset_camera_orientation(self, action):
        getattr(self.pv_view, action)()
        self.reset_camera()
