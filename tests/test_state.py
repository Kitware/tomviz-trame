import json
import math
from types import SimpleNamespace

import pytest
from tomviz_pipeline import SinkGroupNode, SinkNode
from tomviz_pipeline.core.state import pipeline_from_state_dict
from tomviz_pipeline.nodes import register_builtins

from tomviz_web.app.pipeline import state
from tomviz_web.app.pipeline.graph import data_port_of, primary_upstream
from tomviz_web.app.pipeline.representations import RepresentationType

# A reader feeding a sink group that fans out to two sinks, the desktop
# app's layout.
STATE = {
    "schemaVersion": 2,
    "pipeline": {
        "nextNodeId": 5,
        "nodes": [
            {"id": 1, "type": "source.reader", "label": "data", "fileNames": ["x.tif"]},
            {
                "id": 2,
                "type": "sinkGroup",
                "label": "Visualizations",
                "inputPorts": {"volume": {"type": ["ImageData"]}},
                "outputPorts": {"volume": {"persistent": False, "type": "ImageData"}},
                "typeInferenceSources": {"volume": "volume"},
            },
            {
                "id": 3,
                "type": "sink.slice",
                "label": "Slice",
                "inputPorts": {"volume": {"type": ["ImageData"]}},
                "direction": 1,
                "slice": 7,
                "viewId": 42,
            },
            {
                "id": 4,
                "type": "sink.outline",
                "label": "Outline",
                "inputPorts": {"volume": {"type": ["ImageData"]}},
                "visible": False,
            },
        ],
        "links": [
            {
                "from": {"node": 1, "port": "volume"},
                "to": {"node": 2, "port": "volume"},
            },
            {
                "from": {"node": 2, "port": "volume"},
                "to": {"node": 3, "port": "volume"},
            },
            {
                "from": {"node": 2, "port": "volume"},
                "to": {"node": 4, "port": "volume"},
            },
        ],
    },
}


@pytest.fixture(autouse=True)
def _builtins():
    register_builtins()


def test_the_library_builds_the_sink_group_the_desktop_saves():
    pipeline = pipeline_from_state_dict(STATE)
    reader = pipeline.node_by_id(1)
    group = pipeline.node_by_id(2)
    assert isinstance(group, SinkGroupNode)
    assert group.output_port("volume").source is reader.output_port("volume")
    for sink_id in (3, 4):
        sink = pipeline.node_by_id(sink_id)
        assert isinstance(sink, SinkNode)
        assert primary_upstream(sink) is group.output_port("volume")
        assert data_port_of(primary_upstream(sink)) is reader.output_port("volume")
    assert len(pipeline.links) == 3


def test_sink_settings_translate_desktop_enums():
    assert state.slice_settings({"direction": 1, "slice": 7, "interpolate": True}) == {
        "SliceDirection": "YZ Plane",
        "Slice": 7,
        "Interpolate": True,
    }
    assert state.slice_settings(
        {
            "direction": 3,
            "planeCenter": [1, 2, 3],
            "planeNormal": [0, 1, 1],
            "opacity": 0.5,
            "sliceThickness": 3,
            "thickSliceMode": 1,
            "showArrow": False,
            "mapScalars": False,
        }
    ) == {
        "SliceDirection": "Custom",
        "PlaneCenter": (1.0, 2.0, 3.0),
        "PlaneNormal": (0.0, 1.0, 1.0),
        "Opacity": 0.5,
        "SliceThickness": 3,
        "ThickSliceMode": "Maximum",
        "ShowArrow": False,
        "MapScalars": False,
    }
    assert state.volume_settings(
        {
            "interpolation": 1,
            "lighting": {"enabled": True, "shadowReach": 0.4, "scattering": 1.5},
        }
    ) == {
        "InterpolationType": "Linear",
        "Shade": True,
        "ShadowReach": 0.4,
        "VolumetricScattering": 1.5,
        # a file without the key keeps its settings on a label map port
        "label_map_defaults_applied": True,
    }
    assert state.volume_settings(
        {
            "labelMapDefaultsApplied": False,
            "blendingMode": 1,
            "rayJittering": False,
            "solidity": 0.5,
            "lighting": {"shadowsEnabled": False, "smoothNormals": True},
            "cutOut": {"enabled": True, "corner": 5, "position": [0.2, 0.4, 0.6]},
            "exploded": {
                "enabled": True,
                "axis": 3,
                "direction": [0, 1, 1],
                "chunks": 6,
                "gap": 0.5,
                "offset": -2,
                "showArrow": False,
            },
        }
    ) == {
        "BlendMode": "Max",
        "Jittering": False,
        "Solidity": 0.5,
        "ShadowsEnabled": False,
        "SmoothNormals": True,
        # the exploded view wins over the cut-out, as on the desktop
        "CutOutEnabled": False,
        "CutOutCorner": 5,
        "CutOutPosition": (0.2, 0.4, 0.6),
        "ExplodedEnabled": True,
        "ExplodedAxis": "Custom",
        "ExplodedDirection": (0.0, 1.0, 1.0),
        "ExplodedChunks": 6,
        "ExplodedGap": 0.5,
        "ExplodedOffset": -2,
        "ExplodedShowArrow": False,
        "label_map_defaults_applied": False,
    }


