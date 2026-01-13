# tomviz-trame

ParaView and Trame based tomviz

![tomviz](https://raw.githubusercontent.com/Kitware/tomviz-trame/main/tomviz.png)

## License

This library is OpenSource and follow the Apache Software License

## Installation

Install the application/library

```sh
uv venv -p 3.12
source .venv/bin/activate
uv pip install .
```

Run the application

```sh
pvpython --venv .venv -m tomviz
```

## Development setup

We recommend using uv for setting up and managing a virtual environment for your
development.

```sh
# Create venv and install all dependencies
uv sync --all-extras --dev

# Activate environment
source .venv/bin/activate

# Install commit analysis
pre-commit install
pre-commit install --hook-type commit-msg

# Allow live code edit
uv pip install -e .
```

For running tests and checks, you can run `nox`.

```sh
# run all
nox

# lint
nox -s lint

# tests
nox -s tests
```

## Professional Support

- [Training](https://www.kitware.com/courses/trame/): Learn how to confidently
  use trame from the expert developers at Kitware.
- [Support](https://www.kitware.com/trame/support/): Our experts can assist your
  team as you build your web application and establish in-house expertise.
- [Custom Development](https://www.kitware.com/trame/support/): Leverage
  Kitware’s 25+ years of experience to quickly build your web application.
