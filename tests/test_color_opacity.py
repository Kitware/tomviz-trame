from tomviz_trame.app.data_model.color_opacity import (
    ColorOpacityModel,
    normalize_color_space,
)
from tomviz_trame.app.pipeline.vtk.core import LookupTable, PiecewiseFunction

# A three-point map over [10, 20] in the state-file vocabulary.
COLORS = [10.0, 0.0, 0.0, 1.0, 15.0, 0.0, 1.0, 0.0, 20.0, 1.0, 0.0, 0.0]
POINTS = [10.0, 0.0, 0.5, 0.0, 20.0, 1.0, 0.5, 0.0]


def make_model():
    return ColorOpacityModel(None, lut=LookupTable(), pwf=PiecewiseFunction())


def test_new_map_comes_from_the_default_preset():
    model = make_model()
    assert model.active_color_preset == "Fast"
    assert len(model.color_points) > 2
    assert model.color_space == "Lab"  # the "Fast" preset's space
    xs = [row[0] for row in model.color_points]
    assert (min(xs), max(xs)) == (0.0, 1.0)
    assert model.opacity_points == [[0.0, 0.0, 0.5, 0.0], [1.0, 1.0, 0.5, 0.0]]
    assert model.lut.ctf.GetRange() == (0.0, 1.0)


def test_load_map_round_trips_and_keeps_its_range():
    model = make_model()
    model.load_map(COLORS, POINTS, "CIELAB")

    assert model.active_color_preset == ""
    assert model.color_space == "Lab"
    assert model.color_range == [10.0, 20.0]
    assert model.to_state() == {"colorSpace": "Lab", "colors": COLORS, "points": POINTS}
    assert model.lut.ctf.GetRange() == (10.0, 20.0)
    assert model.pwf.function.GetValue(15.0) == 0.5


def test_color_range_rescales_both_point_sets():
    model = make_model()
    model.load_map(COLORS, POINTS, "RGB")
    # Watchers need an event loop; drive the range change handler directly.
    model._on_color_range_change([0.0, 100.0])  # a JS array, like the client

    assert [row[0] for row in model.color_points] == [0.0, 50.0, 100.0]
    assert [row[1:] for row in model.color_points] == [
        [0.0, 0.0, 1.0],
        [0.0, 1.0, 0.0],
        [1.0, 0.0, 0.0],
    ]
    assert [row[0] for row in model.opacity_points] == [0.0, 100.0]


def test_editor_nodes_are_normalized_over_the_data_range():
    model = make_model()
    model.load_map(COLORS, POINTS, "RGB")
    model.data_range = (0.0, 40.0, 1.0)
    model._update_pwf()
    model._update_lut()

    assert model.scaled_opacities == [(0.25, 0.0), (0.5, 1.0)]
    assert model.scaled_colors[0][0] == 0.0
    assert model.scaled_colors[-1][0] == 1.0
    # Below the map's range the gradient clamps to the first color (blue).
    assert model.scaled_colors[0][1] == (0.0, 0.0, 1.0)

    # The editor moving a node (a client write) comes back in data units.
    model.update_from_client_state({"scaled_opacities": [(0.25, 0.0), (0.75, 1.0)]})
    assert model.opacity_points == [[10.0, 0.0, 0.5, 0.0], [30.0, 1.0, 0.5, 0.0]]


def test_server_side_opacity_syncs_never_write_back():
    """Rescaling to a new data range pushes normalized nodes to the editor;
    that push must not be mistaken for an edit, or the points snap back
    to the old range (the bug seen on every file open)."""
    model = make_model()
    model.load_map(COLORS, POINTS, "RGB")
    model.data_range = (0.0, 250.0, 1.0)
    model._update_pwf()  # nodes now at 0.04 and 0.08 of the data range
    model._on_color_range_change([0.0, 250.0])
    model._update_pwf()

    assert [row[0] for row in model.opacity_points] == [0.0, 250.0]
    assert model.scaled_opacities == [(0.0, 0.0), (1.0, 1.0)]
    # A stale echo of the earlier push, applied the old way, is inert.
    model.scaled_opacities = [(0.04, 0.0), (0.08, 1.0)]
    assert [row[0] for row in model.opacity_points] == [0.0, 250.0]


def test_color_space_aliases():
    assert normalize_color_space("CIELAB") == "Lab"
    assert normalize_color_space("Diverging") == "Diverging"
    assert normalize_color_space("") == "RGB"


class FakePort:
    """Just enough of an OutputPortModel for statistics to land."""

    def __init__(self, port_type="Volume", value_range=(0.0, 100.0)):
        self.port_type = port_type
        self.data_version = 1
        self.image = None  # pull() returns early: no arrays to read
        self._range = value_range

    def add_consumer(self, _):
        pass

    def statistics(self, _name):
        from types import SimpleNamespace

        return SimpleNamespace(range=self._range, histogram=[1.0, 2.0, 1.0])


def inherited(port_type="Volume"):
    source = make_model()
    source.load_map(COLORS, POINTS, "RGB")
    model = ColorOpacityModel(
        None, port=FakePort(port_type), lut=LookupTable(), pwf=PiecewiseFunction()
    )
    model.inherit_from(source)
    return source, model


def test_a_new_port_inherits_the_upstream_map():
    source, model = inherited()
    assert model.color_points == source.color_points
    assert model.opacity_points == source.opacity_points
    assert model.color_space == "RGB"
    assert model.active_color_preset == ""
    assert model.color_range == [10.0, 20.0]
    assert model.lut.ctf.GetRange() == (10.0, 20.0)
    # A copy: editing one leaves the other alone.
    model.color_points[0][1] = 0.5
    assert source.color_points[0][1] == 0.0


def test_an_inherited_map_stretches_to_the_new_data_range():
    _source, model = inherited()
    model.acquire("sink")
    model.active_data_array = "scalars"
    model._apply_statistics()
    assert model.data_range[:2] == (0.0, 100.0)
    assert model.color_range == [0.0, 100.0]
    model._on_color_range_change(model.color_range)  # the watcher, by hand
    assert [row[0] for row in model.color_points] == [0.0, 50.0, 100.0]
    assert [row[0] for row in model.opacity_points] == [0.0, 100.0]


def test_an_inherited_label_map_keeps_its_range():
    _source, model = inherited("LabelMap")
    model.acquire("sink")
    model.active_data_array = "labels"
    model._apply_statistics()
    assert model.data_range[:2] == (0.0, 100.0)
    assert model.color_range == [10.0, 20.0]  # label ids are data coordinates
