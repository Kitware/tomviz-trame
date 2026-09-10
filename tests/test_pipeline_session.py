"""Editing a pipeline in a headless app session: sink groups, the tip port,
transforms inserted at the tip, and the models the widget renders."""

import asyncio
import json

import numpy as np
import pytest
from tomviz_pipeline import (
    PipelineSettings,
    SinkGroupNode,
    TransformPersistenceDefault,
)
from tomviz_pipeline.dataset import Dataset
from vtkmodules.vtkIOImage import vtkTIFFWriter

from tomviz_trame.app import data_model
from tomviz_trame.app.pipeline.vtk import convert

SHAPE = (3, 4, 5)


@pytest.fixture
def tiff(tmp_path):
    values = np.arange(np.prod(SHAPE), dtype=np.uint16).reshape(SHAPE, order="F")
    path = tmp_path / "volume.tif"
    writer = vtkTIFFWriter()
    writer.SetFileName(str(path))
    writer.SetInputData(convert.to_vtk_image(Dataset({"scalars": values})))
    writer.Write()
    return path


CATALOG_ENTRY = {
    "name": "SessionAddConstant",
    "label": "Session Add Constant",
    "description": "Add a constant",
    "parameters": [{"name": "constant", "type": "double", "default": 3}],
}
SCRIPT = """
def transform(dataset, constant=3):
    dataset.active_scalars = dataset.active_scalars + constant
"""


@pytest.fixture
def catalog(tmp_path):
    folder = tmp_path / "entries"
    folder.mkdir()
    (folder / "SessionAddConstant.json").write_text(json.dumps(CATALOG_ENTRY))
    (folder / "SessionAddConstant.py").write_text(SCRIPT)
    config = tmp_path / "catalog.json"
    config.write_text(
        json.dumps({"directories": [str(folder)], "modules": [], "favorites": []})
    )
    return config


async def wait_idle(manager):
    for _ in range(200):
        if not manager.pipeline.is_executing():
            break
        await asyncio.sleep(0.05)
    await asyncio.sleep(0.3)


async def settle():
    await asyncio.sleep(0.1)


