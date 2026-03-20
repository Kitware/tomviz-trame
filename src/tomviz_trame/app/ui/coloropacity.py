from trame.widgets import dataclass, html, color_opacity_editor
from trame.widgets import vuetify3 as v3


class ColorOpacityEditor(html.Div):
    def __init__(self, coloropacity_instance="active_coloropacity_id", colormaps_instance=""):
        super().__init__()

        with self:
            with dataclass.Provider(
                v_if=coloropacity_instance,
                name="coloropacity", instance=(coloropacity_instance,)
            ):
                with dataclass.Provider(
                    v_if=colormaps_instance,
                    name="colormaps", instance=(colormaps_instance,)
                ):
                    with v3.Template(
                        v_if="coloropacity && colormaps && coloropacity.scaled_colors && coloropacity.scaled_opacities",
                    ):
                        color_opacity_editor.ColorOpacityEditor(
                            style="height: 15rem;",
                            v_model_colorNodes=("coloropacity.scaled_colors",),
                            v_model_opacityNodes=("coloropacity.scaled_opacities",),
                            histograms=("coloropacity.scaled_histograms",),
                            histograms_range=("coloropacity.histograms_range",),
                            scalar_range=("default_scalar_range", [0, 1]),
                            show_histograms=("show_histograms", False),
                            show_color_editor=False,
                            histograms_color=("histograms_color", [0, 0, 0, 0.25]),
                            background_shape="histograms",
                            background_opacity=False,
                            # handle_radius=7,
                            # line_width=2,
                            # viewport_padding=("viewport_padding", [8, 8]),
                            # handle_color=("handle_color", [0.125, 0.125, 0.125, 1]),
                            # handle_border_color=("handle_border_color", [0.75, 0.75, 0.75, 1]),
                        )

                        with v3.Template(v_if="coloropacity.active_data_array"):
                            v3.VLabel("Color Range [{{ (coloropacity.color_range?.[0] || 0).toFixed(1) }}, {{ (coloropacity.color_range?.[1] || 1).toFixed(1) }}]")
                            v3.VRangeSlider(
                                v_model="coloropacity.color_range",
                                min=("coloropacity.data_range[0]",),
                                max=("coloropacity.data_range[1]",),
                                step=("coloropacity.data_range[2]",),
                                density="comfortable",
                                hide_details=True,
                            )

                            with html.Div(
                                classes="d-flex no-select position-relative align-center"
                            ):
                                with v3.VMenu(
                                    location="end",
                                    height="50vh",
                                    offset=5,
                                    close_on_content_click=False,
                                ):
                                    with v3.Template(v_slot_activator="{ props }"):
                                        with v3.VBtn(
                                            v_bind="props",
                                            classes="rounded flex-grow-1 mx-2 position-relative overflow-hidden",
                                            density="compact",
                                            hide_details=True,
                                            variant="outlined",
                                            size="small",
                                        ):
                                            html.Img(
                                                classes="position-absolute w-100 h-100",
                                                src=(
                                                    "colormaps.presets?.[coloropacity.active_color_preset].imgs[Number(coloropacity.invert_color_preset)]",
                                                ),
                                            )
                                    with v3.VCard(style="width: 300px;"):
                                        v3.VTextField(
                                            autofocus=True,
                                            v_model=(
                                                "color_preset_filter",
                                                "",
                                            ),
                                            hide_details=True,
                                            density="comfortable",
                                            prepend_inner_icon="mdi-magnify",
                                            placeholder=("coloropacity.active_color_preset",),
                                        )
                                        with v3.VList(density="comfortable"):
                                            with v3.VListItem(
                                                v_for="preset, name in colormaps.presets",
                                                key="idx",
                                                subtitle=("name",),
                                                click="coloropacity.active_color_preset = name;color_preset_filter='';",
                                                v_show="name.toLowerCase().includes(color_preset_filter.toLowerCase())",
                                            ):
                                                html.Img(
                                                    src=(
                                                        "preset.imgs[Number(coloropacity.invert_color_preset)]",
                                                    ),
                                                    classes="rounded",
                                                    style="height: 16px;max-width: 100%;",
                                                )
                                v3.VBtn(
                                    icon=(
                                        "coloropacity.invert_color_preset ? 'mdi-invert-colors' : 'mdi-invert-colors-off'",
                                    ),
                                    density="compact",
                                    size="small",
                                    hide_details=True,
                                    variant="plain",
                                    classes="rounded ml-2",
                                    click="coloropacity.invert_color_preset = !coloropacity.invert_color_preset",
                                    disabled=("!coloropacity.active_data_array",),
                                    v_tooltip_top="'Invert color preset'",
                                )

                                v3.VBtn(
                                    icon="mdi-arrow-expand-horizontal",
                                    density="compact",
                                    size="small",
                                    hide_details=True,
                                    variant="plain",
                                    classes="rounded ml-2",
                                    click="coloropacity.color_range = [coloropacity.data_range[0], coloropacity.data_range[1]]",
                                    disabled=("!coloropacity.active_data_array",),
                                    v_tooltip_top="'Reset color range to the full data range'",
                                )

                            with html.Div(classes="d-flex align-center"):
                                v3.VSelect(
                                    label="Color By",
                                    v_model="coloropacity.active_data_array",
                                    items=("coloropacity.data_arrays",),
                                    variant="solo-filled",
                                    flat=True,
                                    density="compact",
                                    hide_details=True,
                                    classes="my-1 mt-2",
                                )

                        with v3.VItemGroup(
                            v_else=True,
                            classes="d-inline-flex ga-1",
                            mandatory="force",
                            v_model="coloropacity.solid_color",
                        ):
                            with v3.VItem(v_for="(color, i) in palette", key="i"):
                                with v3.Template(v_slot_default="{ isSelected, toggle }"):
                                    with v3.VAvatar(
                                        color=("isSelected ? color : 'transparent'",),
                                        size=24,
                                    ):
                                        v3.VBtn(
                                            border="md surface opacity-100",
                                            color=("color",),
                                            size=18,
                                            flat=True,
                                            icon=True,
                                            ripple=False,
                                            click="toggle",
                                        )
