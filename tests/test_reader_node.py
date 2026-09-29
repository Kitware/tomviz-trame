import numpy as np
import pytest
from tomviz_pipeline import NodeFactory, NodeState, Pipeline, PortData, SinkNode
from tomviz_pipeline.dataset import Dataset
from tomviz_pipeline.writers import write_emd
from vtkmodules.vtkIOImage import vtkTIFFWriter

from tomviz_web.app.pipeline.nodes import (
    INPUT_PORT,
    ReaderSourceNode,
    register_nodes,
)
from tomviz_web.app.pipeline.vtk import convert


@pytest.fixture
def tiff_volume(tmp_path):
    values = np.arange(3 * 4 * 5, dtype=np.uint16).reshape((3, 4, 5), order="F")
    writer = vtkTIFFWriter()
    writer.SetFileName(str(tmp_path / "volume.tif"))
    writer.SetInputData(convert.to_vtk_image(Dataset({"scalars": values})))
    writer.Write()
    return tmp_path / "volume.tif", values


def test_register_nodes_overrides_the_library_reader():
    register_nodes()
    assert isinstance(NodeFactory.create("source.reader"), ReaderSourceNode)
    # The library's types are still there.
    assert NodeFactory.create("transform.crop") is not None


def test_reader_node_reads_tiff_through_vtk(tiff_volume):
    path, values = tiff_volume
    node = ReaderSourceNode.for_file(path)
    assert node.type_name == "source.reader"
    assert node.label == "volume"
    assert node.file_path == path

    assert node.execute() is True

    port_data = node.output_port("volume").data()
    dataset = port_data.payload
    assert isinstance(dataset, Dataset)
    assert dataset.file_name == str(path)
    assert dataset.scalars_names == [dataset.active_name]
    np.testing.assert_array_equal(dataset.active_scalars, values)


def test_reader_types_its_output_like_the_desktop(tiff_volume, tmp_path):
    """A TiltSeries when the data has tilt angles, a Volume otherwise: never
    plain ImageData, which kernels declaring a Volume input refuse."""
    values = np.zeros((4, 4, 3), dtype=np.float32, order="F")
    volume = tmp_path / "volume.emd"
    write_emd(Dataset({"scalars": values}), volume)
    tilt_series = Dataset({"scalars": values})
    tilt_series.tilt_angles = np.array([-30.0, 0.0, 30.0])
    tilt_series.tilt_axis = 2
    write_emd(tilt_series, tmp_path / "tilt_series.emd")

    for path, expected in (
        (tiff_volume[0], "Volume"),  # read through VTK
        (volume, "Volume"),  # read by the library
        (tmp_path / "tilt_series.emd", "TiltSeries"),
    ):
        node = ReaderSourceNode.for_file(path)
        assert node.execute() is True
        port = node.output_port("volume")
        assert port.port_type == expected, path.name
        assert port.data().port_type == expected, path.name


def test_reader_node_fails_cleanly_without_a_file(tmp_path):
    assert ReaderSourceNode().execute() is False
    assert ReaderSourceNode.for_file(tmp_path / "missing.tif").execute() is False


class RecordingSink(SinkNode):
    executable = True

    def __init__(self):
        super().__init__()
        self.add_input(INPUT_PORT, ["ImageData"])
        self.received = []

    def consume(self, inputs: dict[str, PortData]) -> bool:
        self.received.append(inputs[INPUT_PORT].payload)
        return True


def test_reader_feeds_sinks_through_the_graph(tiff_volume):
    path, values = tiff_volume
    graph = Pipeline()
    reader = graph.add_node(ReaderSourceNode.for_file(path))
    sink = graph.add_node(RecordingSink())
    graph.create_link(reader.output_port("volume"), sink.input_port(INPUT_PORT))

    future = graph.execute()
    assert future.succeeded()
    assert reader.state == NodeState.Current
    assert sink.state == NodeState.Current
    assert len(sink.received) == 1
    np.testing.assert_array_equal(sink.received[0].active_scalars, values)

    # Nothing changed: re-executing is a no-op for both nodes.
    assert graph.execution_plan() == []
