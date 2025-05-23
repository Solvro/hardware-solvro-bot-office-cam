import typer

from solvro_cam.solvrocam import solvrocam

app = typer.Typer()
app.command()(solvrocam)

if __name__ == "__main__":
    app()
