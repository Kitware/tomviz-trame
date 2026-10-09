from pathlib import Path

from loguru import logger
from trame.widgets import html
from trame.widgets import vuetify3 as v3

from tomviz_web.app.pipeline.nodes import SUPPORTED_EXTENSIONS
from tomviz_web.app.pipeline.state import STATE_EXTENSIONS

# -----------------------------------------------------------------------------
# Utils
# -----------------------------------------------------------------------------

DIRECTORY = {"icon": "mdi-folder", "type": "directory"}
GROUP = {"icon": "mdi-file-document-multiple-outline", "type": "group"}
FILE = {"icon": "mdi-file-document-outline", "type": "file"}

HEADERS = [
    {"title": "Name", "align": "start", "key": "name", "sortable": False},
    {"title": "Size", "align": "end", "key": "size", "sortable": False},
    {"title": "Date", "align": "end", "key": "modified", "sortable": False},
]


def sort_by_name(e):
    return e.get("name")


def to_type(e):
    return e.get("type", "")


def to_suffix(e):
    return Path(e.get("name", "")).suffix


# -----------------------------------------------------------------------------


class FileBrowser:
    def __init__(self, home=None, current=None):
        self._enable_groups = True
        self._home_path = Path(home).resolve() if home else Path.home()
        self._current_path = Path(current).resolve() if current else self._home_path

    @property
    def enable_groups(self):
        return self._enable_groups

    @enable_groups.setter
    def enable_groups(self, v):
        self._enable_groups = v

    @property
    def current_path(self):
        return self._current_path

    @property
    def listing(self):
        directories = []
        files = []
        for f in self._current_path.iterdir():
            if f.name[0] == ".":
                continue
            try:
                stat = f.stat()
            except OSError:  # a broken symlink
                continue
            entry = {"name": f.name, "modified": stat.st_mtime}
            if f.is_dir():
                directories.append({**entry, **DIRECTORY})
            elif f.is_file():
                files.append({**entry, **FILE, "size": stat.st_size})

        # Sort content
        directories.sort(key=sort_by_name)
        files.sort(key=sort_by_name)

        return [{**e, "index": i} for i, e in enumerate([*directories, *files])]

    def open_entry(self, entry):
        entry_type = entry.get("type")
        if entry_type in ["directory", "file"]:
            self._current_path = self._current_path / entry.get("name")
            return entry_type, str(self._current_path)
        if entry_type == "group":
            files = entry.get("files", [])
            return entry, [str(self._current_path / f) for f in files]
        return None

    def goto(self, path):
        self._current_path = Path(path).resolve()

    def goto_home(self):
        self._current_path = self._home_path

    def goto_parent(self):
        self._current_path = self._current_path.parent

    def to_file(self, entry):
        return self._current_path / entry.get("name")

    def open_dataset(self, entry):
        return self._current_path / entry.get("name")

    def open_state(self, entry):
        return self._current_path / entry.get("name")


