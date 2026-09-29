import json

import tomviz_kernels
from trame.app import get_server

from tomviz_web.app import data_model
from tomviz_web.app.catalog import Catalog, _drop_retired, _prune_stale


def test_prune_stale_drops_what_no_longer_resolves(tmp_path):
    directories, modules = _prune_stale(
        [str(tmp_path), str(tmp_path / "gone")],
        ["tomviz_kernels", "tomviz_web.operators"],
    )
    assert directories == [str(tmp_path)]
    assert modules == ["tomviz_kernels"]


def test_retired_defaults_are_dropped_but_user_entries_kept(tmp_path):
    """A config written by an older app lists the defaults of its day; those
    go, whatever the user added stays (and warns as usual if broken)."""
    directories, modules = _drop_retired(
        [str(tmp_path / "mine"), str(_home() / ".tomviz" / "operators")],
        [
            "tomviz_web.builtin",
            "tomviz.operators.builtin",
            "tomviz_web.builtin_kernels",
            "mylab.kernels",
        ],
    )
    assert directories == [str(tmp_path / "mine")]
    assert modules == ["mylab.kernels"]


def test_builtin_entries_come_from_tomviz_kernels(tmp_path):
    catalog = _catalog("catalog-builtin", tmp_path)

    names = {
        json.loads(path.read_text())["name"]
        for path in tomviz_kernels.directory().glob("*.json")
    }
    assert set(catalog.entries) == names

    # Sources are registered but not offered: the app cannot add one yet.
    sources = {name for name, entry in catalog.entries.items() if entry.is_source}
    assert "ConstantDataset" in sources
    offered = set(_item_names(catalog.root))
    assert offered == names - sources
    assert "GaussianFilter" in offered


def test_nameless_entries_are_named_after_their_script(tmp_path):
    folder = tmp_path / "kernels"
    folder.mkdir()
    for stem in ("First", "Second"):
        (folder / f"{stem}.json").write_text(json.dumps({"parameters": []}))
        (folder / f"{stem}.py").write_text("def transform(dataset):\n    pass\n")

    catalog = _catalog("catalog-nameless", tmp_path, directories=[str(folder)])

    for stem in ("First", "Second"):
        entry = catalog.entries[stem]
        assert entry.label == stem
        assert entry.json["name"] == stem


def _catalog(server_name, tmp_path, directories=()):
    config = tmp_path / "catalog.json"
    config.write_text(
        json.dumps({"directories": list(directories), "modules": [], "favorites": []})
    )
    server = get_server(server_name, client_type="vue3")
    return Catalog(server, config_file=config, read_only=True)


def _item_names(folder):
    for child in folder.children:
        if isinstance(child, data_model.CatalogFolder):
            yield from _item_names(child)
        else:
            yield child.name


def _home():
    from pathlib import Path

    return Path.home()
