"""SIPL Language Toolkit: parser, interpreter, trace and semantic terms."""

from .parser import parse, parse_file

__version__ = "0.4.1"

__all__ = ["parse", "parse_file", "__version__"]