class FileLoader(v3.VDialog):
    """A dialog browsing the server's filesystem with a ``FileBrowser``.

    By default it is the toolbar's Open dialog: it loads a data file or a
    state file. ``on_select(path)`` replaces what is done with the chosen
    file, and ``extensions`` which files can be chosen. With ``directory``
    it picks a folder instead: only folders are listed, the current path is
    shown, and the confirm button takes the highlighted folder, or the
    current one when none is. With ``save`` it names a file to write: the
    folders and the files of the first extension family are listed, a name
    field and a format (one of ``extensions``, appended unless the name has
    one) give the target, clicking a file takes its name, and an existing
    target is announced (the confirm button replaces it).

    Each instance keeps its state under its own ``name`` prefix;
    ``{name}_loader`` shows it, and ``open(start)`` shows it at a folder.
    """

    def __init__(
        self,
        name="tomviz_file",
        title="Open Data File",
        confirm="Load",
        confirm_icon="mdi-file-upload-outline",
        extensions=None,
        directory=False,
        save=False,
        on_select=None,
        **_,
    ):
        self._name = name
        self._directory = directory
        self._save = save
        self._on_select = on_select or self._open_data
        super().__init__(v_model=(self._key("loader"), False))

        # What the reader node can open, plus state files
        self._file_ext = (
            tuple(extensions)
            if extensions is not None
            else (*SUPPORTED_EXTENSIONS, *STATE_EXTENSIONS)
        )

        # Initialize file browser (a folder pick starts at home)
        self._file_browser = FileBrowser(current=None if directory else Path.cwd())
        if save:
            self.state[self._key("filename")] = ""
            self.state[self._key("format")] = self._file_ext[0]
            self.state[self._key("exists")] = False
            self.state.change(self._key("filename"), self._key("format"))(
                self._update_target
            )

        # Fill content
        self._update_listing()
        self.selected_entry = None

        # Define UI
        # Sized like the node editor dialog.
        with (
            self,
            v3.VCard(rounded="lg", classes="mx-auto", max_width="1000px", width="80vw"),
        ):
            style_align_center = "d-flex align-center "
            with v3.VToolbar(density="compact", classes="bg-surface"):
                v3.VToolbarTitle(title, style="flex: none;")
                v3.VDivider(classes="mx-3", vertical=True)
                v3.VBtn(
                    icon="mdi-home",
                    classes="rounded",
                    variant="tonal",
                    density="comfortable",
                    click=self.goto_home,
                )
                v3.VBtn(
                    icon="mdi-folder-upload-outline",
                    classes="rounded mx-3",
                    variant="tonal",
                    density="comfortable",
                    click=self.goto_parent,
                )
                v3.VTextField(
                    v_model=(self._key("filter"), ""),
                    hide_details=True,
                    color="primary",
                    placeholder="filter",
                    density="compact",
                    variant="outlined",
                    classes="mx-2",
                    prepend_inner_icon="mdi-magnify",
                    clearable=True,
                )
            if directory:
                html.Div(
                    f"{{{{ {self._key('path')} }}}}",
                    classes="text-caption text-medium-emphasis px-4 py-1 text-truncate",
                )
            v3.VDivider()
            with v3.VDataTable(
                density="compact",
                fixed_header=True,
                classes="bg-surface-light",
                headers=(self._key("headers"), HEADERS),
                items=(self._key("listing"), []),
                height="50vh",
                style="user-select: none; cursor: pointer;",
                hover=True,
                search=(self._key("filter"),),
                items_per_page=-1,
            ):
                v3.Template(raw_attrs=["v-slot:bottom"])
                with v3.Template(raw_attrs=['v-slot:item="{ index, item }"']):
                    with v3.VDataTableRow(
                        index=("index",),
                        item=("item",),
                        click=(self.select_entry, "[item]"),
                        dblclick=(self.open_entry, "[item]"),
                        classes=(
                            f"{{ 'bg-grey': item.index === {self._key('active')}, "
                            "'cursor-pointer': 1 }",
                        ),
                    ):
                        with v3.Template(raw_attrs=["v-slot:item.name"]):
                            with html.Div(classes=style_align_center):
                                v3.VIcon(
                                    "{{ item.icon }}",
                                    size="small",
                                    classes="mr-2",
                                )
                                html.Div("{{ item.name }}")

                        with v3.Template(raw_attrs=["v-slot:item.size"]):
                            with html.Div(
                                classes=style_align_center + " justify-end",
                            ):
                                html.Div(
                                    "{{ utils.fmt.bytes(item.size, 0) }}",
                                    v_if="item.size",
                                )
                                html.Div(" - ", v_else=True)

                        with v3.Template(raw_attrs=["v-slot:item.modified"]):
                            with html.Div(
                                classes=style_align_center + " justify-end",
                            ):
                                html.Div(
                                    "{{ new Date(item.modified * 1000).toDateString() }}"
                                )

            if save:
                with html.Div(classes="d-flex align-center px-4 pt-3"):
                    v3.VTextField(
                        v_model=(self._key("filename"),),
                        label="File name",
                        hide_details=True,
                        density="compact",
                        variant="outlined",
                        autofocus=True,
                        __events=[("keydown_enter", "keydown.enter")],
                        keydown_enter=self.confirm_save,
                    )
                    v3.VSelect(
                        v_model=(self._key("format"),),
                        items=(self._key("formats"), list(self._file_ext)),
                        hide_details=True,
                        density="compact",
                        variant="outlined",
                        classes="ml-3",
                        style="max-width: 9rem;",
                    )
                html.Div(
                    f"{{{{ {self._key('target')} }}}} exists and will be replaced.",
                    v_if=(self._key("exists"),),
                    classes="text-caption text-warning px-4 pt-1",
                )
            with v3.VCardActions(classes="pt-3"):
                if save:
                    v3.VBtn(
                        text=(f"{self._key('exists')} ? 'Replace' : '{confirm}'",),
                        prepend_icon=confirm_icon,
                        color="primary",
                        variant="flat",
                        classes="mr-3 text-none",
                        disabled=(f"!({self._key('filename')} || '').trim()",),
                        click=self.confirm_save,
                    )
                else:
                    v3.VBtn(
                        confirm,
                        prepend_icon=confirm_icon,
                        color="primary",
                        variant="flat",
                        classes="mr-3 text-none",
                        # A folder pick falls back to the current folder.
                        disabled=(self._key("open_disabled"), not directory),
                        click=(
                            self.confirm,
                            f"[{self._key('listing')}[{self._key('active')}]]",
                        ),
                    )
                v3.VBtn(
                    "Cancel",
                    classes="text-none",
                    color="accent",
                    variant="tonal",
                    click=f"{self._key('loader')} = false",
                )
                v3.VSpacer()

    def _key(self, suffix):
        return f"{self._name}_{suffix}"

    def _update_listing(self):
        self.selected_entry = None
        try:
            listing = self._file_browser.listing
        except OSError as error:
            logger.warning("Cannot list {}: {}", self._file_browser.current_path, error)
            listing = []
        if self._directory:
            listing = [
                {**e, "index": i}
                for i, e in enumerate(e for e in listing if to_type(e) == "directory")
            ]
        elif self._save:
            listing = [
                {**e, "index": i}
                for i, e in enumerate(
                    e
                    for e in listing
                    if to_type(e) == "directory" or to_suffix(e) in self._file_ext
                )
            ]
        self.state[self._key("active")] = -1
        self.state[self._key("open_disabled")] = not self._directory
        self.state[self._key("listing")] = listing
        self.state[self._key("path")] = str(self._file_browser.current_path)
        if self._save:
            self._update_target()

    def open(self, start=None):
        """Show the dialog, in the folder ``start`` when it is one (the
        folder holding it when it is a file, whose name a save dialog
        proposes)."""
        if start:
            path = Path(start).expanduser()
            if self._save and path.suffix.lower() in self._file_ext:
                self.state[self._key("filename")] = path.stem
                self.state[self._key("format")] = path.suffix.lower()
            if path.is_file() or not path.exists():
                path = path.parent
            if path.is_dir():
                self._file_browser.goto(path)
        self._update_listing()
        self.state[self._key("loader")] = True

    def goto_home(self):
        self._file_browser.goto_home()
        self._update_listing()

    def goto_parent(self):
        self._file_browser.goto_parent()
        self._update_listing()

    def select_entry(self, entry):
        self.selected_entry = entry
        self.state[self._key("active")] = entry.get("index", 0) if entry else -1
        if self._directory:
            return
        if self._save:
            if entry and to_type(entry) == "file":
                self._take_name(entry)
            return

        # Update button state
        self.state[self._key("open_disabled")] = not (
            entry
            and to_type(entry) in ["file", "group"]
            and to_suffix(entry) in self._file_ext
        )

    def open_entry(self, entry):
        if to_type(entry) == "directory":
            self._file_browser.open_entry(entry)
            self._update_listing()
        elif self._save:
            self._take_name(entry)
            self.confirm_save()
        elif not self._directory:
            self.confirm(entry)

    def confirm(self, entry):
        """Close and hand the chosen path to ``on_select``: the file
        ``entry``, or for a folder pick the folder ``entry`` (the current
        folder without one)."""
        if self._directory:
            if entry and to_type(entry) == "directory":
                path = self._file_browser.to_file(entry)
            else:
                path = self._file_browser.current_path
        elif entry:
            path = self._file_browser.to_file(entry)
        else:
            return
        self.state[self._key("loader")] = False
        self._on_select(path)

    # ---- save mode -----------------------------------------------------------

    def _take_name(self, entry):
        path = Path(entry.get("name", ""))
        self.state[self._key("filename")] = path.stem
        self.state[self._key("format")] = path.suffix.lower()

    def target(self) -> Path | None:
        """The file a save dialog names: the name in the current folder,
        with the chosen format unless the name carries one."""
        name = (self.state[self._key("filename")] or "").strip()
        if not name:
            return None
        if Path(name).suffix.lower() not in self._file_ext:
            name += self.state[self._key("format")] or self._file_ext[0]
        return self._file_browser.current_path / name

    def _update_target(self, **_):
        target = self.target()
        self.state[self._key("target")] = target.name if target else ""
        self.state[self._key("exists")] = bool(target and target.exists())

    def confirm_save(self):
        target = self.target()
        if target is None or target.is_dir():
            return
        self.state[self._key("loader")] = False
        self._on_select(target)

    def _open_data(self, file_to_load):
        if self.ctx.pipeline.is_state_file(file_to_load):
            self.ctx.pipeline.load_state_file_later(file_to_load)
        else:
            self.ctx.pipeline.load_file(file_to_load)
