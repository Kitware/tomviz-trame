from trame.ui.html import DivLayout
from trame.widgets import dataclass, html
from trame.widgets import vuetify3 as v3

NAME = "transform"
TEMPLATE = "transform"


class TransformUI(DivLayout):
    """Parameter panel of the active transform node: the generated GUI of
    its ``parameters`` model (edits are live through the parameter mirror)."""

    def __init__(self, server, template_name=TEMPLATE):
        super().__init__(server, template_name=template_name)

        with (
            self,
            v3.VCard(classes="border-thin pa-2 mb-2", flat=True),
            dataclass.Provider(name="transform", instance=("active_data_id",)),
        ):
            dataclass.Gui(instance=("transform.parameters._id",))
            with html.Div(classes="d-flex"):
                v3.VSpacer()
                v3.VBtn(
                    "Apply",
                    classes="text-none",
                    density="compact",
                    variant="tonal",
                    color="primary",
                )


UI = TransformUI
