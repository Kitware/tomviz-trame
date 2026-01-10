from trame.widgets import client, html
from trame.widgets import vuetify3 as v3


class DataInformationSection(html.Div):
    def __init__(self):
        super().__init__()

        with self:
            v3.VBtn(
                prepend_icon=(
                    "show_informations ? 'mdi-chevron-down' : 'mdi-chevron-up'",
                ),
                text="Information",
                click="show_informations = !show_informations",
                classes="w-100 text-none mb-1",
                variant="tonal",
                spaced="end",
            )
            with v3.VExpandTransition():
                client.ServerTemplate(
                    name="data_info",
                    v_if=("active_data_id", None),
                    v_show=("show_informations", False),
                    classes="mb-2",
                )
