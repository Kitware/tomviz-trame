"""Load synthetic state files into a headless app session, and save it.

One session for both formats: the second load also exercises
``PipelineManager.reset``.
"""

import asyncio
import copy
import json

import numpy as np
import pytest
from tomviz_pipeline import DefaultExecutor, SinkGroupNode
from tomviz_pipeline.core.state import pipeline_from_state_dict
from tomviz_pipeline.dataset import Dataset
from tomviz_pipeline.state import read_state_json, write_state_tvh5
from vtkmodules.vtkIOImage import vtkTIFFWriter

from tomviz_web.app import data_model
from tomviz_web.app.pipeline.nodes import RepresentationSinkNode, register_nodes
from tomviz_web.app.pipeline.vtk import convert

SHAPE = (3, 4, 5)
VIEW_ID = 42
CAMERA = {
    "position": [1.0, 2.0, 30.0],
    "focalPoint": [1.0, 2.0, 2.0],
    "viewUp": [0.0, 1.0, 0.0],
    "viewAngle": 30.0,
    "parallelScale": 5.0,
}
COLOR_MAP = {
    "colorSpace": "CIELAB",
    "colors": [10.0, 0.0, 0.0, 1.0, 20.0, 1.0, 0.0, 0.0],
    "points": [10.0, 0.0, 0.5, 0.0, 20.0, 1.0, 0.5, 0.0],
}


