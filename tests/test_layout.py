"""The desktop's view layout tree turned into a dockview layout, and back."""

import pytest

from tomviz_web.app.pipeline.layout import (
    HORIZONTAL,
    LAYOUT_SERVERS,
    VERTICAL,
    dockview_layout,
    layout_entry,
    layout_view_ids,
)


def cell(view_id):
    return {"direction": 0, "fraction": 0.5, "viewId": view_id}


def split(direction, fraction):
    return {"direction": direction, "fraction": fraction, "viewId": 0}


def panels(*view_ids):
    return {v: {"id": f"panel{v}", "title": "3D View"} for v in view_ids}


def leaves(node):
    if node["type"] == "leaf":
        return [(node["data"]["views"][0], node.get("size"))]
    return [leaf for child in node["data"] for leaf in leaves(child)]


def test_a_single_view_fills_the_grid():
    layout = dockview_layout({"items": [[cell(7)]]}, panels(7), active_view_id=7)
    grid = layout["grid"]
    assert grid["orientation"] == "HORIZONTAL"
    assert grid["root"]["type"] == "branch"
    assert leaves(grid["root"]) == [("panel7", 1000.0)]
    assert layout["panels"] == {"panel7": {"id": "panel7", "title": "3D View"}}
    assert layout["activeGroup"] == "group-panel7"


def test_a_left_right_split_keeps_its_fraction():
    entry = {"items": [[split(HORIZONTAL, 0.3), cell(1), cell(2)]]}
    layout = dockview_layout(entry, panels(1, 2))
    grid = layout["grid"]
    assert grid["orientation"] == "HORIZONTAL"
    assert leaves(grid["root"]) == [("panel1", 300.0), ("panel2", 700.0)]
    assert "activeGroup" not in layout


def test_nested_splits_alternate_and_same_direction_ones_flatten():
    # Top/bottom, the bottom half split left/right, the right quarter split
    # top/bottom again: dockview nests HORIZONTAL inside VERTICAL, and the
    # innermost VERTICAL split becomes a branch of its own inside that.
    entry = {
        "items": [
            [
                split(VERTICAL, 0.5),
                cell(1),
                split(HORIZONTAL, 0.5),
                None,
                None,
                cell(2),
                split(VERTICAL, 0.25),
                None,
                None,
                None,
                None,
                None,
                None,
                cell(3),
                cell(4),
            ]
        ]
    }
    # Empty slots are padding in the flat tree.
    entry["items"][0] = [item or cell(0) for item in entry["items"][0]]
    layout = dockview_layout(entry, panels(1, 2, 3, 4))
    root = layout["grid"]["root"]
    assert layout["grid"]["orientation"] == "VERTICAL"
    top, bottom = root["data"]
    assert (top["type"], top["size"]) == ("leaf", 500.0)
    assert (bottom["type"], bottom["size"]) == ("branch", 500.0)
    left, right = bottom["data"]
    assert (left["data"]["views"], left["size"]) == (["panel2"], 500.0)
    assert (right["type"], right["size"]) == ("branch", 500.0)
    assert leaves(right) == [("panel3", 125.0), ("panel4", 375.0)]

    # The same direction twice in a row is one branch with three children.
    entry = {
        "items": [
            [
                split(VERTICAL, 0.5),
                cell(1),
                split(VERTICAL, 0.5),
                cell(0),
                cell(0),
                cell(2),
                cell(3),
            ]
        ]
    }
    layout = dockview_layout(entry, panels(1, 2, 3))
    assert layout["grid"]["orientation"] == "VERTICAL"
    assert leaves(layout["grid"]["root"]) == [
        ("panel1", 500.0),
        ("panel2", 250.0),
        ("panel3", 250.0),
    ]


def test_empty_cells_collapse():
    entry = {"items": [[split(HORIZONTAL, 0.5), cell(0), cell(1)]]}
    layout = dockview_layout(entry, panels(1))
    assert leaves(layout["grid"]["root"]) == [("panel1", 1000.0)]


def test_layouts_that_do_not_match_the_views_are_refused():
    entry = {"items": [[split(HORIZONTAL, 0.5), cell(1), cell(2)]]}
    assert dockview_layout(entry, panels(1)) is None  # a cell without a view
    assert dockview_layout(entry, panels(1, 2, 3)) is None  # a view without a cell
    assert dockview_layout({"items": [[]]}, panels(1)) is None
    assert layout_view_ids(entry) == [1, 2]


