"""Parameter panels generated from a catalog entry's JSON ``parameters``
list. ``OperatorParameters`` holds the definition and one value per
parameter; the Vuetify HTML editing them is a server template
(``trame__template_operator_<n>``) recomputed whenever the definition
changes, so the panel follows the transform editor's edits."""

import itertools

from loguru import logger
from trame.app.dataclass import StateDataModel, Sync
from trame.widgets import vuetify3 as v3


def gui_bool(parameter):
    name = parameter.get("name")
    label = parameter.get("label", name)

    if name is None:
        logger.warning("Parameter {} has no name. Skipping.", parameter)
        return False

    return v3.VSwitch(
        label=label,
        v_model=f"self.values['{name}']",
        hide_details=True,
    ).html


def gui_number(parameter):
    name = parameter.get("name")
    label = parameter.get("label", name)

    if name is None:
        logger.warning("Parameter {} has no name. Skipping.", parameter)
        return False

    # handling of default/data-default
    default_values = []
    if "default" in parameter:
        d_value = parameter.get("default")
        if isinstance(d_value, list | tuple):
            default_values.extend(d_value)
        else:
            default_values.append(d_value)
    elif "data-default" in parameter:
        # !! data-default needs datasource !!
        logger.critical("Need datasource for {}", parameter)
        # https://github.com/OpenChemistry/tomviz/blob/master/tomviz/InterfaceBuilder.cxx#L257C37-L257C51
        return False

    # handling minimum
    minimum = parameter.get("minimum")
    min_values = [min(default_values) for _ in default_values]
    if "minimum" in parameter:
        min_value = parameter.get("minimum")
        if isinstance(min_value, list | tuple):
            for idx, v in enumerate(min_value):
                min_values[idx] = v
        else:
            size = len(min_values)
            for i in range(size):
                min_values[i] = min_value

    # handling maximum
    maximum = parameter.get("maximum")
    max_values = [max(default_values) for _ in default_values]
    if "maximum" in parameter:
        max_value = parameter.get("maximum")
        if isinstance(max_value, list | tuple):
            for idx, v in enumerate(max_value):
                max_values[idx] = v
        else:
            size = len(max_values)
            for i in range(size):
                max_values[i] = max_value

    # handling precision / step
    py_type = parameter.get("type")
    precision = parameter.get("precision", -1)
    step = parameter.get("step", -1)
    if py_type == "double" and precision < 0:
        precision = 6

    size = len(default_values)
    if size == 1:
        with v3.VNumberInput(
            label=label,
            v_model=f"self.values['{name}']",
            control_variant="stacked",
            variant="outlined",
            density="compact",
            hide_details=True,
            classes="my-2",
        ) as root:
            if precision > 0:
                root.precision = precision
            if step > 0:
                root.step = (step,)
            if minimum is not None:
                root.min = (minimum,)
            if maximum is not None:
                root.max = (maximum,)

            return root.html

    # Need to display an array of widget
    with v3.VCol(classes="px-0 pb-3 pt-0") as root:
        v3.VLabel(label)
        with v3.VRow(no_gutters=True):
            for i in range(size):
                with v3.VCol():
                    with v3.VNumberInput(
                        v_model=f"self.values['{name}'][{i}]",
                        control_variant="hidden",
                        variant="outlined",
                        density="compact",
                        hide_details=True,
                    ) as item:
                        if precision > 0:
                            item.precision = precision
                        if step > 0:
                            item.step = (step,)
                        item.min = (min_values[i],)
                        item.max = (max_values[i],)

        return root.html


def gui_enumeration(parameter):
    name = parameter.get("name")
    label = parameter.get("label", name)

    if name is None:
        logger.warning("Parameter {} has no name. Skipping.", parameter)
        return False

    options = parameter.get("options")
    items = [
        {"title": next(iter(entry.keys())), "value": idx}
        for idx, entry in enumerate(options)
    ]

    return v3.VSelect(
        label=label,
        v_model=f"self.values['{name}']",
        items=(str(items),),
        variant="outlined",
        hide_details=True,
        density="compact",
        classes="my-2",
    ).html


def gui_xyz_header(_):
    with v3.VRow(no_gutters=True) as root:
        for label in ["X", "Y", "Z"]:
            with v3.VCol():
                v3.VLabel(label, classes="d-block text-center")

        return root.html


def gui_string(parameter):
    name = parameter.get("name")
    label = parameter.get("label", name)

    if name is None:
        logger.warning("Parameter {} has no name. Skipping.", parameter)
        return False

    return v3.VTextField(
        label=label,
        v_model=f"self.values['{name}']",
        variant="outlined",
        hide_details=True,
        density="compact",
        classes="my-2",
    ).html


def gui_scalars(parameter):
    # No array picker yet: the kernel runs with its own default, usually the
    # active scalars (see CORE_TYPES).
    logger.debug("No GUI for select_scalars yet: {}", parameter.get("name"))
    return False