def state_dict(tiff_path):
    return {
        "schemaVersion": 2,
        "paletteColor": [0.9, 0.9, 0.9],
        "pipeline": {
            "nextNodeId": 6,
            "nodes": [
                {
                    "id": 1,
                    "type": "source.reader",
                    "label": "volume",
                    "fileNames": [str(tiff_path)],
                    "outputPorts": {
                        "volume": {
                            "type": "ImageData",
                            "persistent": True,
                            "metadata": {"colorOpacityMap": COLOR_MAP},
                        }
                    },
                },
                {
                    "id": 2,
                    "type": "sinkGroup",
                    "label": "Visualizations",
                    "inputPorts": {"volume": {"type": ["ImageData"]}},
                    "outputPorts": {
                        "volume": {"persistent": False, "type": "ImageData"}
                    },
                    "typeInferenceSources": {"volume": "volume"},
                },
                {
                    "id": 3,
                    "type": "sink.slice",
                    "label": "Slice",
                    "inputPorts": {"volume": {"type": ["ImageData"]}},
                    "direction": 1,
                    "slice": 2,
                    "interpolate": True,
                    "viewId": VIEW_ID,
                },
                {
                    "id": 4,
                    "type": "sink.outline",
                    "label": "Outline",
                    "inputPorts": {"volume": {"type": ["ImageData"]}},
                    "visible": False,
                    "viewId": VIEW_ID,
                    "gridColor": [1.0, 0.0, 0.0],
                    "gridVisibility": True,
                    "gridLines": True,
                    "useCustomAxesTitles": True,
                    "customXTitle": "Width",
                },
                {
                    "id": 5,
                    "type": "sink.contour",
                    "label": "Contour",
                    "inputPorts": {"volume": {"type": ["ImageData"]}},
                    "viewId": VIEW_ID + 1,
                    "contourValue": 30.0,
                    "representation": "Wireframe",
                    "colorByArray": True,
                    "colorByArrayName": "Tiff Scalars",  # the reader's name
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
                {
                    "from": {"node": 2, "port": "volume"},
                    "to": {"node": 5, "port": "volume"},
                },
            ],
        },
        "views": [
            {
                "id": VIEW_ID,
                "active": True,
                "interactionMode": "3D",
                "backgroundColor": [[0.1, 0.2, 0.3]],
                "camera": CAMERA,
                "isOrthographic": False,
            },
            {"id": VIEW_ID + 1, "interactionMode": "2D"},
        ],
        # The desktop's layout: the two views side by side, 40 / 60.
        "layouts": [
            {
                "id": 1,
                "items": [
                    [
                        {"direction": 2, "fraction": 0.4, "viewId": 0},
                        {"direction": 0, "fraction": 0.5, "viewId": VIEW_ID},
                        {"direction": 0, "fraction": 0.5, "viewId": VIEW_ID + 1},
                    ]
                ],
            }
        ],
    }


def write_tiff(tmp_path):
    values = np.arange(np.prod(SHAPE), dtype=np.uint16).reshape(SHAPE, order="F")
    tiff_path = tmp_path / "volume.tif"
    writer = vtkTIFFWriter()
    writer.SetFileName(str(tiff_path))
    writer.SetInputData(convert.to_vtk_image(Dataset({"scalars": values})))
    writer.Write()
    return tiff_path


@pytest.fixture
def state_files(tmp_path):
    raw = state_dict(write_tiff(tmp_path))
    tvsm = tmp_path / "session.tvsm"
    tvsm.write_text(json.dumps(raw))

    # A .tvh5 bundles the executed reader's payload.
    register_nodes()
    pipeline = pipeline_from_state_dict(raw)
    assert DefaultExecutor(pipeline).execute()
    tvh5 = tmp_path / "session.tvh5"
    write_state_tvh5(tvh5, raw, pipeline)
    return tvsm, tvh5


async def wait_idle(manager):
    for _ in range(200):
        if not manager.pipeline.is_executing():
            break
        await asyncio.sleep(0.05)
    await asyncio.sleep(0.3)  # loop callbacks and background statistics


def sinks_of(manager):
    return {
        m.node.id: m
        for m in manager.model.nodes
        if isinstance(m, data_model.SinkNodeModel)
    }


async def start_app():
    from tomviz_web.app.core import Tomviz

    app = Tomviz()
    serve = asyncio.create_task(
        app.server.start(exec_mode="coroutine", port=0, open_browser=False, timeout=0)
    )
    await app.server.ready
    return app, serve


async def run_session(tvsm, tvh5):
    app, serve = await start_app()
    server = app.server
    manager = app.ctx.pipeline
    executed = []
    manager.executor.node_execution_started.connect(lambda n: executed.append(n.id))
    layouts = []
    manager.restore_layout = layouts.append  # what would reach dockview

    try:
        # ---- .tvsm: everything re-executes
        await manager.load_state_file(tvsm)
        await wait_idle(manager)
        check_session(manager, server)
        check_layout(manager, server, layouts[-1])
        assert executed[0] == 1  # the reader ran first
        assert set(executed) == {1, 2, 3, 4, 5}

        # ---- the outline's axes follow its visibility; hiding the axes
        # turns the grid and the custom titles off, as on the desktop
        outline = sinks_of(manager)[4]
        grid_axes = outline.representation.grid_axes
        outline.Visibility = True
        await asyncio.sleep(0.1)
        assert grid_axes.GetVisibility()
        outline.ShowGridAxes = False
        await asyncio.sleep(0.1)
        assert not grid_axes.GetVisibility()
        assert (outline.ShowGrid, outline.UseCustomAxesTitles) == (False, False)
        assert not grid_axes.GetGenerateGrid()
        assert grid_axes.GetXTitle() == "X"

        # ---- .tvh5 in the same session: reset, then only the sinks run
        executed.clear()
        await manager.load_state_file(tvh5)
        await wait_idle(manager)
        check_session(manager, server)
        assert set(executed) == {2, 3, 4, 5}  # the group runs (trivially) too
        assert len(manager.views) == 2
        assert len(layouts) == 2  # one restore per load
        assert len(manager.model.nodes) == 5
    finally:
        manager.shutdown()
        await server.stop()
        serve.cancel()


def check_session(manager, server):
    pipeline = manager.pipeline
    sinks = sinks_of(manager)
    assert set(sinks) == {3, 4, 5}
    assert all(
        isinstance(pipeline.node_by_id(i), RepresentationSinkNode) for i in sinks
    )

    source = manager.model.roots[0]
    assert source.label == "volume"
    assert manager.model.active_node == [source._id]
    port = source.primary_output_model
    assert port.has_data
    assert port.image.dimensions == SHAPE
    assert port.data_location == "memory"
    assert server.state.tip_port_id == port._id
    assert server.state.active_port_id == port._id

    # The desktop's sink group survives: the sinks read the reader's port
    # through its passthrough, and the models mirror the links.
    group = manager.node_models[2]
    assert isinstance(group, data_model.SinkGroupNodeModel)
    assert isinstance(pipeline.node_by_id(2), SinkGroupNode)
    assert group.inputs[0].link is port
    assert group.state == "Current"
    for sink in sinks.values():
        assert sink.inputs[0].link is group.outputs[0]
        assert sink.source_port is port
        assert sink.state == "Current"

    slice_model, outline, contour = sinks[3], sinks[4], sinks[5]
    # A contour colored by its own array: that array on its own map
    assert (contour.IsoValue, contour.Mode) == (30.0, "Wireframe")
    assert contour.use_internal_color_opacity is True
    assert contour.color_opacity is not port.color_opacity
    assert contour.color_opacity.active_data_array == "Tiff Scalars"
    assert contour.view is not sinks[3].view  # the second saved view
    assert contour.representation.contour.GetValue(0) == 30.0
    assert (slice_model.SliceDirection, slice_model.Slice) == ("YZ Plane", 2)
    assert slice_model.SliceMax == SHAPE[0] - 1
    assert slice_model.Interpolate is True
    representation = slice_model.representation
    assert representation.property.GetInterpolationTypeAsString() == "Linear"
    assert representation.actor.visibility
    assert outline.Visibility is False
    assert not outline.representation.actor.visibility
    assert (outline.Color, outline.ShowGridAxes, outline.ShowGrid) == (
        "#ff0000",
        True,
        True,
    )
    grid_axes = outline.representation.grid_axes
    assert not grid_axes.GetVisibility()  # hidden with the outline
    assert grid_axes.GetGenerateGrid()
    assert grid_axes.GetGridBounds() == (0.0, 2.0, 0.0, 3.0, 0.0, 4.0)
    assert (grid_axes.GetXTitle(), grid_axes.GetYTitle()) == ("Width", "Y")
    assert outline.representation.property.GetColor() == (1.0, 0.0, 0.0)

    color_map = port.color_opacity
    assert color_map.color_space == "Lab"
    assert color_map.color_range == [10.0, 20.0]  # kept from the file
    assert color_map.data_range[:2] == (0.0, float(np.prod(SHAPE) - 1))

    view = slice_model.view
    assert server.state.active_view_id == view._id
    assert view.background == (0.1, 0.2, 0.3)
    assert view.camera_initialized
    camera = view.vtk_view.camera
    assert camera["position"] == CAMERA["position"]  # not refit by the data
    assert camera["parallelProjection"] is False


def check_layout(manager, server, layout):
    """The two windows side by side, 40 / 60, the first one active."""
    active = manager.views[server.state.active_view_id]
    other = next(v for v in manager.views.values() if v is not active)
    grid = layout["grid"]
    assert grid["orientation"] == "HORIZONTAL"
    left, right = grid["root"]["data"]
    assert (left["data"]["views"], left["size"]) == ([active.vtk_id], 400.0)
    assert (right["data"]["views"], right["size"]) == ([other.vtk_id], 600.0)
    assert layout["activeGroup"] == left["data"]["id"]
    entry = layout["panels"][active.vtk_id]
    assert entry["contentComponent"] == "DockPanel"
    assert entry["tabComponent"] == "tomviz-dockview-tab"
    assert entry["params"] == {
        "templateName": active.tpl_name,
        "viewState": active.local_state._id,
    }
    assert other.local_state.interactive_3d is False


def isolate_app(tmp_path, monkeypatch):
    # The app reads its catalog configuration from the command line (default:
    # the user's home); keep the test off the developer's own files.
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({"directories": [], "modules": [], "favorites": []}))
    # Under pytest, trame only reads its arguments from TRAME_ARGS.
    monkeypatch.setenv(
        "TRAME_ARGS",
        f"--catalog {catalog} --settings {catalog.parent / 'settings.json'} --read-only",
    )


