"""Build source nodes from catalog entries.

A catalog source is a schema-v2 kernel whose description declares no
``inputs``: the script defines a ``SourceNode`` (``SourceKernel``) subclass,
and the library's ``PythonNode`` hosts it as a ``PythonSource``. Like a file
reader, it starts a pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tomviz_pipeline import PythonNode, SourceNode


def build_source_node(
    description: dict[str, Any],
    script_path: str | Path,
    parameters: dict[str, Any] | None = None,
) -> SourceNode:
    """Create the source node for a catalog entry. ``parameters`` override
    the description's defaults."""
    node = PythonNode(description, kernel=Path(script_path))

    if parameters:
        # Write into the store directly: the node is not in a graph yet, so
        # there is nothing to mark stale or re-execute.
        node._parameter_store().update(parameters)

    if not node.label:
        node.label = description.get("label") or description.get("name", "")
    return node
