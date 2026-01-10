from pathlib import Path

from tomviz_trame import __version__

serve_path = str(Path(__file__).with_name("serve").resolve())

BASENAME = f"__trame_tomviz_{__version__}"

serve = {
    BASENAME: serve_path,
}
styles = [
    f"{BASENAME}/style.css",
]