def test_state_files_load_into_a_session(state_files, tmp_path, monkeypatch):
    isolate_app(tmp_path, monkeypatch)
    asyncio.run(run_session(*state_files))


# ---- saving -----------------------------------------------------------------


def saving_state(tiff_path):
    """The session file plus what saving carries through untouched: an inert
    ruler in the second view, a slice key and port metadata the app does not
    restore, and a top-level section it does not know. The desktop's
    animation is dropped."""
    raw = state_dict(tiff_path)
    nodes = {entry["id"]: entry for entry in raw["pipeline"]["nodes"]}
    nodes[1]["outputPorts"]["volume"]["metadata"]["spacing"] = [1.0, 1.0, 2.0]
    nodes[3]["linked"] = True
    raw["pipeline"]["nodes"].append(
        {
            "id": 6,
            "type": "sink.ruler",
            "label": "Ruler",
            "inputPorts": {"volume": {"type": ["ImageData"]}},
            "viewId": VIEW_ID + 1,
            "visible": True,
            "point1": [0.0, 0.0, 0.0],
            "point2": [1.0, 2.0, 3.0],
        }
    )
    raw["pipeline"]["links"].append(
        {"from": {"node": 2, "port": "volume"}, "to": {"node": 6, "port": "volume"}}
    )
    raw["pipeline"]["nextNodeId"] = 7
    raw["custom"] = {"kept": True}
    raw["animation"] = {"numberOfFrames": 10}
    return raw


