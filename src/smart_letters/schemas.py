from pydantic import BaseModel

from smart_letters.config import Settings


class CliContext(BaseModel, arbitrary_types_allowed=True):
    settings: Settings | None = None
