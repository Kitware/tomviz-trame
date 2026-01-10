from trame.app import TrameApp
from trame.ui.vuetify3 import VAppLayout
from trame.widgets import html
from trame.widgets import vuetify3 as v3

from tomviz_trame.app import cli, module, ui
from tomviz_trame.app.operators import Operators
from tomviz_trame.app.pipelines import PipelineManager


class Tomviz(TrameApp):
    def __init__(self, server=None):
        super().__init__(server, client_type="vue3", ctx_name="tomviz")
        self.server.enable_module(module)
        args = cli.configure(self.server.cli)

        # Global helper
        self.ctx.pipeline = PipelineManager(server=self.server)
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
        self.state.trame__favicon = f"{module.BASENAME}/assets/tomviz/favicon.png"

        if self.server.hot_reload:
            ui.reload(ui)

        # Create UI for all representation types
        ui.initialize_dynamic_ui(self.server)

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
            ui.Toolbar()

            # Left Drawer
            with v3.VNavigationDrawer(
                v_model=("show_drawer", True),
                width=350,
                floating=True,
                disable_resize_watcher=True,
                permanent=True,
            ):
                with html.Div(
                    classes="px-2 pt-2 d-flex flex-column",
                    style="max-height: calc(100vh - 48px)",
                ):
                    ui.PipelineSection()
                    ui.DataInformationSection()
                    ui.PropertiesSections()

            # Main content
            with v3.VMain():
                with v3.VRow(no_gutter=True, classes="pa-0 ma-0 h-100"):
                    with v3.VCol(classes="pa-0"):
                        ui.RenderWindow()
                    with v3.VCol(classes="pa-0"):
                        ui.RenderWindow()
