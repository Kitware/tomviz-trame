from typing import Self

from paraview import servermanager
from trame.app.dataclass import StateDataModel, Sync, TypeValidation, watch
from trame_dataclass.v2 import ServerOnly

from tomviz_trame.app.utils import data

from .pipeline import SourceProxy


class OperatorTreeNode(StateDataModel):
    title = Sync(str)
    children = Sync(list, list, has_dataclass=True)
    count = Sync(int)

    def update_count(self):
        local_count = 0
        for n in self.children:
            local_count += n.update_count()
        self.count = local_count
        return local_count


class OperatorNode(StateDataModel):
    title = Sync(str)
    name = Sync(str)
    tags = Sync(list[str], list)
    favorite = Sync(bool, False)
    icon = Sync(str)

    def update_count(self):
        return 1

    @watch("favorite")
    def _on_fav(self, favorite):
        self.server.controller.update_favorite_operator(self.name, favorite)


class Operator(StateDataModel):
    # Data information to display
    name = Sync(str, "")
    dimensions = Sync(tuple[int, int, int], (0, 0, 0))
    bounds: tuple[float, float, float, float, float, float] = (0, -1, 0, -1, 0, -1)
    memory = Sync(int, 0)
    type = Sync(str, "")
    arrays = Sync(list[str], list)

    # Operator specific
    operator_name = Sync(str)
    icon = Sync(str, "mdi-plus")
    input = Sync(Self | SourceProxy, has_dataclass=True)
    config = Sync(dict, dict, client_deep_reactive=True)

    # UI state
    expand_pipeline = Sync(bool, True)
    expand_representations = Sync(
        list[str], list
    )  # view_ids where reps are expanded ("WindowInternalState"?)

    # Color/Opacity handling
    color_opacity = Sync(
        "ColorOpacity",
        has_dataclass=True,
        type_checking=TypeValidation.SKIP,
    )

    # Representations
    representations = Sync(
        dict[str, list[str]] | None, dict
    )  # { view_id: [rep_id, ...] }

    # Downstream pipelines
    pipelines = Sync(list, list, has_dataclass=True)  # ["SourceProxy" | "Operator"]

    # Server only fields
    proxy = ServerOnly(servermanager.Proxy | None)

    def update_info(self):
        if self.proxy is None:
            return

        info = self.proxy.GetDataInformation()
        self.bounds = info.DataInformation.GetBounds()
        self.memory = info.DataInformation.GetMemorySize()
        self.type = info.GetDataSetTypeAsString()

        names = set()
        names.update(data.extract_arrays(self.proxy.GetPointDataInformation()))
        names.update(data.extract_arrays(self.proxy.GetCellDataInformation()))
        names.update(data.extract_arrays(self.proxy.GetFieldDataInformation()))
        self.arrays = list(names)
