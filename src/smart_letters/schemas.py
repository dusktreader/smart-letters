from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path

from smart_letters.config import Settings


@dataclass
class CliContext:
    settings: Settings | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d.%H%M%S"))


@dataclass
class PromptConfig:
    dev_prompt_path: Path | None
    user_prompt_template_path: Path | None


@dataclass
class Prompts:
    dev_prompt: str
    user_prompt_tempate: str


@dataclass
class LetterConfig:
    resume_path: Path
    candidate_name: str
    filename_prefix: str
    openai_api_key: str
    openai_params: dict
    posting_loc: str
    fake: bool
    cache_path: Path
    editor_command: str
    sig_path: Path | None = None
    heading_path: Path | None = None
    example_path: Path | None = None
    output_directory: Path | None = None
    markdown_textwrap: int | None = None
    company: str | None = None
    position: str | None = None


@dataclass
class RenderConfig:
    file_stem: str
    timestamp: str
    output_directory: Path | None = None
