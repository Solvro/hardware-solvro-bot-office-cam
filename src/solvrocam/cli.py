import typer

from solvrocam.file import app as file_app
from solvrocam.preview import app as preview_app

app = typer.Typer()

try:
    from solvrocam.picam import app as camera_app

    app.add_typer(camera_app, name="camera")
except ImportError:
    pass

app.add_typer(file_app, name="file")
app.add_typer(preview_app, name="preview")


if __name__ == "__main__":
    app()
