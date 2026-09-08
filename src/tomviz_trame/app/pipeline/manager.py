from __future__ import annotations

import asyncio
import functools
from collections.abc import Callable
from pathlib import Path

from loguru import logger
from tomviz_pipeline import (
    AsyncioDispatcher,
    Node,
    OutputPort,
    Pipeline,
    ThreadedExecutor,
)
from trame.app import TrameComponent
from trame.decorators import change, trigger

from tomviz_trame.app import data_model
from tomviz_trame.app.parameters_gui import to_parameters_model
from tomviz_trame.app.pipeline.nodes import (
    INPUT_PORT,
    ReaderSourceNode,
    RepresentationSinkNode,
    build_transform_node,
    register_nodes,
)
from tomviz_trame.app.pipeline.representations import RepresentationType

# TEMPORARY: every loaded file gets this transform inserted between the
# reader and its sinks (its sigma is live in the transform panel). Remove
# once transforms are added through the UI.
TEMP_TRANSFORM = "GaussianFilter"
TEMP_TRANSFORM_PARAMETERS = {"sigma": 0.0}


class PipelineManager(TrameComponent):
    """Owns the tomviz_pipeline graph and mirrors it into the trame data model.

    Graph side: ``pipeline`` is a ``tomviz_pipeline.Pipeline`` run by a
    ``ThreadedExecutor``. File sources are ``ReaderSourceNode`` roots,
    catalog transforms are chained after them, and visualizations are
    ``RepresentationSinkNode`` leaves. Whatever the worker thread reports
    comes back through an ``AsyncioDispatcher``, so every handler here runs
    on trame's event loop, the only thread allowed to touch trame state and
    VTK rendering. The one exception is ``_describe_outputs``, connected
    directly on purpose: it runs on the worker right after a data node, does
    the numpy statistics there, and only posts the result to the loop.

    Chain rule (desktop tomviz parity): transforms are appended at the end of
    a data node's chain and sinks always display the end of the chain, so
    ``add_transform`` re-links the existing sinks to the new node.

    UI side: ``model`` (a ``PipelineModel``) holds one ``NodeModel`` per graph
    node; ``node_models`` indexes them by node id. Data nodes carry one
    ``OutputPortModel`` per output port, each with its shared color map.
    """

    def __init__(self, server=None):
        super().__init__(server=server)
        register_nodes()

        self.pipeline = Pipeline()
        self.pipeline.auto_execute = True
        self.executor = ThreadedExecutor()
        self.pipeline.set_executor(self.executor)

        self._loop: asyncio.AbstractEventLoop | None = None
        self._dispatcher: AsyncioDispatcher | None = None

        self.node_models: dict[int, data_model.NodeModel] = {}  # node.id -> model
        self.views = {}  # view_id -> ui.RenderWindow
        self.pending_tasks = set()

        self.model = data_model.PipelineModel(self.server, pipeline=self.pipeline)
        self.state.property_templates = []
        self.state.active_view_id = None
        self.state.active_data_id = None
        self.state.active_port_id = None
        self.state.active_representation_id = None
        self.state.active_color_opacity_id = None
        self._ui_color_opacity_id: str | None = None

        self.model.watch(["active_node"], self._on_active_change)

        # Direct connection: runs on the executor's thread (see class doc).
        self.executor.node_execution_finished.connect(self._describe_outputs)

        self.ctrl.on_server_ready.add(self._on_server_ready)
        self.ctrl.on_server_exited.add(self.shutdown)

        if self.server.hot_reload:
            self.ctrl.on_server_reload.add(self.refresh_views_later)

    def __del__(self):
        self.model.clear_watchers()

    # -------------------------------------------------------------------------
    # Execution
    # -------------------------------------------------------------------------

    def _on_server_ready(self, **_):
        self._ensure_dispatcher()

    def _ensure_dispatcher(self):
        """Bind the graph's signals to the running event loop. Deferred until
        a loop exists because trame starts it after this object is built."""
        if self._dispatcher is not None:
            return

        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.debug("No running event loop yet; pipeline signals not bound")
            return

        self._dispatcher = AsyncioDispatcher(loop=self._loop)
        self.executor.node_execution_finished.connect(
            self._on_node_finished, self._dispatcher
        )
        self.pipeline.execution_started.connect(
            lambda _future: logger.debug("Pipeline execution started"),
            self._dispatcher,
        )
        self.pipeline.execution_finished.connect(
            self._on_execution_finished, self._dispatcher
        )

    def run_on_loop(self, callback: Callable[[], None]):
        """Run ``callback`` on the application's event loop from any thread.
        Without a loop (tests, blocking executors) it runs inline."""
        loop = self._loop
        if loop is None or not loop.is_running():
            callback()
        else:
            loop.call_soon_threadsafe(callback)

    def execute(self, target: Node | None = None):
        """Bring the graph (or just ``target``) up to date. Returns the
        library's ``ExecutionFuture``."""
        self._ensure_dispatcher()
        return self.pipeline.execute(target)

    def execute_when_idle(self):
        self._ensure_dispatcher()
        self.pipeline.execute_when_idle()

    def shutdown(self, **_):
        self.executor.cancel_and_wait(timeout=5)

    def _describe_outputs(self, node: Node, success: bool):
        """Worker thread, right after ``node`` ran and before the next node.
        Describes each output port (geometry plus statistics of the arrays
        some color map displays) and posts it to the loop, so the description
        is installed before the sinks' own updates arrive."""
        if not success:
            return
        model = self.node_models.get(node.id)
        if not isinstance(model, data_model.DataNodeModel):
            return

        for port_model in list(model.outputs):
            description = port_model.describe()
            if description is None:
                continue
            self.run_on_loop(
                functools.partial(port_model.apply_description, description)
            )

    def _on_node_finished(self, node: Node, success: bool):
        # Event loop, queued behind whatever the loop is doing: the node
        # itself finished on the worker some time ago.
        logger.debug("Node '{}' (id={}) finished, ok={}", node.label, node.id, success)

    def _on_execution_finished(self, future):
        logger.debug(
            "Pipeline execution finished, succeeded={} canceled={}",
            future.succeeded(),
            future.was_canceled(),
        )

    # -------------------------------------------------------------------------
    # Node bookkeeping
    # -------------------------------------------------------------------------

    def _track(self, model: data_model.NodeModel):
        """Register a model whose node is already in the graph and linked.
        Data nodes get one ``OutputPortModel`` per output port."""
        if isinstance(model, data_model.DataNodeModel) and not model.outputs:
            model.outputs = [
                self._create_port_model(model, port)
                for port in model.node.output_ports()
            ]
        self.node_models[model.node.id] = model
        self.model.add(model)

    def _untrack(self, model: data_model.NodeModel):
        self.node_models.pop(model.node.id, None)
        self.model.remove(model)

    def _create_port_model(
        self, model: data_model.DataNodeModel, port: OutputPort
    ) -> data_model.OutputPortModel:
        port_model = data_model.OutputPortModel(
            self.server,
            port=port,
            node=model,
            name=port.name,
            port_type=port.port_type,
        )
        # Only image data is colored through a lookup table.
        if (
            data_model.port_data_model_for(port.port_type)
            is data_model.ImagePortDataModel
        ):
            port_model.color_opacity = data_model.create_color_opacity(port_model)
        return port_model

    def _sink_models_of(
        self, data_node: data_model.DataNodeModel
    ) -> list[data_model.SinkNodeModel]:
        return [
            m
            for m in self.node_models.values()
            if isinstance(m, data_model.SinkNodeModel) and m.data_node is data_node
        ]

    @staticmethod
    def _chain_end(data_node: data_model.DataNodeModel) -> data_model.DataNodeModel:
        """The last data node of ``data_node``'s transform chain (itself when
        nothing is chained after it)."""
        while data_node.downstream:
            data_node = data_node.downstream[-1]
        return data_node

    # -------------------------------------------------------------------------
    # Sources
    # -------------------------------------------------------------------------

    def load_file(self, file_path: str | Path) -> str | None:
        file_path = Path(file_path).resolve()

        if not file_path.exists():
            return None

        node = ReaderSourceNode.for_file(file_path)
        self.pipeline.add_node(node)

        source = data_model.SourceNodeModel(
            self.server, node=node, label=node.label, type_name=node.type_name
        )
        self._track(source)

        # TEMPORARY: exercise re-execution with a real transform in the chain.
        self.add_transform(
            source._id,
            TEMP_TRANSFORM,
            parameters=TEMP_TRANSFORM_PARAMETERS,
            execute=False,
        )

        if self.state.active_view_id:
            self.add_default_sinks(source._id, self.state.active_view_id)

        # make new data node active by default
        self.model.active_node = [source._id]

        self.execute()

        return source._id

    # -------------------------------------------------------------------------
    # Views
    # -------------------------------------------------------------------------

    def add_view(self) -> str:
        # Imported here: `ui` imports this package at module level.
        from tomviz_trame.app import ui

        view = ui.RenderWindow(self.server)
        logger.debug("Add view {} vs {}", view.local_state._id, view.vtk_id)
        self.views[view.local_state._id] = view
        self.ctx.dock_view.add_panel(
            view.vtk_id,
            "3D View",
            view.tpl_name,
            tabComponent="tomviz-dockview-tab",
            params={
                "templateName": view.tpl_name,
                "viewState": view.local_state._id,
            },
        )
        return view.local_state._id

    @trigger("remove_view")
    def remove_view(self, view_id: str):
        logger.debug("remove view {}", view_id)
        view = self.views.get(view_id)
        if view is None:
            return

        for sink_model in [
            m
            for m in self.node_models.values()
            if isinstance(m, data_model.SinkNodeModel) and m.view._id == view_id
        ]:
            self.remove_sink(sink_model.node.id)

        view.vtk_view.clear()
        self.ctx.dock_view.remove_panel(view.vtk_id)
        self.state.active_view_id = None
        del self.views[view_id]

    def activate_panel(self, panel_id):
        logger.debug("activate_panel {}", panel_id)
        found = False
        for view_id, view in self.views.items():
            if view.vtk_id == panel_id:
                self.state.active_view_id = view_id
                found = True

        if not found:
            self.state.active_view_id = None

    def refresh_views_later(self, **_):
        task = asyncio.create_task(self._refresh_views())
        self.pending_tasks.add(task)
        task.add_done_callback(self.pending_tasks.discard)

    async def _refresh_views(self):
        await asyncio.sleep(0.1)
        self.refresh_views()

    def refresh_views(self, **_):
        """Register all views into dockview"""
        for view in self.views.values():
            self.ctx.dock_view.add_panel(
                view.vtk_id,
                "3D View",
                view.tpl_name,
                tabComponent="tomviz-dockview-tab",
                params={
                    "templateName": view.tpl_name,
                    "viewState": view.local_state._id,
                },
            )

    # -------------------------------------------------------------------------
    # Transforms
    # -------------------------------------------------------------------------

    def add_transform(
        self,
        data_id: str,
        entry_name: str,
        icon: str | None = None,
        meta: dict | None = None,
        parameters: dict | None = None,
        execute: bool = True,
        **_,
    ) -> str | None:
        """Append the catalog transform ``entry_name`` to the chain that
        starts at ``data_id``. The sinks that displayed the chain's previous
        end move to the new node. Returns the id of the new model."""
        entry = self.ctx.catalog.entries.get(entry_name)
        if entry is None:
            logger.error("Unknown catalog entry '{}'", entry_name)
            return None

        data_node: data_model.DataNodeModel = data_model.get_instance(data_id)
        parent = self._chain_end(data_node)
        output = parent.primary_output
        if output is None:
            logger.error("'{}' has no output to transform", parent.label)
            return None

        description = meta or entry.json
        node = build_transform_node(description, entry.file, parameters)
        self.pipeline.add_node(node)
        self.pipeline.create_link(output, node.input_port(INPUT_PORT))

        model = data_model.TransformNodeModel(
            self.server,
            node=node,
            label=node.label,
            type_name=node.type_name,
            entry_name=entry.name,
            icon=icon or entry.icon,
            input=parent,
            parameters=to_parameters_model(self.server, description),
        )
        model.bind_parameters()
        self._track(model)
        parent.downstream = [*parent.downstream, model]

        self._relink_sinks(parent, model)

        if execute:
            self.execute_when_idle()

        return model._id

    def _relink_sinks(
        self, old_end: data_model.DataNodeModel, new_end: data_model.DataNodeModel
    ):
        """Move every sink displaying ``old_end`` to ``new_end``'s primary
        output, graph links and models alike."""
        output = new_end.primary_output
        port_model = new_end.primary_output_model
        for sink_model in self._sink_models_of(old_end):
            self.pipeline.create_link(output, sink_model.node.input_port(INPUT_PORT))
            sink_model.set_source_port(port_model)

        if old_end.sinks:
            new_end.sinks = {**(new_end.sinks or {}), **old_end.sinks}
            old_end.sinks = {}
        if old_end.expand_sinks:
            new_end.expand_sinks = list(
                dict.fromkeys([*new_end.expand_sinks, *old_end.expand_sinks])
            )

    # -------------------------------------------------------------------------
    # Sinks
    # -------------------------------------------------------------------------

    def add_default_sinks(self, data_id: str, view_id: str):
        self.add_sink(data_id, view_id, RepresentationType.OUTLINE.name, execute=False)
        self.add_sink(data_id, view_id, RepresentationType.SLICE.name, execute=False)

    def add_sink(
        self, data_id: str, view_id: str, type: str, execute: bool = True
    ) -> str | None:
        """Add a sink of the given ``RepresentationType`` name showing the
        primary output at the end of ``data_id``'s chain in ``view_id``. With
        ``execute`` the graph runs right away (once the in-flight run, if any,
        ends) so the new sink gets data. Returns the id of the sink's model."""
        logger.debug("data_id: {}, view_id: {}, type: {}", data_id, view_id, type)
        data_node = self._chain_end(data_model.get_instance(data_id))
        view: data_model.ViewModel = data_model.get_instance(view_id)
        output = data_node.primary_output
        port_model = data_node.primary_output_model
        if output is None or port_model is None:
            logger.error("'{}' has no output to display", data_node.label)
            return None

        representation_type = RepresentationType[type]
        if not representation_type.accepts(output.port_type):
            logger.error(
                "A {} cannot display '{}' ({} data)",
                representation_type.label,
                data_node.label,
                output.port_type,
            )
            return None

        sink = RepresentationSinkNode(
            representation_type, self, port_model, view, self.run_on_loop
        )
        self.pipeline.add_node(sink)
        self.pipeline.create_link(output, sink.input_port(INPUT_PORT))
        self._track(sink.model)

        if view_id not in data_node.expand_sinks:
            data_node.expand_sinks = [*data_node.expand_sinks, view_id]

        sinks = {**(data_node.sinks or {})}
        sinks[view_id] = [*sinks.get(view_id, []), sink.model._id]
        data_node.sinks = sinks

        if execute:
            self.execute_when_idle()

        return sink.model._id

    def remove_sink(self, node_id: int):
        sink_model = self.node_models.get(node_id)
        if not isinstance(sink_model, data_model.SinkNodeModel):
            return
        sink: RepresentationSinkNode = sink_model.node

        self.pipeline.remove_node(sink)
        sink.detach()
        release = getattr(sink_model, "release_color_opacity", None)
        if release is not None:
            release()
        self._untrack(sink_model)

        data_node = sink_model.data_node
        view_id = sink_model.view._id
        sinks = {**(data_node.sinks or {})}
        remaining = [s for s in sinks.get(view_id, []) if s != sink_model._id]
        if remaining:
            sinks[view_id] = remaining
        else:
            sinks.pop(view_id, None)
        data_node.sinks = sinks

    # -------------------------------------------------------------------------
    # Selection
    # -------------------------------------------------------------------------

    def _on_active_change(self, active_node: list[str]):
        # Imported here: `ui` imports this package at module level.
        from tomviz_trame.app.ui.dynamic import DYNAMIC_TEMPLATES

        logger.debug("active_node: {}", active_node)
        with self.state as s:
            obj = data_model.get_instance(active_node[0]) if active_node else None
            if isinstance(obj, data_model.DataNodeModel):
                port = obj.primary_output_model
                color_opacity = port.color_opacity if port else None
                template = (
                    DYNAMIC_TEMPLATES.get("transform")
                    if isinstance(obj, data_model.TransformNodeModel)
                    else None
                )
                s.active_data_id = obj._id
                s.active_port_id = port._id if port else None
                s.active_representation_id = None
                s.active_color_opacity_id = color_opacity._id if color_opacity else ""
                s.property_templates = [template] if template else []
            elif isinstance(obj, data_model.SinkNodeModel):
                port = obj.source_port
                color_opacity = getattr(obj, "color_opacity", None)
                template = DYNAMIC_TEMPLATES.get(obj.representation_type)
                s.active_data_id = obj.data_node._id
                s.active_port_id = port._id
                s.active_representation_id = obj._id
                s.active_view_id = obj.view._id
                s.active_color_opacity_id = color_opacity._id if color_opacity else ""
                s.property_templates = [template] if template else []
            else:
                s.active_data_id = None
                s.active_port_id = None
                s.active_representation_id = None
                s.active_view_id = None
                s.property_templates = []
                s.active_color_opacity_id = ""

    @change("active_color_opacity_id")
    def _on_active_color_opacity_change(self, active_color_opacity_id, **_):
        """The color editor counts as a user of the map it shows, so a port
        nobody displays still gets statistics when selected. Tracked on the
        state key itself because sinks also update it when they rebind."""
        previous_id = self._ui_color_opacity_id
        if previous_id == active_color_opacity_id:
            return
        self._ui_color_opacity_id = active_color_opacity_id

        ui_user = data_model.ColorOpacityModel.UI_USER
        previous = data_model.get_instance(previous_id) if previous_id else None
        if isinstance(previous, data_model.ColorOpacityModel):
            previous.release(ui_user)
        current = (
            data_model.get_instance(active_color_opacity_id)
            if active_color_opacity_id
            else None
        )
        if isinstance(current, data_model.ColorOpacityModel):
            current.acquire(ui_user)
