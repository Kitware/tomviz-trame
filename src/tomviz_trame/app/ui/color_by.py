from trame.widgets import dataclass, html
from trame.widgets import vuetify3 as v3


class ColorBy(dataclass.Provider):
    def __init__(self):
        super().__init__(name="colormaps")
        self.instance = self.ctx.colormaps._id

        with self:
            with html.Div(classes="d-flex align-center"):
                v3.VLabel("Color By")
                v3.VSpacer()

                v3.VBtn(
                    icon=(
                        "rep.color_preset_inverted ? 'mdi-invert-colors' : 'mdi-invert-colors-off'",
                    ),
                    density="compact",
                    size="small",
                    hide_details=True,
                    variant="plain",
                    classes="rounded ml-2",
                    click="rep.color_preset_inverted = !rep.color_preset_inverted",
                    disabled=("!rep.color_by",),
                    v_tooltip_top="'Invert color preset'",
                )

                v3.VBtn(
                    icon="mdi-arrow-expand-horizontal",
                    density="compact",
                    size="small",
                    hide_details=True,
                    variant="plain",
                    classes="rounded ml-2",
                    click=(
                        self.ctx.pipeline.use_color_range_as_bounds,
                        "[rep._id]",
                    ),
                    disabled=("!rep.color_by",),
                    v_tooltip_top="'Use color range as slider bounds'",
                )
                v3.VBtn(
                    icon="mdi-magnify-minus-outline",
                    density="compact",
                    size="small",
                    hide_details=True,
                    variant="plain",
                    classes="rounded ml-2",
                    click="rep.color_range=[rep.color_range[0]*2, rep.color_range[1]*2]",
                    disabled=("!rep.color_by",),
                    v_tooltip_top="'Increase color range by 2 on each bound'",
                )
                v3.VBtn(
                    icon="mdi-magnify-plus-outline",
                    density="compact",
                    size="small",
                    hide_details=True,
                    variant="plain",
                    classes="rounded ml-2",
                    click="rep.color_range=[rep.color_range[0]/2, rep.color_range[1]/2]",
                    disabled=("!rep.color_by",),
                    v_tooltip_top="'Reduce color range by 2 on each bound'",
                )
                v3.VBtn(
                    icon="mdi-database-refresh",
                    density="compact",
                    size="small",
                    hide_details=True,
                    variant="plain",
                    classes="rounded ml-2",
                    click=(
                        self.ctx.pipeline.reset_color_range,
                        "[rep._id]",
                    ),
                    disabled=("!rep.color_by",),
                    v_tooltip_top="'Reset slider to full data range'",
                )

            v3.VSelect(
                v_model="rep.color_by",
                items=("rep.array_names",),
                variant="solo-filled",
                flat=True,
                density="compact",
                hide_details=True,
                classes="my-1",
            )
            with v3.Template(v_if="rep.color_by"):
                v3.VRangeSlider(
                    v_model="rep.color_range",
                    min=("rep.color_range_bounds[0]",),
                    max=("rep.color_range_bounds[1]",),
                    step=("rep.color_range_bounds[2]",),
                    density="comfortable",
                    hide_details=True,
                )
                with html.Div(
                    classes="d-flex no-select position-relative align-center"
                ):
                    v3.VLabel("{{ (rep.color_range?.[0] || 0).toFixed(1) }}")
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
                                        "colormaps.presets?.[rep.color_preset].imgs[Number(rep.color_preset_inverted)]",
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
                                placeholder=("rep.color_preset",),
                            )
                            with v3.VList(density="comfortable"):
                                with v3.VListItem(
                                    v_for="preset, name in colormaps.presets",
                                    key="idx",
                                    subtitle=("name",),
                                    click="rep.color_preset = name;color_preset_filter='';",
                                    v_show="name.toLowerCase().includes(color_preset_filter.toLowerCase())",
                                ):
                                    html.Img(
                                        src=(
                                            "preset.imgs[Number(rep.color_preset_inverted)]",
                                        ),
                                        classes="rounded",
                                        style="height: 16px;max-width: 100%;",
                                    )
                    v3.VLabel("{{ (rep.color_range?.[1] || 1).toFixed(1) }}")

            with v3.VItemGroup(
                v_else=True,
                classes="d-inline-flex ga-1",
                mandatory="force",
                v_model="rep.solid_color",
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
