"""The transform editor, driven through the app: it stages a copy of a
catalog node's definition (whose label names the node) and script; Cancel drops every edit
(the parameter panel's too), Apply commits them all through the library
(rebuilding the parameters panel when the declared parameters change) and
re-executes; an edit the library refuses leaves the node untouched.

A new node waits for the editor before it runs: OK runs it, Cancel removes
it and puts the graph back without re-running anything. A node with more
inputs waits once its last input is linked, and Cancel removes that link.

The Execution tab moves a node to an external Python environment (the one
the tests run in, a real one) and back, checking the environment picked
through the folder browser."""

import asyncio
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest
from tomviz_pipeline import ExternalNodeExecutor, SinkGroupNode
from tomviz_pipeline.dataset import Dataset
from tomviz_pipeline.writers import write_emd

from tomviz_web.app import data_model

SHAPE = (4, 4, 3)

SCALE_DEFINITION = {
    "schemaVersion": 2,
    "name": "Scale",
    "label": "Scale",
    "inputs": [{"name": "volume", "type": "ImageData"}],
    "outputs": [{"name": "volume", "type": "ImageData"}],
    "parameters": [{"name": "factor", "type": "double", "default": 2.0}],
}

SCALE_SCRIPT = """\
from tomviz_pipeline.kernels import TransformKernel


class Scale(TransformKernel):
    def transform(self, inputs, factor=2.0, **_):
        dataset = inputs["volume"]
        dataset.active_scalars = dataset.active_scalars * factor
        return {"volume": dataset}
"""

OFFSET_SCRIPT = SCALE_SCRIPT.replace("* factor", "* factor + _.get('offset', 0.0)")


def ramp():
    size = int(np.prod(SHAPE))
    return np.arange(size, dtype=np.float32).reshape(SHAPE, order="F")


async def wait_idle(manager):
    for _ in range(200):
        if not manager.pipeline.is_executing():
            break
        await asyncio.sleep(0.05)
    await asyncio.sleep(0.3)


async def wait_for(predicate, timeout=60.0):
    """Poll until ``predicate()`` holds; whether it did."""
    for _ in range(int(timeout / 0.05)):
        if predicate():
            return True
        await asyncio.sleep(0.05)
    return predicate()


def scalars(model):
    return model.node.output_ports()[0].data().payload.active_scalars


def with_parameters(definition, *parameters):
    return {**definition, "parameters": list(parameters)}


async def run_session(volume_file):
    from tomviz_web.app.core import Tomviz

    app = Tomviz(server="editor-session")
    server = app.server
    serve = asyncio.create_task(
        server.start(exec_mode="coroutine", port=0, open_browser=False, timeout=0)
    )
    await asyncio.sleep(0.5)
    manager = app.ctx.pipeline
    dialog = app.ctx.transform_editor
    editor = dialog.editor

    try:
        manager.load_file(volume_file)
        await wait_idle(manager)

        # A v1 script is editable too.
        blur = data_model.get_instance(
            manager.add_transform("GaussianFilter", parameters={"sigma": 1.0})
        )
        await wait_idle(manager)
        dialog.open(blur._id)
        assert editor.definition["name"] == "GaussianFilter"
        assert editor.script
        assert editor.script == blur.node.script
        dialog.cancel()
        blurred = scalars(blur)

        scale = data_model.get_instance(manager.add_transform("Scale"))
        await wait_idle(manager)
        assert scale.state == "Current"
        np.testing.assert_allclose(scalars(scale), blurred * 2.0)

        # Opening stages a copy of the node's definition and script.
        dialog.open(scale._id)
        assert editor.show
        assert (editor.definition, editor.script) == (SCALE_DEFINITION, SCALE_SCRIPT)

        # Cancel drops every edit, the parameter panel's included.
        editor.script = OFFSET_SCRIPT
        editor.definition = {**with_parameters(SCALE_DEFINITION), "label": "Renamed"}
        scale.parameters.set(factor=3.0)
        dialog.cancel()
        assert not editor.show
        assert scale.node.label == "Scale"
        assert scale.node.script == SCALE_SCRIPT
        assert json.loads(scale.node.json_description) == SCALE_DEFINITION
        assert scale.node.parameter("factor") == 2.0
        assert scale.parameters.values["factor"] == 2.0
        assert scale.node.state.value == "Current"

        # Apply commits them all and runs once: a new parameter gets a
        # value and a control in the same panel, and the panel value typed
        # before carries over.
        dialog.open(scale._id)
        assert editor.script == SCALE_SCRIPT
        panel = scale.parameters
        template = panel.panel_html()
        scale.parameters.set(factor=3.0)
        editor.script = OFFSET_SCRIPT
        editor.definition = with_parameters(
            {**SCALE_DEFINITION, "label": "Scaled"},
            *SCALE_DEFINITION["parameters"],
            {"name": "offset", "type": "double", "default": 1.0},
        )
        assert dialog.apply()
        assert editor.message_type == "success"
        assert scale.node.label == scale.label == "Scaled"
        assert scale.parameters is panel
        assert server.state[panel.template_key] == panel.panel_html() != template
        assert "offset" in panel.panel_html()
        assert scale.parameters.values["offset"] == 1.0
        assert scale.node.parameter("factor") == 3.0
        assert scale.definition == editor.definition
        await wait_idle(manager)
        assert scale.state == "Current"
        np.testing.assert_allclose(scalars(scale), blurred * 3.0 + 1.0)

        # Retyping a parameter resets its value, and says so.
        retyped = with_parameters(
            {**SCALE_DEFINITION, "label": "Scaled"},
            {"name": "factor", "type": "int", "default": 4},
            {"name": "offset", "type": "double", "default": 1.0},
        )
        editor.definition = retyped
        assert dialog.apply()
        assert editor.message_type == "warning"
        assert "factor" in editor.message
        assert scale.node.parameter("factor") == 4
        await wait_idle(manager)

        # An edit changing the ports is refused, and OK stays open on it.
        before = scale.node.json_description
        panel = scale.parameters
        editor.definition = {
            **retyped,
            "outputs": [{"name": "other", "type": "ImageData"}],
        }
        dialog.ok()
        assert editor.show
        assert editor.message_type == "error"
        assert "outputs" in editor.message
        assert scale.node.json_description == before
        assert scale.parameters is panel

        # OK applies and closes.
        editor.definition = {**retyped, "label": "Final"}
        dialog.ok()
        assert not editor.show
        assert scale.node.label == "Final"
    finally:
        manager.shutdown()
        await server.stop()
        serve.cancel()