# ---- saving ------------------------------------------------------------------


def view_ids(*ids):
    """panel id -> saved view id, as the manager builds it."""
    return {f"panel{v}": v for v in ids}


def round_trip(entry, *ids):
    """The desktop entry through dockview and back."""
    return layout_entry(dockview_layout(entry, panels(*ids)), view_ids(*ids), 99)


def test_a_saved_layout_is_the_desktop_one():
    entry = {"items": [[split(HORIZONTAL, 0.4), cell(1), cell(2)]]}
    saved = round_trip(entry, 1, 2)
    assert saved["items"] == entry["items"]
    assert (saved["id"], saved["xmlGroup"], saved["xmlName"]) == (
        99,
        "misc",
        "ViewLayout",
    )
    assert saved["servers"] == LAYOUT_SERVERS
    assert round_trip({"items": [[cell(7)]]}, 7)["items"] == [[cell(7)]]


def test_nested_layouts_survive_a_round_trip():
    entry = {
        "items": [
            [
                split(VERTICAL, 0.5),
                cell(1),
                split(HORIZONTAL, 0.5),
                None,
                None,
                cell(2),
                split(VERTICAL, 0.5),
                None,
                None,
                None,
                None,
                None,
                None,
                cell(3),
                cell(4),
            ]
        ]
    }
    first = dockview_layout(entry, panels(1, 2, 3, 4))
    saved = layout_entry(first, view_ids(1, 2, 3, 4), 99)
    again = dockview_layout(saved, panels(1, 2, 3, 4))
    assert again["grid"] == first["grid"]


def test_branches_of_many_views_split_in_halves():
    # Four views side by side, 10/20/30/40: two levels, not a chain of three
    layout = {
        "grid": {
            "orientation": "HORIZONTAL",
            "root": {
                "type": "branch",
                "data": [
                    {"type": "leaf", "data": {"views": [f"panel{v}"]}, "size": s}
                    for v, s in ((1, 10), (2, 20), (3, 30), (4, 40))
                ],
            },
        }
    }
    items = layout_entry(layout, view_ids(1, 2, 3, 4), 99)["items"][0]
    assert items == [
        split(HORIZONTAL, 0.3),
        split(HORIZONTAL, 1 / 3),
        split(HORIZONTAL, 3 / 7),
        cell(1),
        cell(2),
        cell(3),
        cell(4),
    ]
    again = dockview_layout({"items": [items]}, panels(1, 2, 3, 4))
    names, sizes = zip(*leaves(again["grid"]["root"]), strict=True)
    assert names == ("panel1", "panel2", "panel3", "panel4")
    assert sizes == pytest.approx((100.0, 200.0, 300.0, 400.0))


def test_tabs_share_their_cell():
    # Two tabs in the right group of a left/right split: split top/bottom
    layout = {
        "grid": {
            "orientation": "HORIZONTAL",
            "root": {
                "type": "branch",
                "data": [
                    {"type": "leaf", "data": {"views": ["panel1"]}, "size": 1},
                    {
                        "type": "leaf",
                        "data": {"views": ["panel2", "panel3"]},
                        "size": 1,
                    },
                ],
            },
        }
    }
    items = layout_entry(layout, view_ids(1, 2, 3), 99)["items"][0]
    assert items[:3] == [split(HORIZONTAL, 0.5), cell(1), split(VERTICAL, 0.5)]
    assert items[5:] == [cell(2), cell(3)]


def test_views_the_layout_misses_go_on_the_right():
    entry = {"items": [[split(VERTICAL, 0.5), cell(1), cell(2)]]}
    layout = dockview_layout(entry, panels(1, 2))
    # A third view the dock has not reported, and a stale panel
    layout["grid"]["root"]["data"].append(
        {"type": "leaf", "data": {"views": ["gone"]}, "size": 500}
    )
    items = layout_entry(layout, view_ids(1, 2, 3), 99)["items"][0]
    assert items[:3] == [split(HORIZONTAL, 2 / 3), split(VERTICAL, 0.5), cell(3)]
    assert items[3:] == [cell(1), cell(2)]

    # Nothing reported yet: side by side
    items = layout_entry(None, view_ids(1, 2), 99)["items"][0]
    assert items == [split(HORIZONTAL, 0.5), cell(1), cell(2)]
    assert layout_entry(None, {}, 99) is None
