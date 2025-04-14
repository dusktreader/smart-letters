from contextlib import contextmanager
import json
from functools import wraps
from pathlib import Path
from typing import Annotated, Any
import os

import snick
import typer
from inflection import dasherize
from loguru import logger
from pydantic import AfterValidator, BaseModel, PositiveInt, ValidationError, Field

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


def has_editor(value: str | None) -> str:
    if value is not None:
        return value

    try:
        return os.environ["EDITOR"]
    except Exception:
        raise ValueError("Couldn't load editor from environment. Please set it explicitly")


class OpenAIParams(BaseModel):
    model: str = "gpt-4o"
    temperature: Annotated[float, Field(ge=0.0, le=2.0)] = 1.0
    top_p: Annotated[float, Field(ge=0.0, le=1.0)] = 1.0
    frequency_penalty: Annotated[float, Field(ge=-2.0, le=2.0)] = 0.0
    presence_penalty: Annotated[float, Field(ge=-2.0, le=2.0)] = 0.0


def parse_openai_params(value: str) -> OpenAIParams:
    value_dict = json.loads(value)
    return OpenAIParams(**value_dict)


class Settings(BaseModel):
    openai_api_key: str
    resume_path: Annotated[Path, AfterValidator(file_exists)]
    candidate_name: str
    filename_prefix: str = "cover-letter"
    heading_path: Annotated[Path | None, AfterValidator(file_exists)] = None
    sig_path: Annotated[Path | None, AfterValidator(file_exists)] = None
    output_directory: Annotated[Path | None, AfterValidator(file_exists)] = None
    markdown_textwrap: PositiveInt | None = None
    dev_prompt_path: Annotated[Path | None, AfterValidator(file_exists)] = None
    user_prompt_template_path: Annotated[Path | None, AfterValidator(file_exists)] = None
    editor_command: Annotated[str | None, AfterValidator(has_editor)] = None
    openai_params: OpenAIParams = OpenAIParams()

    invalid_warning: Annotated[
        str | None,
        Field(
            exclude=True,
            description="""
            An optional warning that can be included when the model is invalid.

            Used when we use the `attach_settings` decorator with `validate=False`.
        """,
        ),
    ] = None


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


def init_settings(validate: bool = True, **settings_values) -> Settings:
    with handle_config_error():
        logger.debug("Validating settings")
        try:
            return Settings(**settings_values)
        except ValidationError as err:
            if validate:
                raise
            settings = Settings.model_construct(**settings_values)
            settings.invalid_warning = str(err)
            return settings


def update_settings(settings: Settings, **settings_values) -> Settings:
    with handle_config_error():
        logger.debug("Validating settings")
        settings_dict = settings.model_dump(exclude_unset=True)

        openai_params = settings_dict.pop("openai_params", {})
        new_openai_params = settings_values.pop("openai_params", None)
        if new_openai_params is not None:
            openai_params.update(**new_openai_params.model_dump(exclude_unset=True))

        settings_dict.update(openai_params=openai_params, **settings_values)
        return Settings(**settings_dict)


def unset_settings(settings: Settings, *unset_keys) -> Settings:
    with handle_config_error():
        logger.debug("Unsetting settings")
        return Settings(**{k: v for (k, v) in settings.model_dump(exclude_unset=True).items() if k not in unset_keys})


def attach_settings(original_function=None, *, validate=True):
    """
    Attach the settings to the CLI context.

    Optionally, skip validation of the settings. This is useful in case the config
    file being loaded is not valid, but we still want to use the settings. Then, we
    can update the settings with correct values.

    Uses recipe for decorator with optional arguments from:
    https://stackoverflow.com/a/24617244/642511
    """

    def _decorate(func):
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
            ctx.obj.settings = init_settings(validate=validate, **settings_values)
            return func(ctx, *args, **kwargs)

        return wrapper

    if original_function:
        return _decorate(original_function)
    else:
        return _decorate