def links_of(raw):
    return sorted(
        (link["from"]["node"], link["to"]["node"]) for link in raw["pipeline"]["links"]
    )


def check_saved(raw, original):
    nodes = {entry["id"]: entry for entry in raw["pipeline"]["nodes"]}
    loaded = {entry["id"]: entry for entry in original["pipeline"]["nodes"]}
    assert set(nodes) == {1, 2, 3, 4, 5, 6}
    assert links_of(raw) == links_of(original)
    assert raw["custom"] == {"kept": True}
    assert raw["paletteColor"] == original["paletteColor"]
    assert "animation" not in raw

    views = {view["id"]: view for view in raw["views"]}
    assert set(views) == {VIEW_ID, VIEW_ID + 1}
    first = views[VIEW_ID]
    assert first["active"] is True
    assert (first["xmlName"], first["servers"]) == ("RenderView", 21)
    assert first["backgroundColor"] == [[0.1, 0.2, 0.3]]
    assert first["camera"]["position"] == CAMERA["position"]
    assert (first["interactionMode"], first["isOrthographic"]) == ("3D", False)
    assert views[VIEW_ID + 1]["interactionMode"] == "2D"
    assert "active" not in views[VIEW_ID + 1]
    # the desktop's own layout, from what the dock reported
    assert raw["layouts"][0]["items"] == original["layouts"][0]["items"]

    slice_entry, outline, contour = nodes[3], nodes[4], nodes[5]
    assert (slice_entry["direction"], slice_entry["slice"]) == (1, 1)
    assert slice_entry["interpolate"] is True
    assert (slice_entry["viewId"], slice_entry["visible"]) == (VIEW_ID, True)
    assert slice_entry["linked"] is True  # not restored, written back
    assert outline["visible"] is False
    assert outline["gridColor"] == [0.0, 1.0, 0.0]
    assert outline["customXTitle"] == "Width"
    assert (contour["contourValue"], contour["representation"]) == (40.0, "Wireframe")
    assert (contour["colorByArray"], contour["colorByArrayName"]) == (
        True,
        "Tiff Scalars",
    )
    assert contour["useDetachedColorMap"] is True
    assert contour["viewId"] == VIEW_ID + 1
    assert nodes[6] == loaded[6]  # the ruler, as loaded

    reader = nodes[1]
    assert reader["fileNames"] == loaded[1]["fileNames"]  # absolute: kept
    metadata = reader["outputPorts"]["volume"]["metadata"]
    assert metadata["spacing"] == [1.0, 1.0, 2.0]
    assert metadata["activeScalars"] == "Tiff Scalars"
    colors = metadata["colorOpacityMap"]["colors"]
    assert (colors[0], colors[-4]) == (12.0, 18.0)


def check_reloaded(manager, server, layout):
    sinks = sinks_of(manager)
    assert set(sinks) == {3, 4, 5}
    ruler = manager.pipeline.node_by_id(6)  # inert, its settings kept
    assert ruler.settings["point2"] == [1.0, 2.0, 3.0]
    assert 6 in manager.node_models

    slice_model, outline, contour = sinks[3], sinks[4], sinks[5]
    assert (slice_model.SliceDirection, slice_model.Slice) == ("YZ Plane", 1)
    assert (outline.Color, outline.Visibility) == ("#00ff00", False)
    assert contour.IsoValue == 40.0
    assert contour.use_internal_color_opacity is True
    assert contour.color_opacity.active_data_array == "Tiff Scalars"
    assert slice_model.view.state_id == VIEW_ID
    assert contour.view.state_id == VIEW_ID + 1
    port = manager.model.roots[0].primary_output_model
    assert port.color_opacity.color_range == [12.0, 18.0]
    assert slice_model.view.vtk_view.camera["position"] == CAMERA["position"]
    check_layout(manager, server, layout)


