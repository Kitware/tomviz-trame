from trame.widgets import html
from trame.widgets import vuetify3 as v3

from tomviz_trame.app.ui.coloropacity import ColorOpacityEditor


class ColorOpacitySection(html.Div):
    def __init__(self):
        super().__init__()

        with self:
            with v3.VBtn(
                prepend_icon=(
                    "show_coloropacity ? 'mdi-chevron-down' : 'mdi-chevron-up'",
                ),
                text="Color Opacity Map",
                click="show_coloropacity = !show_coloropacity",
                classes="w-100 text-none mb-1",
                variant="tonal",
                spaced="end",
            ):
                pass

            with v3.VExpandTransition():
                with v3.VCard(
                    classes="border-thin overflow-hidden flex-fill pa-2 mb-2",
                    flat=True,
                    variant="flat",
                    v_show=("show_coloropacity && active_coloropacity_id",),
                ):
                    ColorOpacityEditor(
                        coloropacity_instance="active_coloropacity_id",
                        colormaps_instance="colormaps_id",
                    )
