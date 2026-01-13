import asyncio
from enum import Enum
from pathlib import Path

from loguru import logger
from paraview import servermanager, simple
from trame.app import TrameComponent
from trame.decorators import trigger
from trame_dataclass.core import StateDataModel, get_instance

from tomviz_trame.app import module, ui
from tomviz_trame.app.ui.dynamic import DYNAMIC_TEMPLATES


def extract_arrays(attr) -> list[str]:
    names = []
    size = attr.GetNumberOfArrays()
    for idx in range(size):
        # logger.debug("Array {}", idx)
        array = attr.GetArray(idx)
        logger.debug("name {}", array.Name)
        names.append(array.Name)
    return names


class SourceProxy(StateDataModel):
    # Data information to display
    name: str
    expand_pipeline: bool = True
    expand_representations: list[str]  # view_ids where reps are expanded
    dimensions: tuple[int, int, int] = (0, 0, 0)
    bounds: tuple[float, float, float, float, float, float] = (0, -1, 0, -1, 0, -1)
    memory: int
    type: str
    arrays: list[str]

    # Representations
    representations: dict[str, list[str]] | None  # { view_id: [rep_id, ...] }

    # Downstream pipelines
    pipelines: list[str]  # !(str -> SourceProxy) [source_proxy_id, ...]

    # Server only fields
    # proxy: object | None = field(mode=FieldMode.SERVER_ONLY)

    def update_info(self):
        proxy = getattr(self, "proxy", None)
        if proxy is None:
            return

        info = proxy.GetDataInformation()
        self.bounds = info.DataInformation.GetBounds()
        self.memory = info.DataInformation.GetMemorySize()
        self.type = info.GetDataSetTypeAsString()

        names = set()
        names.update(extract_arrays(proxy.GetPointDataInformation()))
        names.update(extract_arrays(proxy.GetCellDataInformation()))
        names.update(extract_arrays(proxy.GetFieldDataInformation()))
        self.arrays = list(names)


class Pipeline(StateDataModel):
    children: list[SourceProxy]
    active_node: list[str]


class RepresentationType(Enum):
    def __new__(cls, name: str, label: str):
        obj = object.__new__(cls)
        obj._value_ = name
        obj.label = label
        return obj

    CLIP = ("clip.svg", "Clip")
    CONTOUR = ("contour.svg", "Contour")
    MOLECULE = ("molecule.svg", "Molecule")
    OUTLINE = ("outline.svg", "Outline")
    RULER = ("ruler.svg", "Ruler")
    SCALE_CUBE = ("scale-cube.svg", "Scale Cube")
    SLICE = ("slice.svg", "Slice")
    THRESHOLD = ("threshold.svg", "Threshold")
    VOLUME = ("volume.png", "Volume")

    @property
    def icon(self):
        return f"{module.BASENAME}/assets/representations/{self.value}"

    def create_representation(self, pipeline_manager, proxy_info, view_info):
        if self is RepresentationType.SLICE:
            from .slice import SliceRepresentation

            return SliceRepresentation(pipeline_manager, proxy_info, view_info)

        if self is RepresentationType.OUTLINE:
            from .outline import OutlineRepresentation

            return OutlineRepresentation(pipeline_manager, proxy_info, view_info)

        if self is RepresentationType.VOLUME:
            from .volume import VolumeRepresentation

            return VolumeRepresentation(pipeline_manager, proxy_info, view_info)

        return None


