import snick
import typer

from smart_letters.config import cli as config_cli
from smart_letters.format import terminal_message
from smart_letters.generate import cli as generate_cli
from smart_letters.logging import init_logs
from smart_letters.render import cli as render_cli
from smart_letters.schemas import CliContext
from smart_letters.version import show_version


cli = typer.Typer(rich_markup_mode="rich")


@cli.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, help="Enable verbose logging to the terminal"),
    version: bool = typer.Option(False, help="Print the version of this app and exit"),
):
    """
    Welcome to Smart Letters!

    More information can be shown for each command listed below by running it with the
    --help option.
    """

    if version:
        show_version()
        ctx.exit()

    if ctx.invoked_subcommand is None:
        terminal_message(
            snick.conjoin(
                "No command provided. Please check [bold magenta]usage[/bold magenta]",
                "",
                f"[yellow]{ctx.get_help()}[/yellow]",
            ),
            subject="Need an Armasec command",
        )
        ctx.exit()

    init_logs(verbose=verbose)
    ctx.obj = CliContext()


cli.add_typer(config_cli, name="config")
cli.add_typer(generate_cli, name="generate")
cli.add_typer(render_cli, name="render")


if __name__ == "__main__":
    cli()