def dump_settings(settings: Settings):
    logger.debug(f"Saving settings to {settings_path}")
    settings_values = settings.model_dump_json(indent=2)
    settings_path.write_text(settings_values)


def clear_settings():
    logger.debug(f"Removing saved settings at {settings_path}")
    settings_path.unlink(missing_ok=True)


def show_settings(settings: Settings):
    parts = []
    for field_name, field_value in settings:
        if field_name == "invalid_warning":
            continue
        parts.append((dasherize(field_name), field_value))
    max_field_len = max(len(field_name) for field_name, _ in parts)
    message = "\n".join(f"[bold]{k:<{max_field_len}}[/bold] -> {v}" for k, v in parts)
    if settings.invalid_warning:
        message += f"\n\n[red]Configuration is invalid: {settings.invalid_warning}[/red]"
    terminal_message(message, subject="Current Configuration")


cli = typer.Typer(help="Configure the app, change settings, or view how it's currently configured")


@cli.command()
@handle_abort
@init_cache
def bind(
    openai_api_key: Annotated[str, typer.Option(help="The API key needed to access OpenAI")],
    resume_path: Annotated[Path, typer.Option(help="The path to your resume")],
    candidate_name: Annotated[
        str,
        typer.Option(help="The name of the candidate to use in the closing"),
    ],
    filename_prefix: Annotated[
        str,
        typer.Option(help="The filename prefix to use for your cover letter"),
    ] = "cover-letter",
    sig_path: Annotated[
        Path | None,
        typer.Option(help="The path to your signature"),
    ] = None,
    heading_path: Annotated[
        Path | None,
        typer.Option(help="The path to your markdown heading"),
    ] = None,
    output_directory: Annotated[
        Path | None,
        typer.Option(
            help="""
                The directory where cover letters should be saved.
                If unset, letters will be saved in the current directory
            """
        ),
    ] = None,
    markdown_textwrap: Annotated[
        int | None,
        typer.Option(
            help="""
                If set, wrap the markdown text to the given number of characters.
            """,
        ),
    ] = None,
    dev_prompt_path: Annotated[
        Path | None,
        typer.Option(help="An optional path to the developer prompt for letter generation"),
    ] = None,
    user_prompt_template_path: Annotated[
        Path | None,
        typer.Option(help="An optional path to the user prompt template for letter generation"),
    ] = None,
    editor_command: Annotated[
        str | None,
        typer.Option(
            help="""
                Provide a system command to use for opening files in an editor.
                If not provided, will attempt to load system default editor (from env var $EDITOR).
            """
        ),
    ] = None,
    openai_params: Annotated[
        OpenAIParams,
        typer.Option(
            parser=parse_openai_params,
            help="""
            Provide the OpenAI parameters as a JSON string.
            If not provided, will use the default parameters.
            """
        ),
    ] = OpenAIParams(),
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
        output_directory=output_directory,
        markdown_textwrap=markdown_textwrap,
        dev_prompt_path=dev_prompt_path,
        user_prompt_path=user_prompt_template_path,
        editor_command=editor_command,
        openai_params=openai_params,
    )
    dump_settings(settings)
    show_settings(settings)


