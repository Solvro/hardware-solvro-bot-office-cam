import typer

from solvrocam.detection import solvrocam

app = typer.Typer()
app.command()(solvrocam)

if __name__ == "__main__":
    app()