def test_label_map_settings_add_the_representation_and_surface():
    settings = state.label_map_settings(
        {
            "representation": "Surface",
            "surfaceSmoothing": 8,
            "surfaceOpacity": 0.5,
            "volumeLookApplied": False,
            "lighting": {"ambient": 0.3},
        }
    )
    assert settings["Representation"] == "Surface"
    assert settings["SurfaceSmoothing"] == 8
    assert settings["SurfaceOpacity"] == 0.5
    assert settings["volume_look_applied"] is False
    assert settings["Ambient"] == 0.3
    # a file from before the surface existed was showing a volume, and its
    # lighting is what the user saw
    older = state.label_map_settings({})
    assert older["Representation"] == "Volume"
    assert older["volume_look_applied"] is True
    entry = {"type": "sink.labelMap", "representation": "Volume", "adoptedLabelMap": {}}
    assert state.unrestored_sink_settings(entry, RepresentationType.LABEL_MAP) == []


def test_outline_settings_take_the_desktop_grid_keys():
    assert state.outline_settings(
        {
            "gridColor": [0.9, 0.9, 0.9],
            "gridVisibility": True,
            "gridLines": False,
            "useCustomAxesTitles": True,
            "customXTitle": "Width",
        }
    ) == {
        "Color": "#e6e6e6",
        "ShowGridAxes": True,
        "ShowGrid": False,
        "UseCustomAxesTitles": True,
        "XTitle": "Width",
    }
    assert state.outline_settings({"gridColor": [1, 2]}) == {}


def test_contour_settings_take_the_desktop_keys():
    entry = {
        "contourValue": 12.5,
        "opacity": 0.5,
        "specularPower": 20,
        "representation": "Wireframe",
        "mapScalars": False,
        "useSolidColor": True,
        "color": "#FF8000",
        "activeScalars": "ramp",
        "colorByArray": True,
        "colorByArrayName": "other",
    }
    assert state.contour_settings(entry) == {
        "IsoValue": 12.5,
        "Opacity": 0.5,
        "SpecularPower": 20.0,
        "Mode": "Wireframe",
        "MapScalars": False,
        "UseSolidColor": True,
        "Color": "#ff8000",
        "ContourBy": "ramp",
    }
    assert state.contour_settings({"activeScalars": state.DEFAULT_SCALARS}) == {}
    # the "color by" array goes on the sink's own map (apply_sink_settings)
    assert state.unrestored_sink_settings(entry, RepresentationType.CONTOUR) == []


def test_threshold_settings_take_the_desktop_keys():
    entry = {
        "minimum": 10,
        "maximum": 20,
        "scalarArray": 1,
        "specular": 0.5,
        "representation": "Points",
        "colorByArray": False,
        "colorByArrayName": "ramp",
    }
    assert state.threshold_settings(entry) == {
        "Minimum": 10.0,
        "Maximum": 20.0,
        "ThresholdBy": 1,  # an index, named once data comes
        "Specular": 0.5,
        "Mode": "Points",
    }
    # both bounds or neither; -1 is the default array
    assert state.threshold_settings({"minimum": 1, "scalarArray": -1}) == {}
    assert state.unrestored_sink_settings(entry, RepresentationType.THRESHOLD) == []


def test_clip_settings_take_the_desktop_keys():
    # A Custom clip, inverted: the saved corners already carry the inverted
    # normal (the widget flipped it), so it is taken as is.
    entry = {
        "direction": 3,
        "plane": 4,
        "opacity": 0.25,
        "showPlane": False,
        "showArrow": False,
        "invertPlane": True,
        "selectedColor": [1.0, 0.0, 0.0],
        "origin": [0, 10, 5],
        "point1": [10, 10, 5],
        "point2": [0, 0, 5],
        "linked": True,
    }
    assert state.clip_settings(entry) == {
        "SliceDirection": "Custom",
        "Slice": 4,
        "Opacity": 0.25,
        "ShowPlane": False,
        "ShowArrow": False,
        "InvertPlane": True,
        "Color": "#ff0000",
        "PlaneCenter": (5.0, 5.0, 5.0),
        "PlaneNormal": (0.0, 0.0, -100.0),
    }
    # an axis-aligned clip ignores the corners
    assert state.clip_settings(
        {"direction": 1, **{k: entry[k] for k in ("origin", "point1", "point2")}}
    ) == {"SliceDirection": "YZ Plane"}
    assert state.unrestored_sink_settings(entry, RepresentationType.CLIP) == ["linked"]