@cli.command()
@handle_abort
@init_cache
@attach_settings(validate=False)
def update(
    ctx: typer.Context,
    openai_api_key: Annotated[str | None, typer.Option(help="The API key needed to access OpenAI")] = None,
    resume_path: Annotated[Path | None, typer.Option(help="The path to your resume")] = None,
    candidate_name: Annotated[str | None, typer.Option(help="The name of the candidate to use in the closing")] = None,
    filename_prefix: Annotated[
        str | None,
        typer.Option(help="The filename prefix to use for your cover letter"),
    ] = None,
    sig_path: Annotated[Path | None, typer.Option(help="The path to your signature")] = None,
    heading_path: Annotated[Path | None, typer.Option(help="The path to your markdown heading")] = None,
    output_directory: Annotated[
        Path | None,
        typer.Option(
            help="""
                The directory where cover letters should be saved.
                If unset, letters will be saved in the current directory
            """
        ),
    ] = None,
    markdown_textwrap: Annotated[
        int | None,
        typer.Option(
            help="""
                If set, wrap the markdown text to the given number of characters.
            """,
        ),
    ] = None,
    dev_prompt_path: Annotated[
        Path | None,
        typer.Option(help="An optional path to the developer prompt for letter generation"),
    ] = None,
    user_prompt_template_path: Annotated[
        Path | None,
        typer.Option(help="An optional path to the user prompt template for letter generation"),
    ] = None,
    editor_command: Annotated[
        str | None,
        typer.Option(
            help="""
                Provide a system command to use for opening files in an editor.
                If not provided, will attempt to load system default editor (from env var $EDITOR).
            """
        ),
    ] = None,
    openai_params: Annotated[
        OpenAIParams | None,
        typer.Option(
            parser=parse_openai_params,
            help="""
            Provide the OpenAI parameters as a JSON string.
            If not provided, will use the default parameters.
            """
        ),
    ] = None,
):
    """
    Update one or more configuration settings that are bound to the app.
    """
    logger.debug(f"Updating settings with {locals()}")
    kwargs: dict[str, Any] = {k: v for (k, v) in locals().items() if v is not None}
    settings = update_settings(ctx.obj.settings, **kwargs)
    dump_settings(settings)
    show_settings(settings)


@cli.command()
@handle_abort
@init_cache
@attach_settings(validate=False)
def unset(
    ctx: typer.Context,
    openai_api_key: Annotated[bool, typer.Option(help="The API key needed to access OpenAI")] = False,
    resume_path: Annotated[bool, typer.Option(help="The path to your resume")] = False,
    candidate_name: Annotated[bool, typer.Option(help="The name of the candidate to use in the closing")] = False,
    filename_prefix: Annotated[bool, typer.Option(help="The filename prefix to use for your cover letter")] = False,
    sig_path: Annotated[bool, typer.Option(help="The path to your signature")] = False,
    heading_path: Annotated[bool, typer.Option(help="The path to your markdown heading")] = False,
    output_directory: Annotated[
        bool,
        typer.Option(
            help="""
                The directory where cover letters should be saved.
                If unset, letters will be saved in the current directory
            """
        ),
    ] = False,
    markdown_textwrap: Annotated[
        bool,
        typer.Option(
            help="""
                If set, wrap the markdown text to the given number of characters.
            """,
        ),
    ] = False,
    dev_prompt_path: Annotated[
        bool,
        typer.Option(help="An optional path to the developer prompt for letter generation"),
    ] = False,
    user_prompt_template_path: Annotated[
        bool,
        typer.Option(help="An optional path to the user prompt template for letter generation"),
    ] = False,
    editor_command: Annotated[
        bool,
        typer.Option(
            help="""
                Provide a system command to use for opening files in an editor.
                If not provided, will attempt to load system default editor (from env var $EDITOR).
            """
        ),
    ] = False,
    openai_params: Annotated[
        bool,
        typer.Option(
            parser=parse_openai_params,
            help="""
            Provide the OpenAI parameters as a JSON string.
            If not provided, will use the default parameters.
            """
        ),
    ] = False,
):
    """
    Remove a configuration setting that was previously bound to the app.
    """
    logger.debug(f"Updating settings with {locals()}")
    keys = [k for k in locals() if locals()[k]]
    settings = unset_settings(ctx.obj.settings, *keys)
    dump_settings(settings)
    show_settings(settings)


@cli.command()
@handle_abort
@init_cache
@attach_settings(validate=False)
def show(ctx: typer.Context):
    """
    Show the config that is currently bound to the app.
    """
    show_settings(ctx.obj.settings)


@cli.command()
@handle_abort
@init_cache
def clear():
    """
    Clear the config from the app.
    """
    logger.debug("Clearing settings")
    clear_settings()
