from dataclasses import dataclass
import json
import subprocess
from pathlib import Path
from typing import Annotated

import httpx
import typer
import pyperclip
from inflection import parameterize
from loguru import logger
from openai import OpenAI

from smart_letters.cache import BACKUP_DIR, init_cache
from smart_letters.config import attach_settings
from smart_letters.exceptions import handle_abort
from smart_letters.format import terminal_message, simple_message
from smart_letters.prompt import get_prompts, build_prompts
from smart_letters.utilities import asset_path
from smart_letters.render import render_letter
from smart_letters.schemas import LetterConfig, PromptConfig, RenderConfig


@dataclass
class Reprompt:
    old_letter: str
    user_feedback: str


def pull_posting(letter_config: LetterConfig) -> str:
    logger.debug(f"Pulling posting from {letter_config.posting_url}")
    response = httpx.get(letter_config.posting_url)
    response.raise_for_status()
    return response.text


def pull_resume(letter_config: LetterConfig) -> str:
    logger.debug(f"Loading resume from {letter_config.resume_path}")
    return letter_config.resume_path.read_text()


def pull_example(letter_config: LetterConfig) -> str | None:
    if letter_config.example_path:
        logger.debug(f"Loading example text from {letter_config.example_path}")
        return letter_config.example_path.read_text()
    return None


def pull_heading(letter_config: LetterConfig) -> str | None:
    if letter_config.heading_path:
        logger.debug(f"Loading heading text from {letter_config.heading_path}")
        return letter_config.heading_path.read_text()
    return None


def generate_letter(
    prompt_config: PromptConfig,
    letter_config: LetterConfig,
    reprompts: list[Reprompt],
    posting_text: str,
    resume_text: str,
    example_text: str | None = None,
) -> str:
    logger.debug("Generating letter using OpenAI")
    client = OpenAI(api_key=letter_config.openai_api_key)

    prompts = get_prompts(prompt_config)
    messages = build_prompts(
        prompts,
        posting_text=posting_text,
        resume_text=resume_text,
        example_text=example_text,
    )

    for reprompt in reprompts:
        messages.append(dict(role="assistant", content=reprompt.old_letter))
        messages.append(dict(role="user", content=reprompt.user_feedback))

    kwargs = dict(model="gpt-4o", n=1)
    logger.debug(f"Using params for OpenAI: \n{json.dumps(kwargs, indent=2)}")
    cmp = client.chat.completions.create(messages=messages, **kwargs)  # type: ignore
    text = cmp.choices[0].message.content
    assert text is not None
    return text


def assemble_letter(
    letter_config: LetterConfig,
    letter_text: str,
    heading_text: str | None,
) -> str:
    logger.debug("Assembling letter")
    parts = []

    if heading_text:
        parts.append(heading_text)

    if letter_config.company:
        parts.append(f"To the Hiring Team at {letter_config.company}:")
    else:
        parts.append("Dear Hiring Manager,")

    parts.append("")
    parts.append(letter_text)
    parts.append("")
    parts.append("Best regards,")
    parts.append("")

    if letter_config.sig_path:
        parts.append(f"![signature](file://{letter_config.sig_path.absolute()})")
        parts.append("")

    parts.append(letter_config.candidate_name)

    return "\n".join(parts)


def show_letter(letter_text: str, footer_text: str | None = None):
    terminal_message(letter_text, subject="Generated Letter", markdown=True, footer=footer_text)


def request_feedback(letter_text: str) -> str:
    show_letter(letter_text)
    accepted = typer.confirm("Are you satisfied with the letter?", default=True)
    if accepted:
        return ""
    return typer.prompt("What can I do to fix it?", default="Just try again")


def should_render(cli_param: bool | None) -> bool:
    if cli_param is not None:
        return cli_param
    return typer.confirm("Should I render the letter to PDF?", default=True)


def read_cached_letter(letter_config: LetterConfig) -> str:
    return letter_config.cache_path.read_text()


def write_cached_letter(letter_config: LetterConfig, letter_text):
    logger.debug(f"Writing current version of letter to {letter_config.cache_path}")
    letter_config.cache_path.write_text(letter_text)


def edit_letter(letter_config: LetterConfig, letter_text: str):
    edit = typer.confirm("Would you like to edit the letter?", default=False)
    if not edit:
        return letter_text

    write_cached_letter(letter_config, letter_text)
    logger.debug(f"Editing generated letter at {letter_config.cache_path}")
    subprocess.run([letter_config.editor_command, str(letter_config.cache_path)])
    return read_cached_letter(letter_config)