def test_molecule_settings_take_the_desktop_keys():
    entry = {"ballRadius": 1.5, "stickRadius": 0.2}
    assert state.molecule_settings(entry) == {"BallRadius": 1.5, "StickRadius": 0.2}
    assert state.unrestored_sink_settings(entry, RepresentationType.MOLECULE) == []


def test_every_desktop_sink_type_has_a_representation_type():
    for sink_type in ("sink.outline", "sink.slice", "sink.volume"):
        rep_type = state.REPRESENTATION_BY_SINK_TYPE[sink_type]
        assert rep_type.representation_class is not None
    assert (
        state.REPRESENTATION_BY_SINK_TYPE["sink.contour"] is RepresentationType.CONTOUR
    )


def test_background_prefers_the_palette_and_unnests_the_triple():
    raw = {"paletteColor": [0.1, 0.2, 0.3]}
    assert state.background_of({"backgroundColor": [[0.5, 0.5, 0.5]]}, raw) == (
        0.5,
        0.5,
        0.5,
    )
    assert state.background_of(
        {"backgroundColor": [[0.5, 0.5, 0.5]], "useColorPaletteForBackground": 1}, raw
    ) == (0.1, 0.2, 0.3)
    assert state.background_of({}, {}) is None


def test_node_description_parses_the_embedded_json():
    description = {"name": "GaussianFilter", "parameters": []}
    assert (
        state.node_description({"description": json.dumps(description)}) == description
    )
    assert state.node_description({}) == {}
    assert state.node_description({"description": "{not json"}) == {}


def test_unrestored_settings_report_only_what_the_loader_skips():
    slice_entry = {
        "id": 7,
        "type": "sink.slice",
        "label": "Slice",
        "inputPorts": {},
        "state": "Current",
        "viewId": 1,
        "visible": True,
        "direction": 0,
        "slice": 3,
        "interpolate": True,
        "activeScalars": "tomviz::DefaultScalars",
        "thickSliceMode": 2,
        "opacity": 1,
        "linked": False,
    }
    assert state.unrestored_sink_settings(slice_entry, RepresentationType.SLICE) == [
        "linked",
    ]

    volume_entry = {
        "interpolation": 1,
        "activeScalars": "Other",
        "lighting": {"enabled": True, "ambient": 0.1, "glow": 1.0},
        "cutOut": {"enabled": False},
    }
    assert state.unrestored_sink_settings(volume_entry, RepresentationType.VOLUME) == [
        "activeScalars",
        "lighting.glow",
    ]


# ---- saving -----------------------------------------------------------------


VOLUME_ENTRY = {
    "interpolation": 0,
    "blendingMode": 3,
    "rayJittering": False,
    "solidity": 0.5,
    "labelMapDefaultsApplied": False,
    "lighting": {
        "enabled": True,
        "ambient": 0.2,
        "diffuse": 0.7,
        "specular": 0.1,
        "specularPower": 20.0,
        "scattering": 1.5,
        "shadowsEnabled": False,
        "shadowReach": 0.4,
        "anisotropy": -0.5,
        "smoothNormals": True,
    },
    "cutOut": {"enabled": True, "corner": 5, "position": [0.2, 0.4, 0.6]},
    "exploded": {
        "enabled": False,
        "axis": 3,
        "direction": [0.0, 1.0, 1.0],
        "showArrow": False,
        "chunks": 6,
        "gap": 0.5,
        "offset": -2,
    },
}


def model_of(settings: dict, **fields):
    """A stand-in sink model holding what a loader produced."""
    model = SimpleNamespace(**settings, **fields)
    if hasattr(model, "SliceDirection"):
        model.is_custom = model.SliceDirection == "Custom"
    return model


def round_trip(load, save, entry: dict, **fields) -> dict:
    """``entry`` through the loader into a model, then out of the saver,
    restricted to the keys the entry had."""
    saved = save(model_of(load(entry), **fields))
    return {key: saved[key] for key in entry}


def test_plane_points_give_the_plane_back():
    for normal in ((0, 0, 1), (0, 0, -3), (1, 0, 0), (0, -1, 0), (1, 2, -2)):
        points = state.plane_points((1.0, 2.0, 3.0), normal, 4.0)
        center, saved_normal = state.plane_of_points(points)
        assert center == pytest.approx((1.0, 2.0, 3.0))
        length = math.dist(saved_normal, (0, 0, 0))
        scale = math.dist(normal, (0, 0, 0))
        assert [c / length for c in saved_normal] == pytest.approx(
            [c / scale for c in normal]
        )
        assert length == pytest.approx(16.0)  # the square's area
    assert state.plane_points((0, 0, 0), (0, 0, 0), 1.0) == {}