async def check_save_dialog(app, folder):
    """The toolbar's save dialog: at the loaded file, naming a state file."""
    server, saver = app.server, app.ctx.state_saver
    state = server.state
    saver.open(app.ctx.pipeline.state_path)
    assert state.tomviz_save_loader
    assert (state.tomviz_save_filename, state.tomviz_save_format) == (
        "session",
        ".tvsm",
    )
    # Folders and state files only; the loaded file is there to replace
    assert [e["name"] for e in state.tomviz_save_listing] == ["session.tvsm"]
    assert (state.tomviz_save_target, state.tomviz_save_exists) == (
        "session.tvsm",
        True,
    )
    state.tomviz_save_filename = "copy"
    state.tomviz_save_format = ".tvh5"
    saver._update_target()  # the state change listener, without a client
    assert (state.tomviz_save_target, state.tomviz_save_exists) == (
        "copy.tvh5",
        False,
    )
    state.tomviz_save_filename = "copy.tvsm"  # a name with its own format
    assert saver.target() == folder.resolve() / "copy.tvsm"

    state.tomviz_save_filename = "copy"
    saver.confirm_save()
    assert not state.tomviz_save_loader
    for _ in range(100):
        await asyncio.sleep(0.05)
        if (folder / "copy.tvh5").exists() and not state.state_saving:
            break
    assert read_state_json(folder / "copy.tvh5")["pipeline"]["nodes"]


async def save_session(tmp_path, tvsm, original):
    app, serve = await start_app()
    server, manager = app.server, app.ctx.pipeline
    executed = []
    manager.executor.node_execution_started.connect(lambda n: executed.append(n.id))
    layouts = []
    manager.restore_layout = layouts.append  # what would reach dockview

    async def load(path):
        await manager.load_state_file(path)
        await wait_idle(manager)
        manager.on_layout_changed(layouts[-1])  # the client reports it back

    try:
        await load(tvsm)
        await check_save_dialog(app, tmp_path)
        sinks = sinks_of(manager)
        sinks[3].Slice = 1
        sinks[4].Color = "#00ff00"
        sinks[5].IsoValue = 40.0
        port = manager.model.roots[0].primary_output_model
        port.color_opacity.color_range = [12.0, 18.0]
        await asyncio.sleep(0.2)

        folder = tmp_path / "saved"
        folder.mkdir()
        saved_tvsm, saved_tvh5 = folder / "session.tvsm", folder / "session.tvh5"
        assert await manager.save_state_file(saved_tvsm)
        assert await manager.save_state_file(saved_tvh5)
        assert not manager.pipeline.is_executing()  # saving runs nothing
        assert server.state.state_saving is False
        assert manager.state_path == saved_tvh5
        check_saved(read_state_json(saved_tvsm), original)
        bundled = read_state_json(saved_tvh5)
        check_saved(bundled, original)
        reader_port = bundled["pipeline"]["nodes"][0]["outputPorts"]["volume"]
        assert reader_port["dataRef"] == {"container": "h5", "path": "/data/1/volume"}

        await load(saved_tvsm)
        check_reloaded(manager, server, layouts[-1])
        executed.clear()
        await load(saved_tvh5)
        check_reloaded(manager, server, layouts[-1])
        assert set(executed) == {2, 3, 4, 5}  # the reader's data came with it

        # Closing the second view takes its sinks along, the inert one too
        second = next(
            w for w in manager.views.values() if w.local_state.state_id == VIEW_ID + 1
        )
        manager.remove_view(second.local_state._id)
        assert 5 not in manager.node_models
        assert 6 not in manager.node_models
        # A new view gets the next free id and a place in the layout
        manager.add_view()
        again = folder / "again.tvsm"
        assert await manager.save_state_file(again)
        raw = read_state_json(again)
        assert {entry["id"] for entry in raw["pipeline"]["nodes"]} == {1, 2, 3, 4}
        assert [view["id"] for view in raw["views"]] == [VIEW_ID, VIEW_ID + 1]
        cells = [item["viewId"] for item in raw["layouts"][0]["items"][0]]
        assert cells == [0, VIEW_ID, VIEW_ID + 1]
    finally:
        manager.shutdown()
        await server.stop()
        serve.cancel()


def test_a_saved_session_loads_back(tmp_path, monkeypatch):
    isolate_app(tmp_path, monkeypatch)
    raw = saving_state(write_tiff(tmp_path))
    tvsm = tmp_path / "session.tvsm"
    tvsm.write_text(json.dumps(raw))
    asyncio.run(save_session(tmp_path, tvsm, copy.deepcopy(raw)))
