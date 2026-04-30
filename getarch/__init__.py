"""getarch - declarative Arch Linux base-system installer."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("getarch")
except PackageNotFoundError:
    __version__ = "0.0.0+local"

__all__ = ["__version__"]
