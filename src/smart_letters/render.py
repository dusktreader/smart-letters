from pathlib import Path
from typing import Annotated

import typer
from loguru import logger
from markdown import markdown
from weasyprint import HTML

from smart_letters.exceptions import handle_abort, Abort
from smart_letters.cache import init_cache, BACKUP_DIR
from smart_letters.config import attach_settings
from smart_letters.format import simple_message
from smart_letters.schemas import RenderConfig
from smart_letters.utilities import asset_path


cli = typer.Typer()


@cli.callback(invoke_without_command=True)
@handle_abort
@init_cache
@attach_settings
def render(
    ctx: typer.Context,
    md_file: Annotated[Path, typer.Argument(help="The path to the markdown file to render.")],
    file_stem: Annotated[str | None, typer.Option(help="The stem of the file to save.")] = None,
):
    """
    Render a Markdown cover letter to styled PDF.

    This command is useful if you just want to render a Markdown letter without generating one.
    This might be useful, for example, if you are using a cached letter.
    """
    render_config = RenderConfig(
        file_stem=file_stem or md_file.stem,
        timestamp=ctx.obj.timestamp,
        output_directory=ctx.obj.settings.output_directory,
    )

    try:
        letter_text = md_file.read_text()
    except Exception:
        raise Abort(f"Couldn't read the markdown file from {md_file}", subject="Render failed")

    pdf_path = render_letter(letter_text, render_config)
    simple_message(f"Letter rendered to {pdf_path}")


def render_letter(
    letter_text: str,
    render_config: RenderConfig,
) -> Path:
    logger.debug("Rendering markdown to file")

    pdf_path = Path(f"{render_config.file_stem}.pdf")
    if render_config.output_directory:
        pdf_path = render_config.output_directory / pdf_path

    html_content = markdown(letter_text)
    html_file_path = BACKUP_DIR / Path(f".{render_config.timestamp}.{render_config.file_stem}.html")
    logger.debug(f"Dumping html to {html_file_path}")
    html_file_path.write_text(html_content)

    css_paths = [asset_path("styles.css")]
    html = HTML(string=html_content)
    html.write_pdf(pdf_path, stylesheets=css_paths)

    logger.debug(f"Letter rendered to {pdf_path}")
    return pdf_path
