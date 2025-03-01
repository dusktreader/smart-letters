import json
import os
import subprocess
import tempfile
from importlib import resources
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer
from inflection import parameterize
from loguru import logger
from markdown import markdown
from openai import OpenAI
from weasyprint import HTML

from smart_letters.config import attach_settings
from smart_letters.exceptions import handle_abort
from smart_letters.format import terminal_message, simple_message


def generate_letter(
    api_key: str,
    posting_text: str,
    resume_text: str,
    example_text: str | None = None,
    reprompts: list[tuple[str, str]] | None = None,
) -> str:
    client = OpenAI(api_key=api_key)

    messages = []

    messages.append(
        dict(
            role="developer",
            content="""
                You are a professional resume writer and career coach. Your task is to
                generate a cover letter for a job application based on the provided job
                posting and resume. You will be given a job posting and a resume, and
                you need to create a tailored cover letter that highlights the
                candidate's qualifications and suitability for the position.
            """,
        ),
    )

    messages.append(
        dict(
            role="developer",
            content=f"""
                This is the job posting. It is html scraped from a job board. It
                contains a lot of html markup, but you should ignore that and focus on
                the text content.

                {posting_text}
            """,
        ),
    )

    messages.append(
        dict(
            role="developer",
            content=f"""
                Use this resume as you write the letter. It highlights the skills and
                experience of the candidate.

                {resume_text}
            """,
        ),
    )

    if example_text:
        messages.append(
            dict(
                role="developer",
                content=f"""
                    You should use this cover letter as reference for what I would like
                    the resulting cover letter to look like. It is a markdown document.

                    {example_text}
                """,
            ),
        )

    messages.append(
        dict(
            role="developer",
            content="""
                The cover letter should not sound like it was written by a machine. It
                should be direct, personal, and energetic. It should be professional,
                but informal in an almost daring way.

                Avoid sentences of the form, "With X, I will Y". Do not use any of the
                following words:

                - challenge
                - opportunity
                - leverage
                - passionate

                The letter should highlight the candidate's leadership, technical
                excellence, and ambition.

                Do not include a salutation or closing. Only include the body of the
                letter. Don't include any other text. Just print the body of the letter
                itself.

                Again, do not provide any friendly text before the letter. Do not
                explain what you are doing. Do not say "Here is your letter". Just print
                the damn letter.
            """,
        )
    )

    messages.append(dict(role="user", content="Please write me a nice letter!"))

    if reprompts is not None:
        for old_letter, user_feedback in reprompts:
            messages.append(dict(role="assistant", content=old_letter))
            messages.append(dict(role="user", content=user_feedback))

    kwargs = dict(
        model="gpt-4o",
        n=1,
        messages=messages,
    )
    logger.debug(
        f"Getting openai output using params: \n{json.dumps(kwargs, indent=2)}"
    )

    cmp = client.chat.completions.create(**kwargs)  # type: ignore
    text = cmp.choices[0].message.content
    assert text is not None

    return text


def assemble_letter(
    text: str,
    candidate_name: str,
    company: str | None,
    heading_text: str | None,
    sig_path: Path | None,
) -> str:
    parts = []

    if heading_text:
        parts.append(heading_text)

    if company:
        parts.append(f"To the Hiring Team at {company}:")
    else:
        parts.append("Dear Hiring Manager,")

    parts.append("")
    parts.append(text)
    parts.append("")
    parts.append("Best regards,")
    parts.append("")

    if sig_path:
        parts.append(f"![signature](file://{sig_path.absolute()})")
        parts.append("")

    parts.append(candidate_name)

    return "\n".join(parts)


def edit_letter(text: str) -> str:
    logger.debug("Editing generated letter")
    with tempfile.NamedTemporaryFile() as tmp_file:
        tmp_path = Path(tmp_file.name)
        tmp_path.write_text(text)
        subprocess.run([os.environ["EDITOR"], str(tmp_path)])
        return tmp_path.read_text()