def get_file_stem(letter_config: LetterConfig) -> str:
    stem = letter_config.filename_prefix
    if letter_config.company:
        stem += f"--{parameterize(letter_config.company)}"
    if letter_config.position:
        stem += f"--{parameterize(letter_config.position)}"
    return stem


def build_letter(prompt_config: PromptConfig, letter_config: LetterConfig) -> str:
    logger.debug("Building letter")
    full_text = ""
    heading_text: str | None = pull_heading(letter_config)
    if letter_config.fake:
        logger.debug("Using fake text for letter")
        letter_text = asset_path("fake.txt").read_text()
        full_text = assemble_letter(letter_config, letter_text, heading_text)
        write_cached_letter(letter_config, full_text)
    else:
        logger.debug("Generating letter")
        posting_text: str = pull_posting(letter_config)
        resume_text: str = pull_resume(letter_config)
        example_text: str | None = pull_example(letter_config)

        accepted = False
        reprompts: list[Reprompt] = []

        while not accepted:
            letter_text = generate_letter(
                prompt_config, letter_config, reprompts, posting_text, resume_text, example_text
            )
            full_text = assemble_letter(letter_config, letter_text, heading_text)
            write_cached_letter(letter_config, full_text)
            feedback = request_feedback(full_text)
            if feedback:
                logger.debug("Letter was not accepted, requesting feedback")
                reprompts.append(Reprompt(old_letter=full_text, user_feedback=feedback))
            else:
                accepted = True

    full_text = edit_letter(letter_config, full_text)

    return full_text


cli = typer.Typer()


@cli.callback(invoke_without_command=True)
@handle_abort
@init_cache
@attach_settings
def generate(
    ctx: typer.Context,
    posting_url: Annotated[str, typer.Argument(help="The URL of the job posting.")],
    company: Annotated[str | None, typer.Option(help="The name of the company.")] = None,
    position: Annotated[str | None, typer.Option(help="The title for the job.")] = None,
    example_letter: Annotated[Path | None, typer.Option(help="An example letter to use as a reference.")] = None,
    fake: Annotated[
        bool,
        typer.Option(help="[FOR DEBUGGING] Use a fake letter body instead of fetching one from OpenAI."),
    ] = False,
    render: Annotated[
        bool | None,
        typer.Option(
            help="""
                If this option is provided, render (or don't render) the generated Markdown to PDF.
                If not provided, you will be asked if you want to render it after the letter is generated.
            """,
        ),
    ] = None,
):
    """
    Generate a cover letter for a job posting listed at the provided URL.

    This command will use an LLM prompt (either builtin or user provided in config) to generate
    a cover letter (in Markdown). You may also render the letter into a styled PDF.
    """
    prompt_config = PromptConfig(
        dev_prompt_path=ctx.obj.settings.dev_prompt_path,
        user_prompt_template_path=ctx.obj.settings.user_prompt_template_path,
    )

    letter_config = LetterConfig(
        resume_path=ctx.obj.settings.resume_path,
        candidate_name=ctx.obj.settings.candidate_name,
        filename_prefix=ctx.obj.settings.filename_prefix,
        openai_api_key=ctx.obj.settings.openai_api_key,
        cache_path=BACKUP_DIR.joinpath(f".{ctx.obj.timestamp}.md"),
        editor_command=ctx.obj.settings.editor_command,
        sig_path=ctx.obj.settings.sig_path,
        heading_path=ctx.obj.settings.heading_path,
        example_path=example_letter,
        output_directory=ctx.obj.settings.output_directory,
        company=company,
        position=position,
        posting_url=posting_url,
        fake=fake,
    )

    letter_text: str = build_letter(prompt_config, letter_config)

    if should_render(render):
        render_config = RenderConfig(
            file_stem=get_file_stem(letter_config),
            timestamp=ctx.obj.timestamp,
            output_directory=ctx.obj.settings.output_directory,
        )
        pdf_path = render_letter(letter_text, render_config)
        simple_message(f"Letter saved to {pdf_path}")
    else:
        show_kwargs = {}
        try:
            pyperclip.copy(letter_text)
            show_kwargs["footer_text"] = "Letter copied to clipboard"
        except Exception as exc:
            logger.debug(f"Could not copy letter to clipboard: {exc}")
        show_letter(letter_text, **show_kwargs)
