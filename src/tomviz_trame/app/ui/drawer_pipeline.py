from trame.widgets import dataclass, html
from trame.widgets import vuetify3 as v3


class PipelineSection(html.Div):
    def __init__(self):
        super().__init__()

        with self:
            with v3.VBtn(
                prepend_icon=("show_pipeline ? 'mdi-chevron-down' : 'mdi-chevron-up'",),
                text="Pipelines",
                click="show_pipeline = !show_pipeline",
                classes="w-100 text-none mb-1",
                variant="tonal",
                spaced="end",
            ):
                with v3.Template(v_slot_append=True):
                    with dataclass.Provider(
                        "active_view", instance=("active_view_id",)
                    ):
                        v3.VIcon("mdi-stop", color=("active_view.color",))
            with v3.VExpandTransition():
                with v3.VCard(
                    classes="border-thin overflow-auto flex-fill mb-2",
                    flat=True,
                    variant="flat",
                    v_show=("show_pipeline", True),
                ):
                    with self.ctx.pipeline.tree.provide_as("pipeline"):
                        with v3.VList(
                            items=("pipeline.children",),
                            item_title="name",
                            item_value="_id",
                            rounded=True,
                            slim=True,
                            classes="px-2 pt-0",
                        ):
                            with v3.Template(v_slot_item="{ props }"):
                                with dataclass.Provider(
                                    name="item", instance=("props.value",)
                                ):
                                    # html.Div("{{ item }}") # debug
                                    with v3.VList(
                                        bg_color="surface-light",
                                        classes="py-0 pipeline mt-2",
                                        color="primary",
                                        density="compact",
                                        rounded=True,
                                        activatable=True,
                                        v_model_activated="pipeline.active_node",
                                    ):
                                        with v3.VListItem(
                                            classes="px-2 no-select",
                                            tile=True,
                                            title=("item.name",),
                                            value=("item._id",),
                                        ):
                                            with v3.Template(v_slot_prepend=True):
                                                v3.VBtn(
                                                    icon=(
                                                        "`mdi-chevron-${item.expand_pipeline ? 'down' : 'right'}`",
                                                    ),
                                                    ripple=False,
                                                    size="small",
                                                    density="compact",
                                                    variant="plain",
                                                    classes="mr-1",
                                                    v_on_click_prevent_stop="item.expand_pipeline = !item.expand_pipeline",
                                                )
                                        with v3.VExpandTransition():
                                            with html.Div(
                                                v_if="item.expand_pipeline",
                                                classes="",
                                            ):
                                                with v3.Template(
                                                    v_for="representations, view_id in item.representations",
                                                    key="view_id",
                                                ):
                                                    with dataclass.Provider(
                                                        name="view",
                                                        instance=("view_id",),
                                                    ):
                                                        with v3.VAlert(
                                                            border="start",
                                                            border_color=(
                                                                "view.color",
                                                            ),
                                                            classes="ml-6 mr-2 my-2 py-0 pl-2 pr-0",
                                                            variant="tonal",
                                                            color="bg-surface",
                                                        ):
                                                            v3.VBtn(
                                                                icon=(
                                                                    "item.expand_representations.includes(view_id) ? 'mdi-chevron-up' : 'mdi-chevron-down'",
                                                                ),
                                                                ripple=False,
                                                                block=True,
                                                                tile=True,
                                                                variant="plain",
                                                                density="compact",
                                                                size="x-small",
                                                                click="item.expand_representations = (item.expand_representations.includes(view_id) ? item.expand_representations.filter((v) => v !== view_id) : [...item.expand_representations, view_id])",
                                                            )
                                                            with v3.VExpandTransition():
                                                                with v3.VList(
                                                                    density="compact",
                                                                    classes="py-0",
                                                                    activatable=True,
                                                                    v_model_activated="pipeline.active_node",
                                                                    v_if="item.expand_representations.includes(view_id)",
                                                                ):
                                                                    with v3.Template(
                                                                        v_for="rep, r_idx in representations",
                                                                        key="r_idx",
                                                                    ):
                                                                        with dataclass.Provider(
                                                                            name="rep",
                                                                            instance=(
                                                                                "rep",
                                                                            ),
                                                                        ):
                                                                            with v3.VListItem(
                                                                                title=[
                                                                                    "rep.label"
                                                                                ],
                                                                                classes="representation px-2",
                                                                                value=(
                                                                                    "rep._id",
                                                                                ),
                                                                            ):
                                                                                with v3.Template(
                                                                                    v_slot_prepend=True
                                                                                ):
                                                                                    v3.VAvatar(
                                                                                        image=[
                                                                                            "rep.icon"
                                                                                        ],
                                                                                        tile=True,
                                                                                        size="small",
                                                                                        classes="rounded pa-1",
                                                                                        # color="red",
                                                                                        variant="tonal",
                                                                                    )
                                                                                with v3.Template(
                                                                                    v_slot_append=True
                                                                                ):
                                                                                    v3.VBtn(
                                                                                        icon=(
                                                                                            "rep.Visibility ? 'mdi-eye-outline' : 'mdi-eye-off-outline'",
                                                                                        ),
                                                                                        density="compact",
                                                                                        variant="plain",
                                                                                        v_on_click_prevent_stop="rep.Visibility = !rep.Visibility",
                                                                                    )
