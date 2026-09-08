"""Mirrors of tomviz_pipeline graph nodes for the reactive UI.

One model instance exists per graph node the UI shows, and the class
hierarchy follows the library's: ``NodeModel`` mirrors ``Node``,
``SourceNodeModel`` mirrors ``SourceNode``, ``TransformNodeModel`` mirrors
``TransformNode``, and ``SinkNodeModel`` (in ``sinks.py``) mirrors
``SinkNode``. ``DataNodeModel`` is the app's own intermediate base for nodes
with output ports (sources and transforms); what the UI shows about the
data itself lives on their ``OutputPortModel``s (``port.py``)."""

from __future__ import annotations

from tomviz_pipeline import Node, OutputPort
from trame.app.dataclass import ServerOnly, StateDataModel, Sync


class NodeModel(StateDataModel):
    """Mirror of ``tomviz_pipeline.Node``. ``node`` is the graph object; the
    synced fields copy what the UI displays about it."""

    node = ServerOnly(Node | None)
    label = Sync(str, "")
    type_name = Sync(str, "")  # schema-v2 type string, e.g. "source.reader"


class DataNodeModel(NodeModel):
    """A node with output ports: sources and transforms.

    ``outputs`` mirrors ``node.output_ports()`` with one ``OutputPortModel``
    each (created by the manager). The first one is the primary output that
    sinks and downstream nodes read.
    """

    outputs = Sync(list, list, has_dataclass=True)  # [OutputPortModel]

    # UI state
    expand_pipeline = Sync(bool, True)
    expand_sinks = Sync(list[str], list)  # view ids whose sink list is expanded

    # Graph neighbours, as the drawer shows them: downstream data nodes form
    # the tree, sinks are grouped per view.
    downstream = Sync(list, list, has_dataclass=True)  # [DataNodeModel]
    sinks = Sync(dict[str, list[str]] | None, dict)  # {view_id: [sink model id]}

    @property
    def primary_output(self) -> OutputPort | None:
        """The library port sinks and downstream nodes read from."""
        if self.node is None:
            return None
        ports = self.node.output_ports()
        return ports[0] if ports else None

    @property
    def primary_output_model(self):
        """The ``OutputPortModel`` of the primary output."""
        return self.outputs[0] if self.outputs else None

    @property
    def color_opacity(self):
        """The shared color map of the primary output."""
        port = self.primary_output_model
        return None if port is None else port.color_opacity


class SourceNodeModel(DataNodeModel):
    """Mirror of a ``SourceNode``: a file reader today."""


class TransformNodeModel(DataNodeModel):
    """Mirror of a ``TransformNode``: a catalog transform applied to
    ``input``. ``entry_name`` is the catalog entry it was built from.

    ``parameters`` mirrors ``Node.parameters``: it is the dataclass
    ``parameters_gui`` generates from the entry's JSON (one synced field per
    parameter). ``bind_parameters`` copies the node's values into it and
    pushes edits back with ``set_parameters``, which re-executes the graph.
    """

    entry_name = Sync(str)
    icon = Sync(str, "mdi-plus")
    input = Sync(DataNodeModel, has_dataclass=True)
    parameters = Sync(StateDataModel, has_dataclass=True)

    def __init__(self, server, **kwargs):
        self._parameter_names: list[str] = []
        self._unwatch_parameters = None
        super().__init__(server, **kwargs)

    def bind_parameters(self):
        """Mirror ``node.parameters`` into ``parameters`` and watch the
        mirror so edits reach the node."""
        self.unbind_parameters()
        if self.node is None or self.parameters is None:
            return

        names = [n for n in self.node.parameters if hasattr(self.parameters, n)]
        for name in names:
            setattr(self.parameters, name, self.node.parameters[name])

        self._parameter_names = names
        if names:
            self._unwatch_parameters = self.parameters.watch(
                names, self._on_parameters_change
            )

    def unbind_parameters(self):
        if self._unwatch_parameters is not None:
            self._unwatch_parameters()
            self._unwatch_parameters = None
        self._parameter_names = []

    def _on_parameters_change(self, *values):
        if self.node is None:
            return
        # Watchers fire asynchronously, so the initial sync in
        # bind_parameters lands here too: only push real changes, or that
        # sync would mark the node stale and re-execute for nothing.
        changed = {
            name: value
            for name, value in zip(self._parameter_names, values, strict=True)
            if self.node.parameter(name) != value
        }
        if changed:
            self.node.set_parameters(**changed)
