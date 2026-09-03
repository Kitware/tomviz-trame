from trame.ui.html import DivLayout
from trame.widgets import dataclass, html
from trame.widgets import vuetify3 as v3

NAME = "operator"
TEMPLATE = "operator"


class OperatorUI(DivLayout):
    def __init__(self, server, template_name=TEMPLATE):
        super().__init__(server, template_name=template_name)

        with (
            self,
            v3.VCard(classes="border-thin pa-2 mb-2", flat=True),
            dataclass.Provider(name="operator", instance=("active_data_id",)),
        ):
            dataclass.Gui(instance=("operator.data._id",))
            with html.Div(classes="d-flex"):
                v3.VSpacer()
                v3.VBtn(
                    "Apply",
                    classes="text-none",
                    density="compact",
                    variant="tonal",
                    color="primary",
                )


UI = OperatorUI
