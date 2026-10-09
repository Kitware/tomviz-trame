"""The application's file reader source node."""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from tomviz_pipeline import PortData
from tomviz_pipeline.nodes.sources.reader import ReaderSourceNode as _ReaderSourceNode
from vtkmodules.vtkIOImage import vtkTIFFReader

from tomviz_web.app.pipeline.vtk import convert

OUTPUT_PORT = "volume"

# Formats read through VTK. Anything else is handed to tomviz_pipeline, which
# reads EMD and Data Exchange HDF5 files itself.
VTK_READERS = {
    ".tif": vtkTIFFReader,
    ".tiff": vtkTIFFReader,
}
LIBRARY_EXTENSIONS = (".emd", ".h5", ".hdf5")
SUPPORTED_EXTENSIONS = (*VTK_READERS, *LIBRARY_EXTENSIONS)


class ReaderSourceNode(_ReaderSourceNode):
    """``source.reader`` node that also understands the formats the app reads
    through VTK.

    The node keeps the library's type string, parameters (``fileNames``,
    ``readerOptions``) and serialization, so a state file written here loads
    in the desktop tomviz and vice versa. Only ``execute`` differs: files with
    a VTK reader are read through it and converted to a numpy Dataset, the
    rest go through the library's own readers. Either way the output is typed
    like the desktop reader types it: ``TiltSeries`` when the data has tilt
    angles, ``Volume`` otherwise, never plain ``ImageData`` (which kernels
    declaring a ``Volume`` input refuse).
    """

    @classmethod
    def for_file(cls, file_path: str | Path) -> ReaderSourceNode:
        file_path = Path(file_path)
        node = cls()
        node.file_names = [str(file_path)]
        node.label = file_path.stem
        return node

    @property
    def file_path(self) -> Path | None:
        """The first file, relative paths resolved against the state file's
        directory (stamped on the node by the library's loader)."""
        if not self.file_names:
            return None
        return self.resolve_path(self.file_names[0])

    def execute(self) -> bool:
        file_path = self.file_path
        if file_path is None:
            logger.error("Reader node {} has no file to read", self.id)
            return False

        reader_class = VTK_READERS.get(file_path.suffix.lower())
        if reader_class is None:
            if not super().execute():
                return False
            # The library leaves data without tilt angles as ImageData.
            self._set_output(self.output_port(OUTPUT_PORT).data().payload)
            return True

        if not file_path.exists():
            logger.error("File not found: {}", file_path)
            return False

        reader = reader_class(file_name=str(file_path))
        reader.Update()
        dataset = convert.from_vtk_image(reader.GetOutputDataObject(0))
        dataset.file_name = str(file_path)
        self._set_output(dataset)
        return True

    def _set_output(self, dataset):
        port = self.output_port(OUTPUT_PORT)
        port.port_type = "TiltSeries" if dataset.tilt_angles is not None else "Volume"
        port.set_data(PortData(dataset, port.port_type))
