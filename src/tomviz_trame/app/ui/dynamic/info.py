from trame.ui.html import DivLayout
from trame.widgets import dataclass, html
from trame.widgets import vuetify3 as v3

NAME = "data_info"
TEMPLATE = NAME


class DataInformation(DivLayout):
    def __init__(self, server, template_name=NAME):
        super().__init__(server, template_name=template_name)

        with (
            self,
            dataclass.Provider(name="info", instance=("active_data_id",)),
        ):
            with v3.VCard(classes="border-thin", flat=True):
                # with v3.VCardItem(
                #     classes="pa-1 text-medium-emphasis",
                #     title="Data information",
                # ):
                #     with v3.Template(v_slot_prepend=True):
                #         v3.VIcon("mdi-database", size="small", classes="mx-1")
                #     with v3.Template(v_slot_append=True):
                #         v3.VBtn(
                #             icon=(
                #                 "show_data_information ? 'mdi-chevron-down' : 'mdi-chevron-up'",
                #             ),
                #             density="compact",
                #             variant="plain",
                #             click="show_data_information = !show_data_information",
                #         )
                # v3.VDivider(v_show=("show_data_information", True))
                with v3.VTable(
                    striped="even",
                    density="compact",
                ):
                    with html.Tbody():
                        for name in ["type", "bounds", "dimensions", "memory"]:
                            with html.Tr():
                                html.Td(name, classes="text-capitalize")
                                html.Td("{{ info.%s }}" % (name))  # noqa: UP031


UI = DataInformation
