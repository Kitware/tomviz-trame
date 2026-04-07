import math

import numpy as np
from loguru import logger
from paraview import simple


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
    # May want to use ParaView to compute histogram in //
    proxy.UpdatePipeline()
    dataset = proxy.GetClientSideObject().GetOutput()
    array = dataset.GetPointData().GetArray(array_name)
    histograms, _ = np.histogram(array, bins=n_bins)

    if log_scale:
        histograms = list(map(log10, histograms))

    return histograms


def pv_extract_histograms(proxy, array_name, n_bins, log_scale):
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
