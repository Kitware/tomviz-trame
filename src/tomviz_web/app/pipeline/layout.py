"""The desktop's view layout as a dockview layout.

On the desktop, a state file's ``layouts`` entries serialize ParaView's
``vtkSMViewLayoutProxy``: a binary tree stored as a flat list where item
``i`` has its children at ``2i + 1`` (left or top) and ``2i + 2``. Each item
has a ``direction`` (0: a cell holding ``viewId``, or empty when 0; 1: split
top/bottom; 2: split left/right), and a split's ``fraction`` is the first
child's share.

On the web, dockview describes the same thing as a tree of branches whose
orientation alternates with depth (``grid.orientation`` at the root), with
leaves holding panel ids and sizes in whatever units the grid is given: it
re-lays the grid out proportionally to its container, so sizes only need to
be relative. ``dockview_layout`` converts one into the other, flattening
nested splits of the same direction into one branch since dockview cannot
nest those.

``layout_entry`` goes back, for saving: a branch of n children becomes a
balanced tree of two-way splits, and a group of tabs, which ParaView cannot
show, is split evenly across the cell it occupies."""

from __future__ import annotations

VERTICAL = 1  # split top/bottom (a horizontal line)
HORIZONTAL = 2  # split left/right (a vertical line)
GRID_SIZE = 1000.0  # relative units, see the module docstring

ORIENTATIONS = {VERTICAL: "VERTICAL", HORIZONTAL: "HORIZONTAL"}
DIRECTIONS = {name: direction for direction, name in ORIENTATIONS.items()}

# ParaView's server flags for the proxies a state file recreates
VIEW_SERVERS = 21
LAYOUT_SERVERS = 20


def layout_items(entry: dict) -> list[dict]:
    """The tree of a state-file ``layouts`` entry: its first non-empty
    ``Layout`` element (the desktop writes one list per element)."""
    for items in entry.get("items") or []:
        if items:
            return list(items)
    return []


def layout_view_ids(entry: dict) -> list[int]:
    """The saved view ids the layout's cells hold, in tree order."""
    return [
        int(item.get("viewId", 0))
        for item in layout_items(entry)
        if not item.get("direction") and item.get("viewId")
    ]


def dockview_layout(
    entry: dict,
    panels: dict[int, dict],
    active_view_id: int | None = None,
    size: float = GRID_SIZE,
) -> dict | None:
    """The dockview layout arranging ``panels`` (saved view id -> the
    panel's dockview entry: ``id``, ``contentComponent``, ``title``, ...)
    like the state file's layout ``entry``. None when a cell refers to a
    view without a panel or a panel has no cell, in which case the caller
    keeps whatever arrangement it has."""
    items = layout_items(entry)
    if not items:
        return None
    placed: list[int] = []

    def group_id(view_id: int) -> str:
        return f"group-{panels[view_id]['id']}"

    def build(index: int, width: float, height: float):
        """A node in relative units, plus its own orientation for a branch,
        or None for an empty cell."""
        if index >= len(items):
            return None
        item = items[index]
        direction = int(item.get("direction") or 0)
        if direction not in ORIENTATIONS:
            view_id = int(item.get("viewId") or 0)
            if not view_id:
                return None
            if view_id not in panels:
                raise LookupError(view_id)
            placed.append(view_id)
            panel_id = panels[view_id]["id"]
            data = {
                "views": [panel_id],
                "activeView": panel_id,
                "id": group_id(view_id),
            }
            return {"type": "leaf", "data": data}

        orientation = ORIENTATIONS[direction]
        fraction = min(max(float(item.get("fraction", 0.5)), 0.0), 1.0)
        if direction == HORIZONTAL:
            extents = [(width * fraction, height), (width * (1 - fraction), height)]
        else:
            extents = [(width, height * fraction), (width, height * (1 - fraction))]
        children = []
        for offset, (w, h) in enumerate(extents, start=1):
            child = build(2 * index + offset, w, h)
            if child is None:
                continue
            along = w if direction == HORIZONTAL else h
            if child["type"] == "branch" and child["orientation"] == orientation:
                # dockview alternates orientations: a split in the same
                # direction becomes more children of this branch.
                children.extend(child["data"])
            else:
                child["size"] = along
                children.append(child)
        if not children:
            return None
        if len(children) == 1:
            child = children[0]
            child.pop("size", None)
            return child
        return {"type": "branch", "data": children, "orientation": orientation}

    try:
        root = build(0, size, size)
    except LookupError:
        return None
    if root is None or sorted(placed) != sorted(panels):
        return None

    if root["type"] == "leaf":
        root["size"] = size
        root = {"type": "branch", "data": [root], "orientation": "HORIZONTAL"}
    orientation = root.pop("orientation")
    root["size"] = size
    _strip_orientation(root)

    layout = {
        "grid": {
            "root": root,
            "width": size,
            "height": size,
            "orientation": orientation,
        },
        "panels": {panel["id"]: panel for panel in panels.values()},
    }
    if active_view_id in panels:
        layout["activeGroup"] = group_id(active_view_id)
    return layout


