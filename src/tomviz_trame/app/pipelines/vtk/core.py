from trame_colormaps.core.presets import apply_preset as _apply_ctf_preset
from trame_colormaps.core.presets import invert_ctf, rescale_ctf
from vtkmodules.vtkCommonCore import vtkLookupTable
from vtkmodules.vtkCommonDataModel import vtkPiecewiseFunction
from vtkmodules.vtkRenderingCore import vtkColorTransferFunction


class Algorithm:
    def __init__(self): ...


class PiecewiseFunction:
    def __init__(self):
        self.function = vtkPiecewiseFunction()
        self._points = []

    @property
    def Points(self):
        return self._points

    @Points.setter
    def Points(self, points):
        self._points = points

        self.function.RemoveAllPoints()
        for i in range(0, len(points), 4):
            self.function.AddPoint(*points[i : i + 4])


class LookupTable:
    def __init__(self, n_colors=255):
        self.n_colors = n_colors
        self.ctf = vtkColorTransferFunction()
        self.table = vtkLookupTable()

    def apply_preset(self, preset_name):
        _apply_ctf_preset(self.ctf, preset_name)
        self._build_table()

    def rescale(self, min_value, max_value):
        rescale_ctf(self.ctf, min_value, max_value)
        self._build_table()

    def invert(self):
        invert_ctf(self.ctf)
        self._build_table()

    def _build_table(self):
        n = self.n_colors
        v_min, v_max = self.ctf.GetRange()

        self.table.SetNumberOfTableValues(n)
        self.table.SetRange(v_min, v_max)
        self.table.Build()

        rgb = [0.0, 0.0, 0.0]
        for i in range(n):
            t = v_min + (v_max - v_min) * i / (n - 1) if n > 1 else v_min
            self.ctf.GetColor(t, rgb)
            self.table.SetTableValue(i, rgb[0], rgb[1], rgb[2], 1.0)

        self.table.BuildSpecialColors()
