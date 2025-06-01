import platform
import typer


app = typer.Typer()
if platform.release().find("rpi") != -1:
    from solvrocam.detection import detect

    app.command()(detect)
else:
    from solvrocam.debug import debug

    app.command()(debug)

if __name__ == "__main__":
    app()
