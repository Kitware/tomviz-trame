from trame.app import dataclass
from trame.widgets import vuetify3 as v3

OPERATOR_DATA_CLASSES = {}


def gui_bool(parameter):
    name = parameter.get("name")
    label = parameter.get("label")
    return v3.VSwitch(
        label=label,
        v_model=f"self.{name}",
        hide_details=True,
    ).html


def gui_number(parameter):
    # FIXME handle array of numbers
    name = parameter.get("name")
    label = parameter.get("label")
    py_type = parameter.get("type")
    minimum = parameter.get("minimum")
    maximum = parameter.get("maximum")
    precision = parameter.get("precision", 0)

    if py_type == "double" and precision == 0:
        precision = 6

    with v3.VNumberInput(
        label=label,
        v_model=f"self.{name}",
    ) as root:
        if precision:
            root.precision = precision
        if minimum is not None:
            root.min = (minimum,)
        if maximum is not None:
            root.max = (maximum,)

        return root.html


def gui_enumeration(parameter):
    name = parameter.get("name")
    label = parameter.get("label")
    options = parameter.get("options")
    items = [
        {"title": next(iter(entry.keys())), "value": idx}
        for idx, entry in enumerate(options)
    ]

    return v3.VSelect(label=label, v_model=f"self.{name}", items=(str(items),)).html


def gui_xyz_header(parameter):
    name = parameter.get("name")

    with v3.VRow() as root:
        for idx, label in enumerate(["X", "Y", "Z"]):
            with v3.VCol():
                v3.VNumberInput(
                    label=label,
                    v_model=f"self.{name}[{idx}]",
                    precision="6",
                )

        return root.html


TYPE_MAPPING = {
    "bool": gui_bool,
    "int": gui_number,
    "double": gui_number,
    "enumeration": gui_enumeration,
    "xyz_header": gui_xyz_header,
    "file": "",
    "directory": "",
}


def param_to_gui(parameter) -> str:
    fn = TYPE_MAPPING.get(parameter.get("type"))
    return fn(parameter) if fn else ""


def to_gui(params) -> str:
    return "".join(["<v-col>", *[param_to_gui(p) for p in params], "</v-col>"])


def to_param(name, param):
    param_type = param.get("type")
    param_default = param.get("default")

    core_py_type = None
    if param_type == "bool":
        core_py_type = bool
    elif param_type == "int":
        core_py_type = int
    elif param_type == "double":
        core_py_type = float
    elif param_type == "enumeration":
        core_py_type = int
    elif param_type == "xyz_header":
        core_py_type = tuple[float, float, float]
    elif param_type in {"file", "directory"}:
        core_py_type = str

    if core_py_type is None:
        msg = f"Invalid parameter type::{param_type} for Operator({name}::{param.get('name')})"
        raise ValueError(msg)

    py_type = core_py_type
    py_default = param_default
    add_on = {}
    if isinstance(param_default, list | tuple):
        py_type = list[core_py_type]
        py_default = list(py_default)
        add_on["deep_reactive"] = True

    return dataclass.Sync(py_type, py_default, **add_on)


def get_operator_data_class(meta):
    name = meta.get("name")
    parameters = meta.get("parameters", [])
    klass = OPERATOR_DATA_CLASSES.get(name)

    if klass:
        return klass

    # print("=" * 60)
    # print("meta", meta)
    # for p in parameters:
    #     print(p)
    # print("=" * 60)

    # Generate klass
    namespace = {
        p.get("name", "coord"): to_param(name, p)
        for p in parameters
        if TYPE_MAPPING.get(p.get("type"))
    }

    # Generate UI
    tpl = to_gui(parameters)

    @classmethod
    def generate_gui(*_):
        return tpl

    namespace["generate_gui"] = generate_gui

    # Create class
    klass = type(name, (dataclass.StateDataModel,), namespace)
    OPERATOR_DATA_CLASSES[name] = klass
    return klass


def to_operator_data(server, meta):
    klass = get_operator_data_class(meta)
    return klass(server)
