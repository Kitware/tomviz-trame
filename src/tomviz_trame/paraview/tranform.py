from loguru import logger
from paraview.util.vtkAlgorithm import smdomain, smproperty, smproxy
from vtkmodules.util.vtkAlgorithm import VTKPythonAlgorithmBase


@smproxy.filter()
@smproperty.input(name="Input")
@smdomain.datatype(dataTypes=["vtkImageData"], composite_data_supported=False)
class TomvizVolumeTransform(VTKPythonAlgorithmBase):
    def __init__(self):
        super().__init__(nInputPorts=1, nOutputPorts=1, outputType="vtkImageData")

    def RequestDataObject(self, request, inInfo, outInfo):
        inData = self.GetInputData(inInfo, 0, 0)
        outData = self.GetOutputData(outInfo, 0)
        assert inData is not None
        if outData is None or (not outData.IsA(inData.GetClassName())):
            outData = inData.NewInstance()
            outInfo.GetInformationObject(0).Set(outData.DATA_OBJECT(), outData)
        return super().RequestDataObject(request, inInfo, outInfo)

    def RequestData(self, _, inInfo, outInfo):
        inData = self.GetInputData(inInfo, 0, 0)
        outData = self.GetOutputData(outInfo, 0)
        assert outData.IsA(inData.GetClassName())
        logger.info("tomviz filter execution !!!")
        outData.ShallowCopy(inData)
        return 1
