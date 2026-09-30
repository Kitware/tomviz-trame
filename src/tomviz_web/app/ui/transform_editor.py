"""Dialog configuring a catalog node (a transform, or a catalog source): its
label, its definition (the entry's JSON description), its script and its
parameters. Definition and script edits are staged in the dialog's
``TransformEditorModel``; the label and the parameters (Apply) reach the
node directly."""

from loguru import logger
from trame.app.dataclass import StateDataModel, Sync, get_instance
from trame.widgets import code, dataclass, html
from trame.widgets import vuetify3 as v3

from tomviz_web.app.data_model import DataNodeModel

# Parameter types the definition editor offers (the desktop app's list).
PARAMETER_TYPES = [
    "double",
    "int",
    "bool",
    "string",
    "enumeration",
    "file",
    "save_file",
    "directory",
    "select_scalars",
    "xyz_header",
    "dataset",
]
NUMBER_TYPES = "['int', 'double']"
TEXT_TYPES = "['string', 'file', 'save_file', 'directory']"


class TransformEditorModel(StateDataModel):
    """What the dialog edits. ``definition`` is deep reactive, so the
    client's nested edits (a parameter's fields) reach the server."""

    show = Sync(bool, False)
    tab = Sync(str, "parameters")
    transform_id = Sync(str, "")  # the DataNodeModel being configured


def json_field(label, key, **kwargs):
    """Text field editing ``param[key]`` as JSON: the value only changes
    while the text parses."""
    return v3.VTextField(
        label=label,
        model_value=(f"param.{key} === undefined ? '' : JSON.stringify(param.{key})",),
        update_modelValue=(
            "(e) => {"
            "  if(e === '') {"
            f"   delete param.{key};"
            "  } else {"
            "    try {"
            f"     param.{key} = JSON.parse(e);"
            "    } catch (error) {}"
            "  }"
            "}"
        ),
        variant="outlined",
        density="compact",
        hide_details=True,
        **kwargs,
    )


