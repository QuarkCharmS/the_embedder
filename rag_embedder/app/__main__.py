"""
Module entry point - allows `python -m app` to work.

Simply imports and calls cli.main().
"""

from app.cli import main

if __name__ == '__main__':
    main()
