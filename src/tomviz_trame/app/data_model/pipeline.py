from paraview import servermanager
from trame.app.dataclass import (
    ServerOnly,
    StateDataModel,
    Sync,
    TypeValidation,
)

from tomviz_trame.app.utils import data


class SourceProxy(StateDataModel):
    # Data information to display
    name = Sync(str, "")
    expand_pipeline = Sync(bool, True)
    expand_representations = Sync(
        list[str], list
    )  # view_ids where reps are expanded ("WindowInternalState"?)
    dimensions = Sync(tuple[int, int, int], (0, 0, 0))
    bounds: tuple[float, float, float, float, float, float] = (0, -1, 0, -1, 0, -1)
    memory = Sync(int, 0)
    type = Sync(str, "")
    arrays = Sync(list[str], list)

    # ColorOpacity id associated with this Source
    ColorOpacityId = Sync(str, None)

    # Representations
    representations = Sync(
        dict[str, list[str]] | None, dict
    )  # { view_id: [rep_id, ...] }

    # Downstream pipelines
    pipelines = Sync(list[str], list)  # !(str -> SourceProxy) [source_proxy_id, ...]

    # Server only fields
    proxy = ServerOnly(servermanager.Proxy | None)
    coloropacity = ServerOnly(None, type_checking=TypeValidation.SKIP)

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


class Pipeline(StateDataModel):
    children = Sync(list[SourceProxy], list, has_dataclass=True)
    active_node = Sync(list[str], list)
