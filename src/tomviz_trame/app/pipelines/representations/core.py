from loguru import logger


class RepresentationBase:
    def use_lut(self, lut):
        if lut is None:
            return

        self.mapper.SetLookupTable(lut.table)
        self.mapper.SetUseLookupTableScalarRange(True)
        self.mapper.SetScalarVisibility(True)

    def use_pwf(self, pwf):
        if pwf is None:
            return

        lut = self.mapper.GetLookupTable()
        if lut is None:
            return

        n = lut.GetNumberOfTableValues()
        v_min, v_max = lut.GetRange()

        for i in range(n):
            r, g, b, _a = lut.GetTableValue(i)
            t = v_min + (v_max - v_min) * i / (n - 1) if n > 1 else v_min
            alpha = pwf.function.GetValue(t)
            lut.SetTableValue(i, r, g, b, alpha)

        self.mapper.SetScalarVisibility(True)

    @property
    def ColorArrayName(self):
        return getattr(self, "_color_array_name", (None, None))

    @ColorArrayName.setter
    def ColorArrayName(self, value):
        self._color_array_name = value
        association, name = value

        if not name:
            self.mapper.SetScalarVisibility(False)
            return

        if association == "CELLS":
            self.mapper.SetScalarModeToUseCellFieldData()
        else:
            self.mapper.SetScalarModeToUsePointFieldData()

        self.mapper.SelectColorArray(name)
        self.mapper.SetColorModeToMapScalars()
        self.mapper.SetScalarVisibility(True)

    @property
    def input_extent(self):
        logger.critical("RepresentationBase::input_extent")
        return [0, 10, 0, 10, 0, 10]
