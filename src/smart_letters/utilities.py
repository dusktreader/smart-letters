from importlib import resources


def asset_path(file_name: str):
    return resources.files(f"{__package__}.assets") / file_name
