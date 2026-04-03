from trame.app import TrameApp
from trame.decorators import life_cycle
from trame.ui.vuetify3 import VAppLayout
from trame.widgets import dataclass, dockview, html
from trame.widgets import paraview as pvw
from trame.widgets import vuetify3 as v3

from tomviz_trame.app import cli, module, ui
from tomviz_trame.app.operators import Operators
from tomviz_trame.app.pipelines import PipelineManager
from tomviz_trame.app.ui.colormaps import generate_colormaps


class Tomviz(TrameApp):
    def __init__(self, server=None):
        super().__init__(server, client_type="vue3", ctx_name="tomviz")
        self.server.enable_module(module)
        args = cli.configure(self.server.cli)

        # Force dataclass initialization to v1
        dataclass.initialize(self.server, version="v1")

        # Global helper
        self.ctx.pipeline = PipelineManager(server=self.server)
        self.ctx.colormaps = generate_colormaps(self.server)
        self.state.colormaps_id = self.ctx.colormaps._id
        self.state.show_coloropacity = True
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

    @life_cycle.client_connected
    def on_client_connected(self, **_):
        self.ctx.pipeline.refresh_views()

    def _build_ui(self, **_):
        self.state.trame__title = "tomviz"
        self.state.trame__favicon = f"{module.BASENAME}/assets/tomviz/favicon.png"

        if self.server.hot_reload:
            ui.reload(ui)

        # Create UI for all representation types

        ui.initialize_dynamic_ui(self.server)
        pvw.initialize(self.server)

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
                    style="right:1rem;bottom:1rem;z-index:10;",
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
                    ui.ColorOpacitySection()
                    ui.PropertiesSections()
                    ui.DataInformationSection()

            # Main content
            with v3.VMain():
                dockview.DockView(
                    ctx_name="dock_view",
                    theme=("theme === 'light' ? 'Light' : 'Dark'",),
                    active_panel=(self.ctx.pipeline.activate_panel, "[$event]"),
                )

        # Add a view if none defined
        if not self.ctx.pipeline.views:
            self.ctx.pipeline.add_view()
