import typer

from solvrocam.file import app as file
from solvrocam.preview import app as preview

app = typer.Typer()

try:
    from solvrocam.picam import app as camera

    app.add_typer(camera)
except ImportError:
    pass

app.add_typer(file)
app.add_typer(preview)


if __name__ == "__main__":
    app()
