from typing import Any

from loguru import logger
from mako.template import Template

from smart_letters.exceptions import Abort
from smart_letters.schemas import PromptConfig, Prompts
from smart_letters.utilities import asset_path


def get_prompts(prompt_config: PromptConfig) -> Prompts:
    dev_prompt_path = prompt_config.dev_prompt_path or asset_path("dev_prompt.txt")
    logger.debug(f"Loading dev prompt from {dev_prompt_path}")
    user_prompt_template_path = prompt_config.user_prompt_template_path or asset_path("user_prompt.txt.mako")
    logger.debug(f"Loading user prompt template from {user_prompt_template_path}")

    return Prompts(
        dev_prompt=dev_prompt_path.read_text(),
        user_prompt_tempate=user_prompt_template_path.read_text(),
    )


def build_prompts(prompts: Prompts, **user_prompt_vars) -> list[dict[str, Any]]:
    logger.debug("Assembling prompts for OpenAI")
    try:
        rendered_user_prompt = Template(prompts.user_prompt_tempate).render(**user_prompt_vars)
    except Exception:
        raise Abort("Couldn't render the user prompt", subject="Render failed")

    return [
        dict(role="developer", content=prompts.dev_prompt),
        dict(role="user", content=rendered_user_prompt),
    ]
