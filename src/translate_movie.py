"""Compatibility shim moved to src/ as requested."""

from translate_movie.core import main


if __name__ == "__main__":
    raise SystemExit(main())
