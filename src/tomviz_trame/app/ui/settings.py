from trame.widgets import html
from trame.widgets import vuetify3 as v3


class SettingsDialog(v3.VDialog):
    def __init__(self):
        super().__init__(
            v_model=("show_settings", False),
            contained=True,
        )

        with self:
            with v3.VCard(
                classes="mx-auto",
                rounded="lg",
                max_height="80vh",
                max_width="800px",
                width="80vw",
            ):
                with v3.VCardItem(title="Settings", classes=""):
                    with v3.Template(v_slot_prepend=True):
                        v3.VSwitch(
                            # label=("`Theme ${theme}`",),
                            v_model="theme",
                            true_value="light",
                            true_icon="mdi-weather-sunny",
                            false_value="dark",
                            false_icon="mdi-weather-night",
                            inset=True,
                            density="comfortable",
                            hide_details=True,
                        )
                    with v3.Template(v_slot_append=True):
                        if self.server.hot_reload:
                            v3.VBtn(
                                icon="mdi-refresh",
                                click=self.ctrl.on_server_reload,
                                density="compact",
                                variant="plain",
                                classes="mx-2",
                            )

                        v3.VBtn(
                            icon="mdi-close",
                            density="compact",
                            variant="plain",
                            click="show_settings = false",
                        )
                v3.VDivider()
                with v3.VCardText():
                    html.Label("Operators search paths", classes="text-subtitle-2")

                    with v3.VList(
                        density="compact",
                        items=("settings_operators_paths", ["~/.tomviz/operators"]),
                        border="thin",
                        rounded=True,
                        classes="my-1",
                    ):
                        with v3.Template(v_slot_item="{ props }"):
                            with v3.VListItem(title=("props.title",)):
                                with v3.Template(v_slot_append=True):
                                    v3.VBtn(
                                        icon="mdi-trash-can-outline",
                                        density="compact",
                                        variant="plain",
                                        click="settings_operators_paths = settings_operators_paths.filter(v => v !== props.title)",
                                    )
                    v3.VTextField(
                        v_model=("settings_operators_path", ""),
                        append_inner_icon="mdi-plus",
                        variant="outlined",
                        density="compact",
                        hide_details=True,
                        click_appendInner="settings_operators_paths = [...settings_operators_paths, settings_operators_path]; settings_operators_path = '';",
                    )
