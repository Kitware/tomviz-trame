from trame.widgets import html
from trame.widgets import vuetify3 as v3
from trame_common.decorators.hot_reload import hot_reload

from tomviz_trame.app.assets import ASSETS


@hot_reload
def toolbar_btn(asset_name, click=None, **add_on):
    with v3.VBtn(
        icon=True,
        classes="rounded mr-2",
        density="comfortable",
        variant="tonal",
        click=click,
        **add_on,
    ):
        html.Img(src=ASSETS[asset_name], height=30)
