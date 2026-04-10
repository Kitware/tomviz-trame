from trame.widgets import dataclass, html
from trame.widgets import vuetify3 as v3

from tomviz_trame.app import data_model


class OperatorSelection(html.Div):
    def __init__(self):
        super().__init__()

        self.state.setdefault("operator_favorites", False)

        with self:
            v3.VBtn(
                prepend_icon="mdi-chevron-left",
                text="Operators",
                click="select_operator = false",
                classes="w-100 text-none mb-1",
                variant="tonal",
                spaced="end",
            )

            with (
                dataclass.Provider(name="active_input", instance=("active_data_id",)),
                v3.VCard(
                    classes="border-thin overflow-auto flex-fill mb-2",
                    flat=True,
                    variant="flat",
                ),
            ):
                v3.VLabel(
                    "{{ active_input.name }}",
                    classes="text-subtitle-2 text-truncate mx-2 mt-2",
                )
                with html.Div(classes="d-flex pa-2 ga-2 align-center"):
                    v3.VTextField(
                        placeholder="Search operators...",
                        v_model=("operator_filter", ""),
                        prepend_inner_icon="mdi-magnify",
                        variant="outlined",
                        density="compact",
                        hide_details=True,
                        clearable=True,
                    )
                    v3.VBtn(
                        disabled=("operator_activated.length === 0",),
                        classes="rounded",
                        icon="mdi-plus",
                        color="primary",
                        density="comfortable",
                        flat=True,
                        click=(
                            self.create_operator,
                            "[active_input._id, operator_activated[0]]",
                        ),
                    )
                with html.Div(
                    classes="d-flex mx-2 pa-1 ga-2 align-center justify-space-around bg-surface-light rounded",
                ):
                    v3.VBtn(
                        "All Operators",
                        variant=("operator_favorites ? 'plain' : 'flat'",),
                        classes="text-none flex-fill",
                        click="operator_favorites = false",
                        density="comfortable",
                    )
                    v3.VBtn(
                        "Favorites ({{ operator_favorite_count }})",
                        prepend_icon="mdi-star",
                        variant=("operator_favorites ? 'flat' : 'plain'",),
                        classes="text-none flex-fill",
                        click="operator_favorites = true",
                        density="comfortable",
                    )

                with (
                    self.ctx.operators.root_node.provide_as("operator_root_node"),
                    html.Div(
                        style="height: calc(100vh - 14.8rem)",
                        classes="overflow-scroll mt-2",
                    ),
                    v3.VTreeview(
                        v_model_opened=("operator_opened", []),
                        v_model_activated=("operator_activated", []),
                        items=("operator_root_node.children",),
                        density="compact",
                        item_value="_id",
                        activatable=True,
                        open_on_click=True,
                        indent=20,
                        hide_actions=True,
                        open_all=(
                            "operator_favorites || (operator_filter|| '').length",
                        ),
                        search=(
                            "operator_favorites ? `${operator_filter} ::fav::` : operator_filter",
                        ),
                        custom_filter=("utils.tomviz.treeFilter",),
                    ),
                ):
                    with v3.Template(v_slot_prepend="{ item, isOpen }"):
                        v3.VIcon(
                            v_if="item.children",
                            icon=("isOpen ? 'mdi-folder-open' : 'mdi-folder'",),
                        )
                        v3.VIcon(v_else=True, icon=("item.icon",))
                    with v3.Template(v_slot_append="{ item }"):
                        v3.VChip(
                            "{{ item.count }}",
                            v_if="item.children && item.count",
                            size="x-small",
                        )
                        v3.VIcon(
                            icon=("item.favorite ? 'mdi-heart':'mdi-heart-outline'",),
                            color=("item.favorite ? 'red' : null",),
                            v_if="!item.children",
                            v_on_click_prevent="item.favorite = !item.favorite",
                        )

    def create_operator(self, input_id, operator_id):
        operator_node = data_model.get_instance(operator_id)
        self.ctx.pipeline.add_operator(
            input_id,
            operator_node.name,
            icon=operator_node.icon,
        )