class TransformEditorDialog(html.Div):
    def __init__(self):
        super().__init__()
        self.editor = TransformEditorModel(self.server)
        self.ctrl.open_transform_editor = self.open

        with (
            self,
            self.editor.provide_as("editor"),
            v3.VDialog(v_model="editor.show", contained=True),
            dataclass.Provider(name="transform", instance=("editor.transform_id",)),
        ):
            with v3.VCard(
                classes="mx-auto d-flex flex-column",
                rounded="lg",
                height="80vh",
                max_width="1000px",
                width="80vw",
            ):
                with v3.VCardItem(title=("`Configure - ${transform.label}`",)):
                    with v3.Template(v_slot_append=True):
                        v3.VBtn(
                            icon="mdi-close",
                            density="compact",
                            variant="plain",
                            click="editor.show = false",
                        )
                v3.VDivider()
                with v3.VCardText(classes="flex-0-0 pb-0"):
                    v3.VTextField(
                        label="Name",
                        model_value=("transform.label",),
                        update_modelValue=(self.rename, "[transform._id, $event]"),
                        variant="outlined",
                        density="compact",
                        hide_details=True,
                    )
                with v3.VTabs(
                    v_model="editor.tab",
                    density="compact",
                    classes="flex-0-0 px-4 mt-2",
                ):
                    v3.VTab("Definition", value="definition", classes="text-none")
                    v3.VTab("Script", value="script", classes="text-none")
                    v3.VTab("Parameters", value="parameters", classes="text-none")
                    v3.VTab("Execution", value="execution", classes="text-none")
                v3.VDivider()
                with v3.VTabsWindow(
                    v_model="editor.tab",
                    classes="flex-fill overflow-auto",
                ):
                    with v3.VTabsWindowItem(value="definition", classes="pa-4"):
                        self._definition()

                    with v3.VTabsWindowItem(value="script", classes="h-100"):
                        code.Editor(
                            v_model="transform.script",
                            language="python",
                            theme=("theme === 'light' ? 'vs' : 'vs-dark'",),
                            options=(
                                "{ automaticLayout: true, scrollBeyondLastLine: false }",
                            ),
                            style="height: 100%; min-height: 10px;",
                        )

                    with v3.VTabsWindowItem(value="parameters", classes="pa-4"):
                        self._parameters()
                    v3.VTabsWindowItem(value="execution", classes="pa-4")

    def _definition(self):
        with v3.VRow(dense=True):
            with v3.VCol(cols=6):
                v3.VTextField(
                    label="Name",
                    v_model="transform.definition.name",
                    variant="outlined",
                    density="compact",
                    hide_details=True,
                )
            with v3.VCol(cols=6):
                v3.VTextField(
                    label="Label",
                    v_model="transform.definition.label",
                    variant="outlined",
                    density="compact",
                    hide_details=True,
                )
            with v3.VCol(cols=12):
                v3.VTextarea(
                    label="Description",
                    v_model="transform.definition.description",
                    variant="outlined",
                    density="compact",
                    hide_details=True,
                    rows=2,
                    auto_grow=True,
                )

        with html.Div(classes="d-flex align-center mt-4 mb-2"):
            html.Div("Parameters", classes="text-subtitle-2")
            v3.VSpacer()
            v3.VBtn(
                "Add Parameter",
                prepend_icon="mdi-plus",
                classes="text-none",
                density="compact",
                variant="tonal",
                click=(
                    "transform.definition.parameters = [...(transform.definition.parameters || []), "
                    "{ name: `param_${(transform.definition.parameters || []).length}`, "
                    "type: 'double', default: 0 }]"
                ),
            )
            v3.VBtn(
                "Apply Edits",
                prepend_icon="mdi-content-save-outline",
                classes="text-none ml-4",
                density="compact",
                variant="tonal",
                click=(self.save, "[transform._id]"),
            )

        with v3.VExpansionPanels(
            variant="accordion", multiple=True, flat=True, rounded=True, static=True
        ):
            with v3.VExpansionPanel(
                v_for="(param, idx) in (transform.definition.parameters || [])",
                key="idx",
                rounded=True,
                classes="border-thin my-1",
            ):
                with v3.VExpansionPanelTitle():
                    html.Span("{{ param.label || param.name }}")
                    html.Span(
                        "{{ param.name }} · {{ param.type }}",
                        classes="text-caption text-medium-emphasis ml-2",
                    )
                    v3.VSpacer()
                    v3.VBtn(
                        icon="mdi-trash-can-outline",
                        density="compact",
                        variant="plain",
                        classes="mr-2",
                        click_stop="transform.definition.parameters.splice(idx, 1)",
                    )
                with v3.VExpansionPanelText(classes="border-t-thin pt-3"):
                    with v3.VRow(dense=True):
                        with v3.VCol(cols=4):
                            v3.VTextField(
                                label="Name",
                                v_model="param.name",
                                variant="outlined",
                                density="compact",
                                hide_details=True,
                            )
                        with v3.VCol(cols=4):
                            v3.VTextField(
                                label="Label",
                                v_model="param.label",
                                variant="outlined",
                                density="compact",
                                hide_details=True,
                            )
                        with v3.VCol(cols=4):
                            v3.VSelect(
                                label="Type",
                                v_model="param.type",
                                items=(str(PARAMETER_TYPES),),
                                variant="outlined",
                                density="compact",
                                hide_details=True,
                            )
                        with v3.VCol(cols=12):
                            v3.VTextField(
                                label="Description",
                                v_model="param.description",
                                variant="outlined",
                                density="compact",
                                hide_details=True,
                            )

                        # Default value, by type
                        with v3.VCol(cols=12, v_if="param.type === 'bool'"):
                            v3.VSwitch(
                                label="Default",
                                v_model="param.default",
                                density="compact",
                                hide_details=True,
                            )
                        with v3.VCol(
                            cols=12, v_else_if=f"{TEXT_TYPES}.includes(param.type)"
                        ):
                            v3.VTextField(
                                label="Default",
                                v_model="param.default",
                                variant="outlined",
                                density="compact",
                                hide_details=True,
                            )
                        with v3.VCol(
                            cols=12,
                            v_else_if="!['xyz_header', 'dataset', 'select_scalars'].includes(param.type)",
                        ):
                            json_field(
                                "Default (JSON)",
                                "default",
                                placeholder="1.0 or [128, 128, 128]",
                            )

                        # Numeric bounds
                        with v3.Template(v_if=f"{NUMBER_TYPES}.includes(param.type)"):
                            with v3.VCol(cols=3):
                                json_field("Minimum", "minimum")
                            with v3.VCol(cols=3):
                                json_field("Maximum", "maximum")
                            with v3.VCol(cols=3):
                                json_field("Step", "step")
                            with v3.VCol(cols=3):
                                json_field("Precision", "precision")

                        # Enumeration options
                        with v3.VCol(cols=12, v_if="param.type === 'enumeration'"):
                            json_field(
                                "Options (JSON)",
                                "options",
                                placeholder='[{"Linear": 0}, {"Cubic": 1}]',
                            )

    def _parameters(self):
        html.Div(
            "{{ transform.definition.description }}",
            v_if="transform?.definition?.description",
            classes="text-body-2 mb-4",
            style="white-space: pre-wrap;",
        )
        dataclass.Gui(instance=("transform.parameters._id",))
        with html.Div(classes="d-flex ga-2 mt-1"):
            v3.VSpacer()
            v3.VBtn(
                "Reset",
                classes="text-none",
                density="compact",
                variant="text",
                disabled=("!transform.parameters_dirty",),
                click=(self.reset, "[transform._id]"),
            )
            v3.VBtn(
                "Apply",
                classes="text-none",
                density="compact",
                variant="tonal",
                color="primary",
                disabled=("!transform.parameters_dirty",),
                click=(self.apply, "[transform._id]"),
            )

    def open(self, model_id):
        """Show the dialog for the catalog node model ``model_id``, loading
        its entry's description and script."""
        model = get_instance(model_id)
        if not isinstance(model, DataNodeModel) or model.parameters is None:
            logger.warning("No catalog node to configure: {}", model_id)
            return

        self.editor.transform_id = model._id
        self.editor.show = True

    def rename(self, model_id, label):
        model = get_instance(model_id)
        model.label = label
        model.definition = {**model.definition, "label": label}
        # model.dirty("definition")
        model.save_to_node()

    def save(self, model_id):
        model = get_instance(model_id)
        model.label = model.definition.get("label", model.label)
        model.save_to_node()

    def apply(self, model_id):
        model = get_instance(model_id)
        if model is not None:
            model.apply_parameters()

    def reset(self, model_id):
        model = get_instance(model_id)
        if model is not None:
            model.reset_parameters()