PATH_TYPES = {"file", "save_file", "directory"}
# Types without an entry have no control and no field. "dataset" is one on
# purpose: like in the desktop app, such a parameter is an input port of the
# node (the library adds it), linked in the pipeline.
TYPE_MAPPING = {
    "bool": gui_bool,
    "int": gui_number,
    "double": gui_number,
    "enumeration": gui_enumeration,
    "xyz_header": gui_xyz_header,
    "file": gui_string,
    "save_file": gui_string,
    "directory": gui_string,
    "string": gui_string,
    "select_scalars": gui_scalars,  # RemoveArrays, PowerSpectrumDensity, ...
    # finding: reconstruction / label_map / table
}


def param_to_gui(parameter) -> str:
    fn = TYPE_MAPPING.get(parameter.get("type"))
    return fn(parameter) if fn else False


def to_gui(params) -> str:
    controls = [param_to_gui(p) for p in params]
    return "".join(['<v-col class="pa-0">', *filter(None, controls), "</v-col>"])


def _coerce_one(core_type, value):
    if value is None or isinstance(value, core_type):
        return value
    return core_type(value)


def coerce(parameter, value):
    """``value`` as the declared type of ``parameter`` (state files store
    ``4`` for a double; lists are coerced element-wise). ``None`` stays."""
    core_type = CORE_TYPES[parameter.get("type")]
    if isinstance(value, list | tuple):
        return [_coerce_one(core_type, v) for v in value]
    return _coerce_one(core_type, value)


# The parameters with a value in the panel. "xyz_header" is decoration only
# and "select_scalars" has no picker yet (gui_scalars): left out, the kernel
# falls back to its own default, usually the active scalars.
CORE_TYPES = {
    "bool": bool,
    "int": int,
    "double": float,
    "enumeration": int,
    "string": str,
    **dict.fromkeys(PATH_TYPES, str),
}


def default_values(parameters) -> dict:
    """Parameter name -> default value, for the parameters with a value.
    Raises ``ValueError`` (or ``TypeError``) on a default of the wrong
    type."""
    values = {}
    for parameter in parameters:
        name = parameter.get("name")
        if name is None or parameter.get("type") not in CORE_TYPES:
            continue
        default = parameter.get("default")
        if default is None and parameter.get("type") == "bool":
            default = False
        values[name] = coerce(parameter, default)
    return values


# Template names are lowercased on the client (component names), which
# dataclass ids (mixed case) do not survive: number them instead.
_TEMPLATE_IDS = itertools.count(1)


class OperatorParameters(StateDataModel):
    """The parameter panel of a catalog node: its ``definition`` (the
    entry's ``parameters`` list) and ``values`` (name -> value, for the
    parameters with a control). The panel's HTML lives in the trame state
    under ``template_key`` (not the class' ``generate_gui``, which
    trame-dataclass caches per class) and is rendered with
    ``client.ServerTemplate(name=template_name)``; ``set_definition``
    recomputes both values and template."""

    definition = Sync(list, list)
    values = Sync(dict, dict, client_deep_reactive=True)
    template_name = Sync(str, "")

    def __init__(self, server, parameters=None, **kwargs):
        super().__init__(server, **kwargs)
        self.template_name = f"operator_{next(_TEMPLATE_IDS)}"
        self.set_definition(parameters or [])

    @property
    def template_key(self) -> str:
        return f"trame__template_{self.template_name}"

    def parameter(self, name) -> dict | None:
        """The definition of parameter ``name``."""
        for parameter in self.definition:
            if parameter.get("name") == name:
                return parameter
        return None

    def set_definition(self, parameters, keep=None):
        """Use the ``parameters`` definition: values go back to their
        defaults, but for ``keep`` (name -> value) entries still declared.
        Raises ``ValueError`` (or ``TypeError``) on an unusable default,
        leaving the panel untouched."""
        values = default_values(parameters)
        self.definition = list(parameters)
        for name, value in (keep or {}).items():
            if name in values:
                values[name] = coerce(self.parameter(name), value)
        self.values = values
        self.update_template()

    def set(self, **values):
        """Set the values of declared parameters (others are ignored),
        coerced to their declared types."""
        self.values = {
            **self.values,
            **{
                name: coerce(self.parameter(name), value)
                for name, value in values.items()
                if name in self.values
            },
        }

    def panel_html(self) -> str:
        """The panel's HTML for the current definition."""
        return (
            f"<trame-dataclass :instance=\"'{self._id}'\" "
            'v-slot="{ dataclass: self }">'
            f"{to_gui(self.definition)}"
            "</trame-dataclass>"
        )

    def update_template(self):
        """Publish ``panel_html()`` as the panel's template."""
        if self.server is not None:
            with self.server.state as state:
                state[self.template_key] = self.panel_html()

    def release(self):
        """Empty the panel's template once its node is gone."""
        if self.server is not None:
            with self.server.state as state:
                state[self.template_key] = "<div></div>"


def to_parameters_model(server, meta) -> OperatorParameters:
    return OperatorParameters(server, parameters=meta.get("parameters") or [])
