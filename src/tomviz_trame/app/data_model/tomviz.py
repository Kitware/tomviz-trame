from enum import StrEnum
from typing import Any

from trame.app.dataclass import ServerOnly, StateDataModel, Sync, watch


class DataType(StrEnum):
    TABLE = "table"
    MOLECULE = "molecule"
    # ---
    TILT_SERIES = "volume-tilt"  # volume + tilt angle
    VOLUME = "volume"  # volume (only)
    IMAGE_DATA = "image-data"  # baseclass ~ volume
    LABEL_MAP = "label-map"  # volume (with colormap)

    def is_compatible(self, other): ...


class NodeStatus(StrEnum):
    NEW = "new"
    STALE = "stale"
    CURRENT = "current"


class ExecutionState(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PersistenceMode(StrEnum):
    TRANSIENT = "transient"
    PERSISTENT_MEMORY = "persistence-memory"
    PERSISTENT_FILE = "persistence-file"


class InputPort(StateDataModel):
    name = Sync(str)
    type = Sync(DataType)
    link = Sync("Link", has_dataclass=True)


class OutputPort(StateDataModel):
    name = Sync(str)
    type = Sync(DataType)
    links = Sync(list["Link"], list, has_dataclass=True)
    persistence_mode = Sync(PersistenceMode, PersistenceMode.TRANSIENT)
    stale = Sync(bool)


class Link(StateDataModel):
    input_port = Sync(InputPort | None, has_dataclass=True)
    output_port = Sync(OutputPort | None, has_dataclass=True)


class Node(StateDataModel):
    internal = ServerOnly(Any)
    label = Sync(str)
    status = Sync(NodeStatus)
    execution = Sync(ExecutionState)
    inputs = Sync(dict[str, InputPort], dict, has_dataclass=True)
    outputs = Sync(dict[str, OutputPort], dict, has_dataclass=True)

    def add_input(self, name: str, type: DataType):
        self.inputs[name] = InputPort(self.server, name=name, type=type)
        self.dirty("inputs")

    def add_output(self, name: str, type: DataType):
        self.outputs[name] = OutputPort(self.server, name=name, type=type)
        self.dirty("outputs")

    @watch("status")
    def _on_status(self, status):
        # propagate downstream stale
        ...


class View(StateDataModel):
    color = Sync(str)
    interaction = Sync(str, "3D")
    menu_expanded = Sync(bool, False)
    orientation_axes = Sync(bool, True)
    center_axes = Sync(bool, False)
    vtk_impl = ServerOnly(Any)
    ui_widget = ServerOnly(Any)


class RepresentationNode(Node):
    view = Sync(View, has_dataclass=True)
    visible = Sync(bool)
    properties = Sync(StateDataModel, has_dataclass=True)