def asset_path(file_name: str):
    return resources.files(f"{__package__}.assets") / file_name


def write_letter(
    text: str,
    filename_prefix: str,
    company: str | None,
    position: str | None,
    dump_html: bool,
) -> Path:
    logger.debug("Saving letter to file")
    name = filename_prefix
    if company:
        name += f"--{parameterize(company)}"
    if position:
        name += f"--{parameterize(position)}"
    pdf_path = Path(f"{name}.pdf")

    html_content = markdown(text)

    if dump_html:
        html_path = Path(f"{name}.html")
        logger.debug(f"Dumping html to {html_path}")
        html_path.write_text(html_content)

    css_paths = [asset_path("styles.css")]
    html = HTML(string=html_content)
    html.write_pdf(pdf_path, stylesheets=css_paths)
    return pdf_path


cli = typer.Typer()


@cli.callback(invoke_without_command=True)
@handle_abort
@attach_settings
def generate(
    ctx: typer.Context,
    posting_url: Annotated[str, typer.Argument(help="The URL of the job posting.")],
    company: Annotated[
        str | None, typer.Option(help="The name of the company.")
    ] = None,
    position: Annotated[str | None, typer.Option(help="The title for the job.")] = None,
    example_letter: Annotated[
        Path | None, typer.Option(help="An example letter to use as a reference.")
    ] = None,
    dump_html: Annotated[
        bool, typer.Option(help="[FOR DEBUGGING] Dump generated HTML to a file.")
    ] = False,
    fake: Annotated[
        bool,
        typer.Option(
            help="[FOR DEBUGGING] Use a fake letter body instead of fetching one from OpenAI."
        ),
    ] = False,
):
    settings = ctx.obj.settings
    resume_path: Path = settings.resume_path
    candidate_name = settings.candidate_name
    filename_prefix = settings.filename_prefix
    heading_path = settings.heading_path
    sig_path = settings.sig_path

    logger.debug(f"Loading resume from {resume_path}")
    resume_text = resume_path.read_text()

    heading_text: str | None = None
    if heading_path:
        logger.debug(f"Loading heading text from {heading_path}")
        heading_text = heading_path.read_text()

    example_text: str | None = None
    if example_letter:
        logger.debug(f"Loading example text from {example_letter}")
        example_text = example_letter.read_text()

    logger.debug(f"Pulling posting from {posting_url}")
    response = httpx.get(posting_url)
    response.raise_for_status()
    posting_text = response.text

    logger.debug("Generating letter")

    api_key = ctx.obj.settings.openai_api_key

    generate_args: list[Any] = [api_key, posting_text, resume_text]
    generate_kwargs: dict[str, Any] = dict(
        example_text=example_text,
    )

    assemble_args = [
        candidate_name,
        company,
        heading_text,
        sig_path,
    ]

    if fake:
        text = asset_path("fake.txt").read_text()
    else:
        text = generate_letter(*generate_args, **generate_kwargs)

    full_text = assemble_letter(text, *assemble_args)

    accepted = False
    reprompts = []

    while not accepted:
        terminal_message(full_text, subject="Generated Letter", markdown=True)

        accepted = typer.confirm("Are you satisfied with the letter?", default=True)

        if not accepted:
            reprompts.append(
                (
                    text,
                    typer.prompt("What can I do to fix it?", default="Just try again"),
                )
            )
            generate_kwargs["reprompts"] = reprompts

            logger.debug("Regenerating letter based on feedback")
            text = generate_letter(*generate_args, **generate_kwargs)
            full_text = assemble_letter(text, *assemble_args)

    edit = typer.confirm("Would you like to edit the letter?", default=False)
    if edit:
        edit_letter(full_text)

    pdf_path = write_letter(full_text, filename_prefix, company, position, dump_html)

    simple_message(f"Cover letter saved to {pdf_path}")
