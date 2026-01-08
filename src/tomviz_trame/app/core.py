import time
from pathlib import Path

from paraview import simple
from trame.app import TrameApp
from trame.ui.vuetify3 import VAppLayout
from trame.widgets import html
from trame.widgets import vuetify3 as v3

from tomviz_trame.app import ui
from tomviz_trame.app.assets import ASSETS
from tomviz_trame.app.operators import Operators
from tomviz_trame.app.representations import ORDER as representations_names

PIPELINES = [
    {
        "id": 1,
        "title": "Applications :",
        "children": [
            {"id": 2, "title": "Calendar : app"},
            {"id": 3, "title": "Chrome : app"},
            {"id": 4, "title": "Webstorm : app"},
        ],
    },
    {
        "id": 5,
        "title": "Documents :",
        "children": [
            {
                "id": 6,
                "title": "vuetify :",
                "children": [
                    {
                        "id": 7,
                        "title": "src :",
                        "children": [
                            {"id": 8, "title": "index : ts"},
                            {"id": 9, "title": "bootstrap : ts"},
                        ],
                    },
                ],
            },
            {
                "id": 10,
                "title": "material2 :",
                "children": [
                    {
                        "id": 11,
                        "title": "src :",
                        "children": [
                            {"id": 12, "title": "v-btn : ts"},
                            {"id": 13, "title": "v-card : ts"},
                            {"id": 14, "title": "v-window : ts"},
                        ],
                    },
                ],
            },
        ],
    },
    {
        "id": 15,
        "title": "Downloads :",
        "children": [
            {"id": 16, "title": "October : pdf"},
            {"id": 17, "title": "November : pdf"},
            {"id": 18, "title": "Tutorial : html"},
        ],
    },
    {
        "id": 19,
        "title": "Videos :",
        "children": [
            {
                "id": 20,
                "title": "Tutorials :",
                "children": [
                    {"id": 21, "title": "Basic layouts : mp4"},
                    {"id": 22, "title": "Advanced techniques : mp4"},
                    {"id": 23, "title": "All about app : dir"},
                ],
            },
            {"id": 24, "title": "Intro : mov"},
            {"id": 25, "title": "Conference introduction : avi"},
        ],
    },
]


