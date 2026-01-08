from trame.assets.local import LocalFileManager

ASSETS = LocalFileManager(__file__)

ASSETS.url("favicon", "./favicon.png")
ASSETS.url("title", "./logo.png")
ASSETS.url("title_dark", "./logo-dark.png")

# Data
ASSETS.url("d_open", "./data/open.svg")
ASSETS.url("d_operator", "./data/operator.svg")

# Representations
ASSETS.url("r_clip", "./representations/clip.svg")
ASSETS.url("r_contour", "./representations/contour.svg")
ASSETS.url("r_molecule", "./representations/molecule.svg")
ASSETS.url("r_outline", "./representations/outline.svg")
ASSETS.url("r_ruler", "./representations/ruler.svg")
ASSETS.url("r_scale_cube", "./representations/scale-cube.svg")
ASSETS.url("r_slice", "./representations/slice-ortho.svg")
ASSETS.url("r_threshold", "./representations/threshold.svg")
ASSETS.url("r_volume", "./representations/volume.png")

# View
ASSETS.url("v_palette", "./view/Palette.svg")
ASSETS.url("PickCenter", "./view/PickCenter.svg")
ASSETS.url("ResetCamera", "./view/ResetCamera.svg")
ASSETS.url("ResetCenter", "./view/ResetCenter.svg")
ASSETS.url("RotateCameraCCW", "./view/RotateCameraCCW.svg")
ASSETS.url("RotateCameraCW", "./view/RotateCameraCW.svg")
ASSETS.url("ShowCenterAxes", "./view/ShowCenterAxes.svg")
ASSETS.url("ShowOrientationAxes", "./view/ShowOrientationAxes.svg")
ASSETS.url("XMinus", "./view/XMinus.svg")
ASSETS.url("XPlus", "./view/XPlus.svg")
ASSETS.url("YMinus", "./view/YMinus.svg")
ASSETS.url("YPlus", "./view/YPlus.svg")
ASSETS.url("ZMinus", "./view/ZMinus.svg")
ASSETS.url("ZPlus", "./view/ZPlus.svg")

# Settings
ASSETS.url("Settings", "./icons/Toolbar.svg")
# ASSETS.url("Settings", "./icons/Settings.svg")