async def run_pending_session(volume_file, other_file):
    from tomviz_web.app.core import Tomviz

    app = Tomviz(server="pending-session")
    server = app.server
    serve = asyncio.create_task(
        server.start(exec_mode="coroutine", port=0, open_browser=False, timeout=0)
    )
    await asyncio.sleep(0.5)
    manager = app.ctx.pipeline
    dialog = app.ctx.transform_editor

    def group_feed():
        group = next(n for n in manager.pipeline.nodes if isinstance(n, SinkGroupNode))
        return group, group.input_ports()[0].link.from_port

    def sinks():
        return [
            m for m in manager.model.nodes if isinstance(m, data_model.SinkNodeModel)
        ]

    try:
        source = data_model.get_instance(manager.load_file(volume_file))
        await wait_idle(manager)
        group, feed = group_feed()
        assert feed is source.node.output_ports()[0]
        selection = list(manager.model.active_node)

        # A new node is held: the visualizations move to it, nothing runs.
        scale = data_model.get_instance(manager.add_transform("Scale", pending=True))
        assert manager.is_pending(scale._id)
        assert scale.node.breakpoint
        assert scale.breakpoint
        assert group_feed()[1] is scale.node.output_ports()[0]
        manager.execute()
        await wait_idle(manager)
        assert scale.node.state.value == "New"

        # Cancel: the graph as it was, nothing stale, the pictures kept.
        dialog.open(scale._id)
        dialog.cancel()
        await wait_idle(manager)
        assert scale.node not in manager.pipeline.nodes
        assert group_feed()[1] is feed
        assert group.state.value == "Current"
        for sink in sinks():
            assert sink.node.state.value == "Current"
            assert sink.source_port is source.outputs[0]
            assert sink.node._has_data
        assert manager.model.active_node == selection
        assert not manager.pipeline.is_executing()

        # OK releases it and runs it.
        scale = data_model.get_instance(manager.add_transform("Scale", pending=True))
        dialog.open(scale._id)
        dialog.ok()
        await wait_idle(manager)
        assert not manager.is_pending(scale._id)
        assert not scale.node.breakpoint
        assert scale.state == "Current"
        np.testing.assert_allclose(scalars(scale), ramp() * 2.0)

        # After an Apply the node is committed: Cancel only closes.
        again = data_model.get_instance(manager.add_transform("Scale", pending=True))
        dialog.open(again._id)
        assert dialog.apply()
        await wait_idle(manager)
        dialog.cancel()
        assert again.node in manager.pipeline.nodes
        assert again.state == "Current"

        # A node with more inputs is not held while some are unlinked...
        combine = data_model.get_instance(
            manager.add_transform("combine_datasets", pending=True)
        )
        assert not manager.is_pending(combine._id)
        assert not combine.node.breakpoint
        second = combine.inputs[1]
        other = data_model.get_instance(manager.load_file(other_file))
        await wait_idle(manager)

        # ...but once the last one is linked; Cancel removes that link and
        # leaves the user's own breakpoint alone.
        manager.toggle_breakpoint(combine._id)
        assert manager.create_link(other.outputs[0]._id, second._id)
        assert manager.is_pending(combine._id)
        dialog.open(combine._id)
        dialog.cancel()
        assert combine.node in manager.pipeline.nodes
        assert second.port.link is None
        assert combine.node.breakpoint
        manager.toggle_breakpoint(combine._id)

        assert manager.create_link(other.outputs[0]._id, second._id)
        await wait_idle(manager)
        assert manager.is_pending(combine._id)
        assert combine.state != "Current"
        dialog.open(combine._id)
        dialog.ok()
        await wait_idle(manager)
        assert combine.state == "Current"

        # A catalog source is held too, and gets its visualizations once
        # confirmed; Cancel removes it.
        count = len(sinks())
        selection = list(manager.model.active_node)
        constant = data_model.get_instance(
            manager.add_source("ConstantDataset", pending=True)
        )
        assert manager.is_pending(constant._id)
        assert len(sinks()) == count
        manager.execute()
        await wait_idle(manager)
        assert constant.node.state.value == "New"
        dialog.open(constant._id)
        dialog.cancel()
        assert constant.node not in manager.pipeline.nodes
        assert manager.model.active_node == selection

        constant = data_model.get_instance(
            manager.add_source("ConstantDataset", pending=True)
        )
        dialog.open(constant._id)
        dialog.ok()
        await wait_idle(manager)
        assert constant.state == "Current"
        added = sinks()[count:]
        assert len(added) == 2
        assert all(s.source_port is constant.outputs[0] for s in added)
    finally:
        manager.shutdown()
        await server.stop()
        serve.cancel()