class PipelineManager(TrameComponent):
    def __init__(self, server=None):
        super().__init__(server=server)
        self.representations = {}  # { view_id: [rep, ...] }
        self.views = {}
        self.pending_tasks = set()
        self.pxm = servermanager.ProxyManager()
        self.tree = Pipeline(self.server)
        self.state.property_templates = []
        self.state.active_view_id = None
        self.state.active_data_id = None
        self.state.active_representation_id = None

        self.tree.watch(["active_node"], self._on_active_change)

        if self.server.hot_reload:
            self.server.controller.on_server_reload.add(self.refresh_views_later)

    def __del__(self):
        self.tree.clear_watchers()

    def load_file(self, file_path: str | Path) -> str | None:
        file_path = Path(file_path).resolve()

        if not file_path.exists():
            return None

        # Create reader and track it
        reader = servermanager._getPyProxy(
            simple.TIFFSeriesReader(FileNames=[str(file_path)])
        )
        reader.UpdatePipeline()
        dataset = SourceProxy(self.server, name=file_path.stem)
        dataset.proxy = reader
        dataset.update_info()

        # make new data active by default
        self.state.active_data_id = dataset._id

        self.add_default_representations(dataset._id, self.state.active_view_id)
        get_instance(self.state.active_view_id).widget_view.reset_camera()

        # Update tracking
        self.tree.children = [*self.tree.children, dataset]

        return dataset._id

    def add_view(self) -> str:
        view = ui.RenderWindow(self.server)
        self.views[view.local_state._id] = view
        self.ctx.dock_view.add_panel(
            view.pv_id,
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
        # FIXME need more
        # - remove representations of view
        # - remove view in self.views
        view = self.views.get(view_id)
        if view:
            self.ctx.dock_view.remove_panel(view.pv_id)
            self.state.active_view_id = None

    def activate_panel(self, panel_id):
        logger.debug("activate_panel {}", panel_id)
        found = False
        for view_id, view in self.views.items():
            if view.pv_id == panel_id:
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
                view.pv_id,
                "3D View",
                view.tpl_name,
                tabComponent="tomviz-dockview-tab",
                params={
                    "templateName": view.tpl_name,
                    "viewState": view.local_state._id,
                },
            )

    def add_default_representations(self, data_id: str, view_id: str):
        self.add_representation(data_id, view_id, RepresentationType.OUTLINE.name)
        self.add_representation(data_id, view_id, RepresentationType.SLICE.name)

    def add_representation(self, data_id: str, view_id: str, type: str) -> str | None:
        logger.debug("data_id: {}, view_id: {}, type: {}", data_id, view_id, type)
        data_obj = get_instance(data_id)
        view_obj = get_instance(view_id)
        data_proxy = data_obj.proxy
        view_proxy = view_obj.pv_view

        if view_id not in data_obj.expand_representations:
            data_obj.expand_representations = [
                *data_obj.expand_representations,
                view_id,
            ]

        if data_obj.representations is None:
            data_obj.representations = {}

        if view_id not in data_obj.representations:
            data_obj.representations[view_id] = []

        new_reps = {**data_obj.representations}
        rep = RepresentationType[type].create_representation(
            self, (data_id, data_proxy), (view_id, view_proxy)
        )
        if rep:
            self.representations.setdefault(view_id, []).append(rep)
            new_reps[view_id] = [
                *new_reps[view_id],
                rep.props._id,
            ]
            data_obj.representations = new_reps

            return rep.props._id

        return None

    def _on_active_change(self, active_node):
        logger.debug("active_node: {}", active_node)
        if active_node:
            obj = get_instance(active_node[0])
            if isinstance(obj, SourceProxy):
                with self.state as s:
                    s.active_data_id = active_node[0]
                    s.active_representation_id = None
                    s.property_templates = []
            else:
                # representation
                with self.state as s:
                    s.active_representation_id = active_node[0]
                    s.active_data_id = obj.Input
                    s.active_view_id = obj.View

                    rep_tpl = DYNAMIC_TEMPLATES.get(obj.Type)
                    if rep_tpl:
                        s.property_templates = [rep_tpl]
                    else:
                        s.property_templates = []

        else:
            with self.state as s:
                s.active_data_id = None
                s.active_representation_id = None
                s.active_view_id = None
                s.property_templates = []

    def reset_color_range(self, rep_id):
        get_instance(rep_id).reset_color_range()

    def use_color_range_as_bounds(self, rep_id):
        get_instance(rep_id).use_color_range_as_bounds()
