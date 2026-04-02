import math
from dataclasses import dataclass
from typing import Any

from loguru import logger
from paraview import servermanager, simple
from trame_dataclass.core import StateDataModel


def log10(v):
    if v > 0:
        return math.log10(v)
    return 0


def extract_arrays(attr) -> list[str]:
    names = []
    size = attr.GetNumberOfArrays()
    for idx in range(size):
        array = attr.GetArray(idx)
        logger.debug("name {}", array.Name)
        names.append(array.Name)
    return names


def extract_histograms(proxy, array_name, n_bins, log_scale) -> list[int | float]:
    histograms = []

    hist_proxy = simple.Histogram(
        Input=proxy,
        BinCount=n_bins,
        SelectInputArray=array_name,
    )
    hist_proxy.UpdatePipeline()
    hist_output = simple.io.FetchData(proxy=hist_proxy)
    hist_table = hist_output[0]

    for row in range(hist_table.GetNumberOfRows()):
        histograms.append(hist_table.GetValue(row, 1).ToInt())

    if log_scale:
        histograms = list(map(log10, histograms))

    return histograms


@dataclass
class SourceProxyContext:
    proxy: servermanager.Proxy | None = None
    coloropacity: Any | None = None


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

    # ColorOpacity id associated with this Source
    ColorOpacityId: str

    # Representations
    representations: dict[str, list[str]] | None  # { view_id: [rep_id, ...] }

    # Downstream pipelines
    pipelines: list[str]  # !(str -> SourceProxy) [source_proxy_id, ...]

    # Server only fields
    # proxy: object | None = field(mode=FieldMode.SERVER_ONLY)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.ctx = SourceProxyContext()

    def update_info(self):
        proxy = self.ctx.proxy

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