class Tomviz(TrameApp):
    def __init__(self, server=None):
        super().__init__(server, client_type="vue3", ctx_name="tomviz")

        # CLI
        self.server.cli.add_argument(
            "--operators",
            help="Path to the operators configuration file",
        )
        self.server.cli.add_argument(
            "--read-only",
            action="store_true",
            help="Disable operators modifications",
        )
        args, _ = self.server.cli.parse_known_args()

        # Global helper
        self.ctx.operators = Operators(
            server=self.server,
            config_file=args.operators,
            read_only=args.read_only,
        )

        # --hot-reload arg optional logic
        if self.server.hot_reload:
            self.server.controller.on_server_reload.add(self._build_ui)

        # build ui
        self._build_ui()

    def _build_ui(self, **_):
        self.state.trame__title = "tomviz"
        self.state.trame__favicon = ASSETS.favicon

        if self.server.hot_reload:
            ui.reload(ui)

        with VAppLayout(
            self.server,
            full_height=True,
            theme=("theme", "light"),
        ) as self.ui:
            if self.server.hot_reload:
                v3.VBtn(
                    icon="mdi-refresh",
                    classes="position-absolute rounded",
                    density="comfortable",
                    style="right:1rem;bottom:1rem;z-index:1;",
                    click=self.server.controller.on_server_reload,
                )

            # Dialogs
            ui.FileLoader()
            ui.SettingsDialog()

            # Toolbar
            with v3.VAppBar(density="compact"):
                v3.VProgressLinear(
                    v_show="trame__busy",
                    indeterminate=True,
                    absolute=True,
                    height=3,
                    color="red-darken-1",
                    location="bottom",
                )
                with html.Div(
                    classes="position-absolute",
                    style="pointer-events: none; left: -5px;",
                ):
                    v3.VIcon("mdi-chevron-left", v_if="show_drawer")
                    v3.VIcon("mdi-chevron-right", v_else=True)
                html.Img(
                    v_if="theme === 'dark'",
                    src=ASSETS.title_dark,
                    height="100%",
                    classes="pa-2 ml-1",
                    click="show_drawer = !show_drawer",
                )
                html.Img(
                    v_else=True,
                    src=ASSETS.title,
                    height="100%",
                    classes="pa-2 ml-1",
                    click="show_drawer = !show_drawer",
                )
                v3.VSpacer()

                # Data open
                ui.toolbar_btn(
                    "d_open",
                    v_tooltip_bottom="'Open data file'",
                    click="tomviz_file_loader = true",
                )

                # Data operators
                ui.toolbar_btn(
                    "d_operator",
                    v_tooltip_bottom="'Select operator'",
                    click=self.fake_busy,
                )

                v3.VDivider(vertical=True, classes="mr-2")

                # Representations
                for rep_name, tooltip in representations_names:
                    ui.toolbar_btn(f"r_{rep_name}", v_tooltip_bottom=f"'{tooltip}'")

                v3.VDivider(vertical=True, classes="mr-2")

                # Settings
                ui.toolbar_btn(
                    "Settings",
                    v_tooltip_bottom="'Edit settings'",
                    click="show_settings = true",
                )

            # Left Drawer
            with v3.VNavigationDrawer(
                v_model=("show_drawer", True),
                width=300,
                floating=True,
                disable_resize_watcher=True,
                permanent=True,
            ):
                with html.Div(
                    classes="px-2 pt-2 d-flex flex-column",
                    style="max-height: calc(100vh - 48px)",
                ):
                    v3.VBtn(
                        prepend_icon=(
                            "show_pipeline ? 'mdi-chevron-down' : 'mdi-chevron-up'",
                        ),
                        text="Pipelines",
                        click="show_pipeline = !show_pipeline",
                        classes="w-100 text-none mb-1",
                        variant="tonal",
                        spaced="end",
                    )
                    with v3.VCard(
                        classes="border-thin overflow-auto flex-fill mb-2",
                        flat=True,
                        variant="flat",
                        v_show=("show_pipeline", True),
                    ):
                        v3.VTreeview(
                            density="compact",
                            items=("pipelines", PIPELINES),
                            item_value="id",
                        )
                    v3.VBtn(
                        prepend_icon=(
                            "show_properties ? 'mdi-chevron-down' : 'mdi-chevron-up'",
                        ),
                        text="Properties",
                        click="show_properties = !show_properties",
                        classes="w-100 text-none mb-1",
                        variant="tonal",
                        spaced="end",
                    )
                    with v3.VCard(
                        classes="border-thin overflow-auto flex-fill mb-2",
                        flat=True,
                        variant="flat",
                        v_show=("show_properties", True),
                    ):
                        html.Div(
                            style="height: calc(50vh)",
                        )

                    v3.VBtn(
                        prepend_icon=(
                            "show_informations ? 'mdi-chevron-down' : 'mdi-chevron-up'",
                        ),
                        text="Information",
                        click="show_informations = !show_informations",
                        classes="w-100 text-none mb-1",
                        variant="tonal",
                        spaced="end",
                    )
                    with v3.VCard(
                        classes="border-thin overflow-auto flex-fill mb-2",
                        flat=True,
                        variant="flat",
                        v_show=("show_informations", True),
                    ):
                        html.Div(
                            style="height: calc(50vh)",
                        )

            # Main content
            with v3.VMain(classes="bg-red"):
                ui.RenderWindow(ctx_name="view")

    def open_file(self, file_path):
        name = Path(file_path).stem
        reader = simple.TIFFSeriesReader(
            registrationName=name,
            FileNames=[str(file_path)],
        )
        simple.Show(reader, self.ctx.view.pv_view)
        self.ctx.view.reset_camera()

    def fake_busy(self):
        time.sleep(2)
