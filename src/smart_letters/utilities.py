from contextlib import contextmanager
from importlib import resources

from rich.progress import Progress, SpinnerColumn, TextColumn


def asset_path(file_name: str):
    return resources.files(f"{__package__}.assets") / file_name


@contextmanager
def spinner(text: str, max_length: int = 80):
    text = text[:max_length] if len(text) > max_length else text
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
        progress.add_task(description=f"{text}...", total=None)
        yield