async def run_session(tiff):
    from tomviz_trame.app.core import Tomviz

    app = Tomviz(server="editing-session")  # its own server: one app per test
    server = app.server
    serve = asyncio.create_task(
        server.start(exec_mode="coroutine", port=0, open_browser=False, timeout=0)
    )
    await server.ready
    manager = app.ctx.pipeline
    state = server.state
    assert "SessionAddConstant" in app.ctx.catalog.entries

    try:
        # ---- load: source, a group on its output, the default sinks in it
        source_id = manager.load_file(tiff)
        await wait_idle(manager)
        source = data_model.get_instance(source_id)
        assert isinstance(source, data_model.SourceNodeModel)
        port = source.primary_output_model
        assert state.tip_port_id == port._id
        assert manager.model.active_node == [source._id]
        assert state.active_port_id == port._id
        assert state.pipeline_executing is False

        groups = [n for n in manager.pipeline.nodes if isinstance(n, SinkGroupNode)]
        assert len(groups) == 1
        group_model = manager.node_models[groups[0].id]
        assert isinstance(group_model, data_model.SinkGroupNodeModel)
        assert group_model.inputs[0].link is port
        assert group_model.state == "Current"
        sinks = [
            m for m in manager.model.nodes if isinstance(m, data_model.SinkNodeModel)
        ]
        assert {m.representation_type for m in sinks} == {"OUTLINE", "SLICE"}
        for sink in sinks:
            assert sink.inputs[0].link is group_model.outputs[0]
            assert sink.source_port is port
            assert sink.state == "Current"
            assert sink.node_id == sink.node.id
        assert port.data_location == "memory"
        assert port.has_data

        # ---- a third sink joins the same group
        volume_id = manager.add_sink(state.active_view_id, "VOLUME")
        await wait_idle(manager)
        volume = data_model.get_instance(volume_id)
        assert volume.inputs[0].link is group_model.outputs[0]
        assert len(groups[0].sinks()) == 3
        assert volume.state == "Current"

        # ---- a transform at the tip takes the group with it and is selected;
        # its output inherits the upstream color map, stretched to its range
        port.color_opacity.active_color_preset = "Viridis (matplotlib)"
        await settle()  # the preset watcher fills the points
        source_colors = [row[1:] for row in port.color_opacity.color_points]
        transform_id = manager.add_transform("SessionAddConstant")
        await wait_idle(manager)
        transform = data_model.get_instance(transform_id)
        assert isinstance(transform, data_model.TransformNodeModel)
        inherited = transform.outputs[0].color_opacity
        assert inherited.active_color_preset == "Viridis (matplotlib)"
        assert [row[1:] for row in inherited.color_points] == source_colors
        # The +3 data spans 3..62, the source 0..59: stretched, not copied.
        assert inherited.color_range == [3.0, 62.0]
        xs = [row[0] for row in inherited.color_points]
        assert (min(xs), max(xs)) == (3.0, 62.0)
        assert port.color_opacity.color_range == [0.0, 59.0]
        assert transform.inputs[0].link is port
        assert group_model.inputs[0].link is transform.outputs[0]
        assert manager.model.active_node == [transform._id]
        assert state.tip_port_id == transform.outputs[0]._id
        assert state.active_port_id == transform.outputs[0]._id
        assert state.property_templates == ["transform"]
        for sink in [*sinks, volume]:
            assert sink.source_port is transform.outputs[0]
            assert sink.state == "Current"
        assert transform.state == "Current"
        assert transform.outputs[0].has_data
        assert transform.outputs[0].node is transform
        np.testing.assert_array_equal(
            transform.outputs[0].payload.active_scalars,
            port.payload.active_scalars + 3,
        )

        # ---- effective types follow the upstream port, models included
        assert transform.outputs[0].port_type == "ImageData"
        port.port.port_type = "TiltSeries"  # what the reader does for a stack
        await settle()
        assert transform.outputs[0].port.port_type == "TiltSeries"
        assert transform.outputs[0].port_type == "TiltSeries"
        assert group_model.outputs[0].port_type == "TiltSeries"
        assert transform.inputs[0].link_valid is True
        port.port.port_type = "ImageData"
        await settle()
        assert transform.outputs[0].port_type == "ImageData"

        # ---- selecting the source moves the tip back to it; a port and a
        # link can be selected too; deselecting keeps the branch tip
        manager.model.active_node = [source._id]
        await settle()
        assert state.tip_port_id == port._id
        assert state.active_data_id == source._id
        manager.model.active_node = [transform.outputs[0]._id]
        await settle()
        assert state.tip_port_id == transform.outputs[0]._id
        assert state.active_data_id == transform._id
        assert state.property_templates == ["data_info"]  # a port shows its data
        manager.model.active_node = [group_model.inputs[0]._id]  # the link
        await settle()
        assert state.tip_port_id == transform.outputs[0]._id
        manager.model.active_node = [volume._id]
        await settle()
        assert state.active_representation_id == volume._id
        assert state.tip_port_id == transform.outputs[0]._id
        manager.model.active_node = []
        await settle()
        assert state.tip_port_id == transform.outputs[0]._id
        assert state.active_data_id == transform._id  # the tip's data node

        # ---- the widget's actions: menus, deletion, breakpoints
        assert [a["id"] for a in manager.menu_actions("node", volume._id)] == [
            "leave_group",
            "delete",
        ]
        assert [a["id"] for a in manager.menu_actions("node", transform._id)] == [
            "add_transform",
            "delete",
        ]
        assert len(manager.menu_actions("port", port._id)) == 3  # persistence
        manager.run_menu_action("add_transform", "node", source._id)
        await settle()
        assert manager.model.active_node == [source._id]
        assert state.select_transform is True
        state.select_transform = False
        manager.run_menu_action("delete", "node", volume._id)
        await settle()
        assert volume._id not in {m._id for m in manager.model.nodes}
        assert len(groups[0].sinks()) == 2
        manager.toggle_breakpoint(transform._id)
        assert transform.breakpoint is True
        assert transform.node.breakpoint is True
        manager.toggle_breakpoint(transform._id)
        assert transform.breakpoint is False

        # ---- links: remove, re-create by id (drag-to-link), validation
        group_input = group_model.inputs[0]
        manager.model.active_node = [group_input._id]
        await settle()
        assert manager.remove_link(group_input._id)
        await settle()
        assert group_input.link is None
        assert manager.model.active_node == []
        for sink in sinks:
            assert sink.node.representation.image is None
            assert not sink.node.representation.actor.visibility
        assert not manager.create_link(
            transform.outputs[0]._id, transform.inputs[0]._id
        )
        assert manager.create_link(transform.outputs[0]._id, group_input._id)
        await wait_idle(manager)
        assert group_input.link is transform.outputs[0]
        for sink in sinks:
            assert sink.node.representation.image is not None
            assert sink.state == "Current"
            assert sink.source_port is transform.outputs[0]
        # Moving a group between ports rebinds its sinks' color maps; the
        # slice stays opaque (its lookup table never takes the opacity
        # function, whose low end would hide the data).
        slice_model = next(s for s in sinks if s.representation_type == "SLICE")
        lut = slice_model.representation.mapper.GetLookupTable()
        assert lut is slice_model.color_opacity.lut.table
        assert {
            lut.GetTableValue(i)[3] for i in range(lut.GetNumberOfTableValues())
        } == {1.0}
        assert slice_model.representation.actor.visibility
        assert [a["id"] for a in manager.menu_actions("link", group_input._id)] == [
            "delete"
        ]

        # ---- port persistence
        out = transform.outputs[0]
        manager.set_port_persistence(out._id, "disk")
        await settle()
        assert (out.persistent, out.persistence_mode) == (True, "disk")
        actions = manager.menu_actions("port", out._id)
        assert [a["id"] for a in actions] == [
            "persist_memory",
            "persist_disk",
            "transient",
        ]
        assert [a["checked"] for a in actions] == [False, True, False]
        manager.set_port_persistence(out._id, "transient")
        await settle()
        assert out.persistent is False
        manager.set_port_persistence(out._id, "memory")  # re-runs if the data went
        await wait_idle(manager)
        assert (out.persistent, out.persistence_mode) == (True, "memory")
        assert out.has_data
        assert manager.menu_actions("port", group_model.outputs[0]._id) == []

        # ---- groups: leave, then a new group around the sink
        outline = next(s for s in sinks if s.representation_type == "OUTLINE")
        assert [a["id"] for a in manager.menu_actions("node", outline._id)] == [
            "leave_group",
            "delete",
        ]
        manager.leave_group(outline._id)
        await wait_idle(manager)
        assert outline.inputs[0].link is out
        assert outline.state == "Current"
        assert [a["id"] for a in manager.menu_actions("node", outline._id)] == [
            "create_group",
            "delete",
        ]
        manager.create_group_for(outline._id)
        await wait_idle(manager)
        new_group = outline.inputs[0].link.node
        assert isinstance(new_group, data_model.SinkGroupNodeModel)
        assert new_group is not group_model
        assert new_group.inputs[0].link is out
        assert outline.state == "Current"

        # ---- pause / resume, default persistence
        manager.set_paused(True)
        await settle()
        assert state.pipeline_paused is True
        manager.set_paused(False)
        await settle()
        assert state.pipeline_paused is False
        manager.set_transform_persistence_default("disk")
        assert state.transform_persistence_default == "disk"
        assert (
            PipelineSettings.instance().transform_persistence_default
            is TransformPersistenceDefault.OnDisk
        )
        manager.set_transform_persistence_default("memory")

        # ---- deleting the transform: consumers lose their input, tip falls back
        manager.model.active_node = [transform._id]
        await settle()
        assert manager.run_menu_action("delete", "node", transform._id) is None
        await settle()
        assert transform._id not in {m._id for m in manager.model.nodes}
        assert manager.pipeline.node_by_id(transform.node_id) is None
        assert group_model.inputs[0].link is None
        assert new_group.inputs[0].link is None
        assert manager.model.active_node == []
        assert state.tip_port_id == port._id
        for sink in sinks:
            assert sink.node.representation.image is None
    finally:
        manager.shutdown()
        await server.stop()
        serve.cancel()


def test_editing_a_pipeline_in_a_session(tiff, catalog, monkeypatch):
    # Under pytest, trame only reads its arguments from TRAME_ARGS.
    monkeypatch.setenv(
        "TRAME_ARGS",
        f"--catalog {catalog} --settings {catalog.parent / 'settings.json'} --read-only",
    )
    asyncio.run(run_session(tiff))