async def run_execution_session(volume_file, settings_file, folder, external_runs):
    from tomviz_web.app.core import Tomviz

    app = Tomviz(server="execution-session")
    server = app.server
    serve = asyncio.create_task(
        server.start(exec_mode="coroutine", port=0, open_browser=False, timeout=0)
    )
    await asyncio.sleep(0.5)
    manager = app.ctx.pipeline
    dialog = app.ctx.transform_editor
    editor = dialog.editor
    picker = dialog.env_picker
    env_root = os.path.normpath(sys.prefix)

    async def idle():
        await wait_for(lambda: not manager.pipeline.is_executing())
        await asyncio.sleep(0.3)

    try:
        manager.load_file(volume_file)
        await idle()
        scale = data_model.get_instance(manager.add_transform("Scale"))
        await idle()

        # A node runs internally until told otherwise: nothing to check.
        dialog.open(scale._id)
        assert (editor.executor, editor.env_path) == ("", "")
        assert scale.executor_type == ""
        await asyncio.sleep(0.6)
        assert editor.env_status == ""

        # The environment is checked as it is typed...
        editor.executor = "external"
        editor.env_path = str(folder)
        assert await wait_for(lambda: editor.env_status == "problem")
        assert "not a Python environment" in editor.env_message

        # ...or picked: the folder browser lists folders only, and Select
        # takes the highlighted one, or the current one.
        picker.open(folder)
        assert server.state.tomviz_env_loader
        assert server.state.tomviz_env_path == str(folder.resolve())
        listing = server.state.tomviz_env_listing
        assert [e["name"] for e in listing] == ["sub"]
        picker.select_entry(listing[0])
        picker.confirm(listing[0])
        assert not server.state.tomviz_env_loader
        assert editor.env_path == str(folder.resolve() / "sub")
        env_bin = Path(sys.prefix) / "bin"
        picker.open(env_bin)
        picker.confirm(None)
        assert editor.env_path == str(env_bin.resolve())

        # A pick of <env>/bin is shown as the environment's root.
        editor.env_path = str(env_bin)
        assert await wait_for(lambda: editor.env_status == "ok")
        assert editor.env_path == env_root
        assert "compatible" in editor.env_message
        assert not scale.node.node_executor

        # OK moves the node there, re-runs it in a subprocess, and remembers
        # the environment for the transform.
        dialog.ok()
        assert isinstance(scale.node.node_executor, ExternalNodeExecutor)
        assert scale.node.node_executor.env_path == env_root
        assert (scale.executor_type, scale.executor_env_path) == ("external", env_root)
        assert editor.message_type == "success"
        assert server.state.external_env_paths == {"Scale": env_root}
        await idle()
        assert external_runs == [(scale.node.id, True)]
        assert scale.state == "Current"
        np.testing.assert_allclose(scalars(scale), ramp() * 2.0)
        server.state.flush()
        saved = json.loads(settings_file.read_text())
        assert saved["external_env_paths"] == {"Scale": env_root}

        # A new node of the same transform starts with that environment,
        # still running internally.
        other = data_model.get_instance(manager.add_transform("Scale", pending=True))
        dialog.open(other._id)
        assert (editor.executor, editor.env_path) == ("", env_root)
        dialog.cancel()

        # Back to internal: the node re-runs in the application.
        dialog.open(scale._id)
        assert (editor.executor, editor.env_path) == ("external", env_root)
        editor.executor = ""
        dialog.ok()
        assert scale.node.node_executor is None
        assert scale.executor_type == ""
        await idle()
        assert len(external_runs) == 1
        assert scale.state == "Current"
        np.testing.assert_allclose(scalars(scale), ramp() * 2.0)

        # An externalOnly transform cannot run internally, and says what
        # is missing without an environment.
        only = data_model.get_instance(
            manager.add_transform("ExternalScale", pending=True)
        )
        dialog.open(only._id)
        assert (editor.executor, editor.env_path) == ("external", "")
        editor.executor = ""
        assert dialog.apply()
        assert editor.executor == "external"
        assert isinstance(only.node.node_executor, ExternalNodeExecutor)
        assert editor.message_type == "warning"
        assert "Python environment" in editor.message
        await idle()
    finally:
        manager.shutdown()
        await server.stop()
        serve.cancel()


