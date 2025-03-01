from contextlib import contextmanager
import json
from functools import wraps
from pathlib import Path
from typing import Annotated, Any

import snick
import typer
from loguru import logger
from pydantic import AfterValidator, BaseModel, ValidationError

from smart_letters.exceptions import Abort, handle_abort
from smart_letters.cache import CACHE_DIR, init_cache
from smart_letters.format import terminal_message


settings_path: Path = CACHE_DIR / "settings.json"


def file_exists(value: Path | None) -> Path | None:
    if value is None:
        return value

    value = value.expanduser()
    if not value.exists():
        raise ValueError(f"File not found at {value}")
    return value


class Settings(BaseModel):
    openai_api_key: str
    resume_path: Annotated[Path, AfterValidator(file_exists)]
    candidate_name: str
    filename_prefix: str = "cover-letter"
    heading_path: Annotated[Path | None, AfterValidator(file_exists)] = None
    sig_path: Annotated[Path | None, AfterValidator(file_exists)] = None


@contextmanager
def handle_config_error():
    try:
        yield
    except ValidationError as err:
        raise Abort(
            snick.conjoin(
                "A configuration error was detected.",
                "",
                "Details:",
                "",
                f"[red]{err}[/red]",
            ),
            subject="Configuration Error",
            log_message="Configuration error",
        )


def init_settings(**settings_values) -> Settings:
    with handle_config_error():
        logger.debug("Validating settings")
        return Settings(**settings_values)


def update_settings(settings: Settings, **settings_values) -> Settings:
    with handle_config_error():
        logger.debug("Validating settings")
        return settings.model_copy(update=settings_values)


def unset_settings(settings: Settings, *unset_keys) -> Settings:
    with handle_config_error():
        logger.debug("Unsetting settings")
        return Settings(
            **{
                k: v
                for (k, v) in settings.model_dump(exclude_unset=True).items()
                if k not in unset_keys
            }
        )


def attach_settings(func):
    @wraps(func)
    def wrapper(ctx: typer.Context, *args, **kwargs):
        try:
            logger.debug(f"Loading settings from {settings_path}")
            settings_values = json.loads(settings_path.read_text())
        except FileNotFoundError:
            raise Abort(
                f"""
                No settings file found at {settings_path}!

                Run the set-config sub-command first to establish your settings.
                """,
                subject="Settings file missing!",
                log_message="Settings file missing!",
            )
        logger.debug("Binding settings to CLI context")
        ctx.obj.settings = init_settings(**settings_values)
        return func(ctx, *args, **kwargs)

    return wrapper


def dump_settings(settings: Settings):
    logger.debug(f"Saving settings to {settings_path}")
    settings_values = settings.model_dump_json(indent=2)
    settings_path.write_text(settings_values)


def clear_settings():
    logger.debug(f"Removing saved settings at {settings_path}")
    settings_path.unlink(missing_ok=True)


cli = typer.Typer()


@cli.command()
@handle_abort
@init_cache
def bind(
    openai_api_key: Annotated[
        str, typer.Option(help="The API key needed to access OpenAI")
    ],
    resume_path: Annotated[Path, typer.Option(help="The path to your resume")],
    candidate_name: Annotated[
        str, typer.Option(help="The name of the candidate to use in the closing")
    ],
    filename_prefix: Annotated[
        str, typer.Option(help="The filename prefix to use for your cover letter")
    ] = "cover-letter",
    sig_path: Annotated[
        Path | None, typer.Option(help="The path to your signature")
    ] = None,
    heading_path: Annotated[
        Path | None, typer.Option(help="The path to your markdown heading")
    ] = None,
):
    """
    Bind the configuration to the app.
    """
    logger.debug(f"Initializing settings with {locals()}")
    settings = init_settings(
        openai_api_key=openai_api_key,
        resume_path=resume_path,
        candidate_name=candidate_name,
        filename_prefix=filename_prefix,
        sig_path=sig_path,
        heading_path=heading_path,
    )
    dump_settings(settings)


@cli.command()
@handle_abort
@init_cache
@attach_settings
def update(
    ctx: typer.Context,
    openai_api_key: Annotated[
        str | None, typer.Option(help="The API key needed to access OpenAI")
    ] = None,
    resume_path: Annotated[
        Path | None, typer.Option(help="The path to your resume")
    ] = None,
    candidate_name: Annotated[
        str | None, typer.Option(help="The name of the candidate to use in the closing")
    ] = None,
    filename_prefix: Annotated[
        str | None,
        typer.Option(help="The filename prefix to use for your cover letter"),
    ] = None,
    sig_path: Annotated[
        Path | None, typer.Option(help="The path to your signature")
    ] = None,
    heading_path: Annotated[
        Path | None, typer.Option(help="The path to your markdown heading")
    ] = None,
):
    """
    Bind the configuration to the app.
    """
    logger.debug(f"Updating settings with {locals()}")
    kwargs: dict[str, Any] = {}
    if openai_api_key is not None:
        kwargs["openai_api_key"] = openai_api_key
    if resume_path is not None:
        kwargs["resume_path"] = resume_path
    if candidate_name is not None:
        kwargs["candidate_name"] = candidate_name
    if filename_prefix is not None:
        kwargs["filename_prefix"] = filename_prefix
    if sig_path is not None:
        kwargs["sig_path"] = sig_path
    if heading_path is not None:
        kwargs["heading_path"] = heading_path

    settings = update_settings(ctx.obj.settings, **kwargs)
    dump_settings(settings)


@cli.command()
@handle_abort
@init_cache
@attach_settings
def unset(
    ctx: typer.Context,
    openai_api_key: Annotated[
        bool, typer.Option(help="The API key needed to access OpenAI")
    ] = False,
    resume_path: Annotated[bool, typer.Option(help="The path to your resume")] = False,
    candidate_name: Annotated[
        bool, typer.Option(help="The name of the candidate to use in the closing")
    ] = False,
    filename_prefix: Annotated[
        bool, typer.Option(help="The filename prefix to use for your cover letter")
    ] = False,
    sig_path: Annotated[bool, typer.Option(help="The path to your signature")] = False,
    heading_path: Annotated[
        bool, typer.Option(help="The path to your markdown heading")
    ] = False,
):
    """
    Bind the configuration to the app.
    """
    logger.debug(f"Updating settings with {locals()}")
    keys = [k for k in locals() if locals()[k]]
    settings = unset_settings(ctx.obj.settings, *keys)
    dump_settings(settings)


@cli.command()
@handle_abort
@init_cache
@attach_settings
def show(ctx: typer.Context):
    """
    Show the config that is currently bound to the app.
    """
    parts = []
    for field_name, field_value in ctx.obj.settings:
        parts.append((field_name, field_value))
    max_field_len = max(len(field_name) for field_name, _ in parts)
    message = "\n".join(f"[bold]{k:<{max_field_len}}[/bold] -> {v}" for k, v in parts)
    terminal_message(message, subject="Current Configuration")


@cli.command()
@handle_abort
@init_cache
def clear():
    """
    Clear the config from the app.
    """
    logger.debug("Clearing settings")
    clear_settings()
