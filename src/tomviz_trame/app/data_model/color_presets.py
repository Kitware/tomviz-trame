from trame.app.dataclass import StateDataModel, Sync

from tomviz_trame.app.utils import colors as util_colors


class ColorPreset(StateDataModel):
    name = Sync(str)
    colors = Sync(list[util_colors.Color], list)
    imgs = Sync(tuple[str, str], ("", ""))  # normal, inverted


class ColorMaps(StateDataModel):
    presets = Sync(dict[str, ColorPreset], dict, has_dataclass=True)
