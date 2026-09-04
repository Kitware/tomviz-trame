from pathlib import Path

from vtkmodules.vtkIOImage import vtkTIFFReader

FACTORY = {
    ".tiff": vtkTIFFReader,
    ".tif": vtkTIFFReader,
}


class Reader:
    def __init__(self, file_path=None):
        self.algo = None
        self.file_path = None
        self._dataset = None

        if file_path:
            self.load(file_path)

    def load(self, file_path):
        file_path = Path(file_path).resolve()
        if not file_path.exists():
            msg = f"Invalid file path to load: {file_path}"
            raise ValueError(msg)

        klass = FACTORY.get(file_path.suffix.lower())
        if klass is None:
            msg = f"No matching reader for: {file_path}"
            raise ValueError(msg)

        self.algo = klass(file_name=str(file_path))
        self.algo.Update()
        self._dataset = self.algo.GetOutputDataObject(0)
        self.file_path = file_path

        return self

    @property
    def dataset(self):
        return self._dataset

    @property
    def bounds(self):
        return self.dataset.GetBounds()

    @property
    def memory(self):
        return self.dataset.GetActualMemorySize()

    @property
    def type(self):
        return self.dataset.GetClassName()

    @property
    def field_names(self):
        names = set()
        for field in [
            self.dataset.GetPointData(),
            self.dataset.GetCellData(),
            self.dataset.GetFieldData(),
        ]:
            size = field.GetNumberOfArrays()
            for i in range(size):
                names.add(field.GetAbstractArray(i).GetName())

        return list(names)
