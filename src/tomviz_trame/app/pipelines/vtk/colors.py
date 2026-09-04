import json
from pathlib import Path

from loguru import logger
from vtkmodules.vtkRenderingCore import vtkColorTransferFunction


def extract_presets(file_to_load):
    loaded_presets = {}
    file_to_load = Path(file_to_load)
    if not file_to_load.exists():
        msg = f"Preset file not found: {file_to_load}"
        raise ValueError(msg)

    for preset in json.loads(file_to_load.read_text()):
        name = preset.get("Name")
        loaded_presets[name] = preset

    return loaded_presets


PRESET_FILE = Path(__file__).with_name("presets.json").resolve()
PRESETS = extract_presets(PRESET_FILE)


class LookupTable:
    def __init__(self):
        self.ctf = vtkColorTransferFunction()
        self.color_min = 0
        self.color_max = 1
        self._preset = None
        self._inverted = False

    @property
    def preset(self):
        return self._preset

    @property
    def inverted(self):
        return self._inverted

    @property
    def vtk_scalar_to_color(self):
        return self.ctf

    def apply_preset(self, name):
        preset = PRESETS.get(name)
        if preset is None:
            msg = f"Preset not found: {name}"
            raise ValueError(msg)

        # Reset
        self.ctf.RemoveAllPoints()
        self.ctf.ResetAnnotations()
        self._preset = name
        self._inverted = False

        # ColorSpace
        color_space = preset.get("ColorSpace", "RGB")
        if color_space == "Diverging":
            self.ctf.SetColorSpaceToDiverging()
        elif color_space == "HSV":
            self.ctf.SetColorSpaceToHSV()
        elif color_space == "Lab":
            self.ctf.SetColorSpaceToLab()
        else:
            self.ctf.SetColorSpaceToRGB()

        # RGBPoints
        points = preset["RGBPoints"]
        for i in range(0, len(points), 4):
            self.ctf.AddRGBPoint(points[i], points[i + 1], points[i + 2], points[i + 3])

        # Reset Range
        self.rescale(self.color_min, self.color_max)

    def invert(self):
        self._inverted = not self._inverted
        n = self.ctf.GetSize()
        if n < 2:
            return
        x_min, x_max = self.ctf.GetRange()
        node = [0.0] * 6  # x, r, g, b, midpoint, sharpness
        nodes = []
        for i in range(n):
            self.ctf.GetNodeValue(i, node)
            x = x_min + (x_max - node[0])
            nodes.append((x, *node[1:4]))

        self.ctf.RemoveAllPoints()
        while nodes:
            node = nodes.pop()
            self.ctf.AddRGBPoint(*node)

    def rescale(self, min_value, max_value):
        self.color_min = min_value
        self.color_max = max_value
        logger.critical("lut::rescale({}, {})", min_value, max_value)
        n = self.ctf.GetSize()
        if n < 2:
            return
        old_min, old_max = self.ctf.GetRange()
        old_range = old_max - old_min
        if old_range == 0:
            return
        new_range = max_value - min_value
        node = [0.0] * 6  # x, r, g, b, midpoint, sharpness
        nodes = []
        for i in range(n):
            self.ctf.GetNodeValue(i, node)
            t = (node[0] - old_min) / old_range
            x = min_value + t * new_range
            nodes.append((x, *node[1:4]))

        self.ctf.RemoveAllPoints()
        for node in nodes:
            self.ctf.AddRGBPoint(*node)
