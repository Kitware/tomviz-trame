import math

import numpy as np
from loguru import logger


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
    array = proxy.dataset.point_data[array_name]
    histograms, _ = np.histogram(array, bins=n_bins)

    if log_scale:
        histograms = list(map(log10, histograms))

    return histograms
