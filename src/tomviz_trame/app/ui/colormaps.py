import base64

from paraview import simple
from trame_dataclass.core import StateDataModel
from vtkmodules.vtkCommonCore import vtkUnsignedCharArray
from vtkmodules.vtkCommonDataModel import vtkImageData
from vtkmodules.vtkIOImage import vtkPNGWriter

COLOR_PALETTE = [
    "#4CAF50",
    "#FB8C00",
    "#E82D2D",
    "#2196F3",
    "#ffffff",
    "#000000",
]


def color_to_float_rgb(color):
    red = int(color[1:3], 16)
    green = int(color[3:5], 16)
    blue = int(color[5:7], 16)
    return (red / 255, green / 255, blue / 255)


class ColorPreset(StateDataModel):
    name: str
    imgs: tuple[str, str] = ("", "")  # normal, inverted


class ColorMaps(StateDataModel):
    presets: dict[str, ColorPreset]


def generate_colormaps(server):
    color_maps = {}
    samples = 255
    rgb = [0, 0, 0]
    names = simple.ListColorPresetNames()
    lut = simple.GetColorTransferFunction("to_generate_image")
    vtk_lut = lut.GetClientSideObject()
    colorArray = vtkUnsignedCharArray()
    colorArray.SetNumberOfComponents(3)
    colorArray.SetNumberOfTuples(samples)
    imgData = vtkImageData()
    imgData.SetDimensions(samples, 1, 1)
    imgData.GetPointData().SetScalars(colorArray)
    writer = vtkPNGWriter()
    writer.WriteToMemoryOn()
    writer.SetInputData(imgData)
    writer.SetCompressionLevel(1)

    for name in names:
        imgs = []
        for inverted in range(2):
            lut.ApplyPreset(name, True)
            if inverted:
                lut.InvertTransferFunction()

            v_min = lut.RGBPoints[0]
            v_max = lut.RGBPoints[-4]
            step = (v_max - v_min) / (samples - 1)

            for i in range(samples):
                value = v_min + step * float(i)
                vtk_lut.GetColor(value, rgb)
                r = int(round(rgb[0] * 255))
                g = int(round(rgb[1] * 255))
                b = int(round(rgb[2] * 255))
                colorArray.SetTuple3(i, r, g, b)

            writer.Write()
            img_bytes = writer.GetResult()

            base64_img = base64.standard_b64encode(img_bytes).decode("utf-8")
            imgs.append(f"data:image/png;base64,{base64_img}")

        color_maps[name] = imgs

    server.state.palette = COLOR_PALETTE

    return ColorMaps(
        server,
        presets={k: ColorPreset(server, name=k, imgs=v) for k, v in color_maps.items()},
    )