def test_saved_sink_entries_are_the_desktop_ones():
    outline = {
        "gridColor": [1.0, 0.0, 0.0],
        "gridVisibility": True,
        "gridLines": False,
        "useCustomAxesTitles": True,
        "customXTitle": "Width",
        "customYTitle": "Y",
        "customZTitle": "Depth",
    }
    assert round_trip(state.outline_settings, state.outline_entry, outline) == outline

    slice_entry = {
        "direction": 2,
        "slice": 7,
        "interpolate": True,
        "showArrow": False,
        "mapScalars": False,
        "opacity": 0.5,
        "sliceThickness": 3,
        "thickSliceMode": 1,
        "planeCenter": [1.0, 2.0, 3.0],
        "planeNormal": [0.0, 1.0, 0.0],
    }
    assert (
        round_trip(
            state.slice_settings, state.slice_entry, slice_entry, source_port=None
        )
        == slice_entry
    )
    saved = state.slice_entry(
        model_of(state.slice_settings(slice_entry), source_port=None)
    )
    assert "origin" not in saved  # the desktop places an ortho slice itself

    volume = VOLUME_ENTRY
    assert round_trip(state.volume_settings, state.volume_entry, volume) == volume

    contour = {
        "contourValue": 30.0,
        "opacity": 0.5,
        "ambient": 0.1,
        "diffuse": 0.8,
        "specular": 0.3,
        "specularPower": 50.0,
        "representation": "Wireframe",
        "mapScalars": False,
        "useSolidColor": True,
        "color": "#00ff80",
        "activeScalars": "A",
        "colorByArray": True,
        "colorByArrayName": "B",
    }
    color_map = SimpleNamespace(active_data_array="B")
    assert (
        round_trip(
            state.contour_settings,
            state.contour_entry,
            contour,
            use_internal_color_opacity=True,
            color_opacity=color_map,
        )
        == contour
    )

    threshold = {
        "minimum": 10.0,
        "maximum": 20.0,
        "opacity": 0.5,
        "specular": 0.2,
        "representation": "Points",
        "mapScalars": True,
        "scalarArray": 1,
        "colorByArray": False,
        "colorByArrayName": "",
    }
    assert (
        round_trip(
            state.threshold_settings,
            state.threshold_entry,
            threshold,
            use_internal_color_opacity=False,
        )
        == threshold
    )
    # Once data named the thresholded array, its index; the active one is -1
    named = model_of({"ThresholdBy": "B", "ArrayNames": ["A", "B"]})
    assert state.threshold_array_index(named) == 1
    assert state.threshold_array_index(model_of({"ThresholdBy": ""})) == -1

    molecule = {"ballRadius": 1.5, "stickRadius": 0.2}
    assert (
        round_trip(state.molecule_settings, state.molecule_entry, molecule) == molecule
    )


def test_a_saved_custom_clip_is_the_same_plane():
    entry = {
        "direction": 3,
        "plane": 4,
        "opacity": 0.25,
        "showPlane": False,
        "showArrow": False,
        "invertPlane": True,
        "selectedColor": [1.0, 0.0, 0.0],
        "origin": [0, 10, 5],
        "point1": [10, 10, 5],
        "point2": [0, 0, 5],
    }
    saved = state.clip_entry(model_of(state.clip_settings(entry), source_port=None))
    assert {k: saved[k] for k in entry if k not in ("origin", "point1", "point2")} == {
        k: entry[k] for k in entry if k not in ("origin", "point1", "point2")
    }
    center, normal = state.plane_of_points(saved)
    assert center == pytest.approx((5.0, 5.0, 5.0))
    assert normal[2] < 0
    assert normal[:2] == pytest.approx((0.0, 0.0))
    # an axis-aligned clip saves no corners: the desktop places it itself
    axis = state.clip_entry(
        model_of({**state.clip_settings(entry), "SliceDirection": "YZ Plane"})
    )
    assert "origin" not in axis
    assert axis["direction"] == 1


def test_a_saved_label_map_keeps_its_surface_and_adopted_table():
    entry = {
        **VOLUME_ENTRY,
        "representation": "Volume",
        "surfaceSmoothing": 8,
        "surfaceOpacity": 0.5,
        "volumeLookApplied": False,
    }
    table = {"labels": [{"value": 1, "name": "grain", "color": [0, 0, 1]}]}
    representation = SimpleNamespace(adopted_labels=lambda: table)
    model = model_of(state.label_map_settings(entry), representation=representation)
    saved = state.label_map_entry(model)
    assert {key: saved[key] for key in entry} == entry
    assert saved["adoptedLabelMap"] == table
    representation.adopted_labels = lambda: None
    assert "adoptedLabelMap" not in state.label_map_entry(model)