def test_new_nodes_wait_for_the_editor(tmp_path, monkeypatch):
    kernels = tmp_path / "kernels"
    kernels.mkdir()
    (kernels / "Scale.json").write_text(json.dumps(SCALE_DEFINITION))
    (kernels / "Scale.py").write_text(SCALE_SCRIPT)

    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps({"directories": [str(kernels)], "modules": [], "favorites": []})
    )
    monkeypatch.setenv(
        "TRAME_ARGS",
        f"--catalog {catalog} --settings {tmp_path / 'settings.json'} --read-only",
    )
    volume = tmp_path / "volume.emd"
    write_emd(Dataset({"scalars": ramp()}), volume)
    other = tmp_path / "other.emd"
    write_emd(Dataset({"other": ramp()}), other)
    asyncio.run(run_pending_session(volume, other))


def test_editing_a_catalog_node(tmp_path, monkeypatch):
    kernels = tmp_path / "kernels"
    kernels.mkdir()
    (kernels / "Scale.json").write_text(json.dumps(SCALE_DEFINITION))
    (kernels / "Scale.py").write_text(SCALE_SCRIPT)

    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps({"directories": [str(kernels)], "modules": [], "favorites": []})
    )
    # Under pytest, trame only reads its arguments from TRAME_ARGS.
    monkeypatch.setenv(
        "TRAME_ARGS",
        f"--catalog {catalog} --settings {tmp_path / 'settings.json'} --read-only",
    )
    volume = tmp_path / "volume.emd"
    write_emd(Dataset({"scalars": ramp()}), volume)
    asyncio.run(run_session(volume))


@pytest.mark.skipif(os.name == "nt", reason="external execution is POSIX-only here")
def test_choosing_where_a_node_runs(tmp_path, monkeypatch):
    kernels = tmp_path / "kernels"
    kernels.mkdir()
    (kernels / "Scale.json").write_text(json.dumps(SCALE_DEFINITION))
    (kernels / "Scale.py").write_text(SCALE_SCRIPT)
    external_only = {
        **SCALE_DEFINITION,
        "name": "ExternalScale",
        "label": "External Scale",
        "externalOnly": True,
    }
    (kernels / "ExternalScale.json").write_text(json.dumps(external_only))
    (kernels / "ExternalScale.py").write_text(SCALE_SCRIPT)

    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps({"directories": [str(kernels)], "modules": [], "favorites": []})
    )
    settings = tmp_path / "settings.json"
    monkeypatch.setenv("TRAME_ARGS", f"--catalog {catalog} --settings {settings}")
    volume = tmp_path / "volume.emd"
    write_emd(Dataset({"scalars": ramp()}), volume)
    folder = tmp_path / "browse"
    (folder / "sub").mkdir(parents=True)
    (folder / "file.txt").write_text("not listed")

    external_runs = []
    execute = ExternalNodeExecutor.execute

    def record(self, node):
        ok = execute(self, node)
        external_runs.append((node.id, ok))
        return ok

    monkeypatch.setattr(ExternalNodeExecutor, "execute", record)
    asyncio.run(run_execution_session(volume, settings, folder, external_runs))