def _strip_orientation(node: dict):
    node.pop("orientation", None)
    if node["type"] == "branch":
        for child in node["data"]:
            _strip_orientation(child)


# ---- saving ------------------------------------------------------------------


def layout_entry(
    layout: dict | None, view_ids: dict[str, int], layout_id: int
) -> dict | None:
    """The state-file ``layouts`` entry arranging the views like the
    dockview ``layout`` (what dockview's ``layout_changed`` reports; None
    when none was), or None without views. ``view_ids`` maps each panel id
    to its saved view id. Views the layout's grid does not hold (none was
    reported yet, a floating group) go side by side on the right, one share
    each."""
    if not view_ids:
        return None
    placed: list[int] = []
    grid = (layout or {}).get("grid") or {}
    root = None
    if grid.get("root"):
        root = _tree(
            grid["root"], grid.get("orientation", "HORIZONTAL"), view_ids, placed
        )
    shares = [(root, float(len(placed)))] if root is not None else []
    shares += [(("cell", v), 1.0) for v in view_ids.values() if v not in placed]
    return {
        "id": layout_id,
        "xmlGroup": "misc",
        "xmlName": "ViewLayout",
        "servers": LAYOUT_SERVERS,
        "items": [_items(_balanced(shares, HORIZONTAL))],
    }


def _flip(orientation: str) -> str:
    return "VERTICAL" if orientation == "HORIZONTAL" else "HORIZONTAL"


def _tree(node: dict, orientation: str, view_ids: dict[str, int], placed: list):
    """A dockview node as a split tree: ``("cell", view_id)`` or ``("split",
    direction, fraction, first, second)``; None when it holds no view.
    ``orientation`` is the node's own, should it be a branch."""
    if node.get("type") == "leaf":
        panel_ids = (node.get("data") or {}).get("views") or []
        cells = [view_ids[p] for p in panel_ids if p in view_ids]
        placed.extend(cells)
        if not cells:
            return None
        # Tabs: the views share the group's cell.
        return _balanced([(("cell", v), 1.0) for v in cells], DIRECTIONS[orientation])

    children = []
    for child in node.get("data") or []:
        tree = _tree(child, _flip(orientation), view_ids, placed)
        if tree is not None:
            children.append((tree, float(child.get("size") or 0.0)))
    if not children:
        return None
    return _balanced(children, DIRECTIONS[orientation])


def _balanced(shares: list[tuple], direction: int):
    """Split ``(tree, share)`` pairs in ``direction``, halving the list at
    each level so the tree, and ParaView's flat list of it, stay shallow."""
    if len(shares) == 1:
        return shares[0][0]
    middle = len(shares) // 2
    first, second = shares[:middle], shares[middle:]
    total = sum(share for _, share in shares)
    if total > 0:
        fraction = sum(share for _, share in first) / total
    else:
        fraction = len(first) / len(shares)
    return (
        "split",
        direction,
        fraction,
        _balanced(first, direction),
        _balanced(second, direction),
    )


def _items(tree) -> list[dict]:
    """A split tree as ParaView's flat list: item ``i``'s children at
    ``2i + 1`` and ``2i + 2``, the unused slots empty cells."""
    cells: dict[int, dict] = {}

    def place(node, index: int):
        if node[0] == "cell":
            cells[index] = {"direction": 0, "fraction": 0.5, "viewId": node[1]}
            return
        _, direction, fraction, first, second = node
        cells[index] = {"direction": direction, "fraction": fraction, "viewId": 0}
        place(first, 2 * index + 1)
        place(second, 2 * index + 2)

    place(tree, 0)
    empty = {"direction": 0, "fraction": 0.5, "viewId": 0}
    return [cells.get(i, dict(empty)) for i in range(max(cells) + 1)]
