def transform(dataset):
    """Apply a Laplace filter to dataset."""

    import numpy as np
    import scipy.ndimage

    array = dataset.active_scalars

    # Transform the dataset
    result = np.empty_like(array)
    scipy.ndimage.filters.laplace(array, output=result)

    # Set the result as the new scalars.
    dataset.active_scalars = result
