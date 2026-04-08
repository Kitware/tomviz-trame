from __future__ import annotations

import asyncio
from enum import Enum
from pathlib import Path

from loguru import logger
from paraview import servermanager, simple
from trame.app import TrameComponent
from trame.decorators import trigger

from tomviz_trame.app import data_model, module, ui
from tomviz_trame.app.ui.dynamic import DYNAMIC_TEMPLATES


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

    def create_representation(
        self, pipeline_manager, source_proxy: data_model.SourceProxy, view_info
    ):
        if self is RepresentationType.SLICE:
            from .slice import SliceRepresentation

            return SliceRepresentation(pipeline_manager, source_proxy, view_info)

        if self is RepresentationType.OUTLINE:
            from .outline import OutlineRepresentation

            return OutlineRepresentation(pipeline_manager, source_proxy, view_info)

        if self is RepresentationType.VOLUME:
            from .volume import VolumeRepresentation

            return VolumeRepresentation(pipeline_manager, source_proxy, view_info)

        return None


class PipelineManager(TrameComponent):
    def __init__(self, server=None):
        super().__init__(server=server)
        self.representations = {}  # { view_id: [rep, ...] }
        self.views = {}
        self.pending_tasks = set()
        self.pxm = servermanager.ProxyManager()
        self.tree = data_model.Pipeline(self.server)
        self.state.property_templates = []
        self.state.active_view_id = None
        self.state.active_data_id = None
        self.state.active_representation_id = None
        self.state.active_coloropacity_id = None

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
        dataset = data_model.SourceProxy(self.server, name=file_path.stem)
        dataset.proxy = reader
        dataset.update_info()

        self.add_default_coloropacity(dataset._id)
        self.add_default_representations(dataset._id, self.state.active_view_id)

        # self.state.active_coloropacity_id = dataset.coloropacity

        data_model.get_instance(self.state.active_view_id).widget_view.reset_camera()

        # Update tracking
        self.tree.children = [*self.tree.children, dataset]

        # make new data node active by default
        self.tree.active_node = [dataset._id]

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

    def add_default_coloropacity(self, data_id: str):
        logger.debug("data_id: {}", data_id)
        data_obj: data_model.SourceProxy = data_model.get_instance(data_id)

        if not data_obj.ColorOpacityId:
            coloropacity = data_model.create_default_coloropacity(data_obj)
            data_obj.coloropacity = coloropacity
            data_obj.ColorOpacityId = coloropacity._id

    def add_default_representations(self, data_id: str, view_id: str):
        self.add_representation(data_id, view_id, RepresentationType.OUTLINE.name)
        self.add_representation(data_id, view_id, RepresentationType.SLICE.name)

    def add_representation(self, data_id: str, view_id: str, type: str) -> str | None:
        logger.debug("data_id: {}, view_id: {}, type: {}", data_id, view_id, type)
        data_obj = data_model.get_instance(data_id)
        view_obj = data_model.get_instance(view_id)
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
            self, data_obj, (view_id, view_proxy)
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

    def _on_active_change(self, active_node: list[str]):
        logger.debug("active_node: {}", active_node)
        if active_node:
            obj = data_model.get_instance(active_node[0])
            coloropacity_id = getattr(obj, "ColorOpacityId", "")
            if isinstance(obj, data_model.SourceProxy):
                with self.state as s:
                    s.active_data_id = active_node[0]
                    s.active_representation_id = None
                    s.property_templates = []
                    s.active_coloropacity_id = coloropacity_id
            elif isinstance(obj, data_model.REPRESENTATIONS):
                # representation
                with self.state as s:
                    s.active_representation_id = active_node[0]
                    s.active_data_id = obj.Input
                    s.active_view_id = obj.View
                    s.active_coloropacity_id = coloropacity_id

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
                s.active_coloropacity_id = ""

    def reset_color_range(self, rep_id):
        data_model.get_instance(rep_id).reset_color_range()

    def use_color_range_as_bounds(self, rep_id):
        data_model.get_instance(rep_id).use_color_range_as_bounds()
