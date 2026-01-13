from trame.widgets import client, dataclass, html
from trame.widgets import vuetify3 as v3


class PropertiesSections(html.Div):
    def __init__(self):
        super().__init__()

        with self:
            with v3.VBtn(
                prepend_icon=(
                    "show_properties ? 'mdi-chevron-down' : 'mdi-chevron-up'",
                ),
                text="Properties",
                click="show_properties = !show_properties",
                classes="w-100 text-none mb-1",
                variant="tonal",
                spaced="end",
            ):
                with v3.Template(v_slot_append=True):
                    with dataclass.Provider(
                        name="rep", instance=("active_representation_id",)
                    ):
                        with dataclass.Provider(name="view", instance=("rep.View",)):
                            v3.VIcon("mdi-stop", color=("view.color",))
            with v3.VExpandTransition():
                with v3.Template(
                    v_for="tpl in property_templates",
                    key="tpl",
                ):
                    client.ServerTemplate(
                        name=("tpl",),
                        v_show=("show_properties", True),
                    )
