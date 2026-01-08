from trame.widgets import html
from trame.widgets import vuetify3 as v3


class SettingsDialog(v3.VDialog):
    def __init__(self):
        super().__init__(
            v_model=("show_settings", False),
            contained=True,
        )

        with self:
            with v3.VCard(rounded="lg", min_height="80vh"):
                with v3.VCardItem():
                    v3.VCardTitle("Settings")
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
                    with v3.VRow():
                        with v3.VCol(cols=12, md=6):
                            with v3.VRow(classes="pb-2"):
                                with v3.VCol():
                                    v3.VSwitch(
                                        label=("`Theme ${theme}`",),
                                        v_model="theme",
                                        true_value="light",
                                        true_icon="mdi-weather-sunny",
                                        false_value="dark",
                                        false_icon="mdi-weather-night",
                                        inset=True,
                                        density="comfortable",
                                        hide_details=True,
                                    )
                                with v3.VCol():
                                    v3.VSwitch(
                                        label=(
                                            "`DataSet ${settings_keep_dataset ? 'persistent' : 'minimal'}`",
                                        ),
                                        v_model=("settings_keep_dataset", False),
                                        true_icon="mdi-database-plus",
                                        false_icon="mdi-database-remove",
                                        inset=True,
                                        density="comfortable",
                                        hide_details=True,
                                    )
                            v3.VSelect(
                                label="Execution model",
                                v_model=("settings_exec_model", "paraview"),
                                variant="outlined",
                                items=(
                                    "settings_exec_models",
                                    [
                                        {
                                            "title": "ParaView execution",
                                            "value": "paraview",
                                        },
                                        {
                                            "title": "Python environment",
                                            "value": "python",
                                        },
                                    ],
                                ),
                                density="comfortable",
                                hide_details=True,
                                classes="mt-2",
                            )
                        with v3.VCol(cols=12, md=6):
                            html.Label(
                                "Operators search paths", classes="text-subtitle-2"
                            )

                            with v3.VList(
                                density="compact",
                                items=("settings_operators_paths", []),
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
