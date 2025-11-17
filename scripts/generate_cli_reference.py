#!/usr/bin/env python3
"""Generate CLI reference documentation from typer app."""

import sys
from pathlib import Path

# Add parent directory to path to import ynam
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import Any

from ynam.cli import app


def format_option(param_name: str, param: Any) -> str:
    """Format an option with its flags and help text."""
    # Get flag names from param_decls (typer/click structure)
    flags = []
    if hasattr(param, "param_decls") and param.param_decls:
        flags = param.param_decls

    if not flags:
        # Fallback: construct from parameter name
        flags = [f"--{param_name.replace('_', '-')}"]

    flag_str = ", ".join(f"`{flag}`" for flag in flags)

    parts = [f"- {flag_str}"]

    # Add help text if available
    if hasattr(param, "help") and param.help:
        parts.append(f": {param.help}")

    # Add default value if present
    if hasattr(param, "default") and param.default is not None and param.default is not False:
        parts.append(f" (default: {param.default})")

    return "".join(parts)


def generate_command_doc(command_name: str, command_obj: Any) -> str:
    """Generate documentation for a single command."""
    callback = command_obj.callback

    # Get docstring
    doc = callback.__doc__ or "No description available."
    doc = doc.strip()

    # Build markdown
    lines = [
        f"### {command_name}",
        "",
        doc,
        "",
        "**Usage:**",
        "",
        "```bash",
        f"uv run ynam {command_name}",
        "```",
        "",
    ]

    # Get parameters
    import inspect

    sig = inspect.signature(callback)

    args = []
    options = []

    for param_name, param in sig.parameters.items():
        if param.default == inspect.Parameter.empty:
            args.append(param_name.upper())
        elif hasattr(param.default, "help"):  # typer.Option or typer.Argument
            options.append(param.default)

    if args:
        lines.append("**Arguments:**")
        lines.append("")
        for arg in args:
            lines.append(f"- `{arg}` (required)")
        lines.append("")

    if options:
        lines.append("**Options:**")
        lines.append("")
        for param_name, param in sig.parameters.items():
            if param.default != inspect.Parameter.empty and hasattr(param.default, "help"):
                lines.append(format_option(param_name, param.default))
        lines.append("")

    return "\n".join(lines)


def generate_cli_reference() -> str:
    """Generate complete CLI reference documentation."""
    lines = [
        "---",
        "tags: [reference]",
        "---",
        "",
        "# CLI Commands Reference",
        "",
        "Complete reference for all ynam CLI commands and options.",
        "",
        "## Usage",
        "",
        "```bash",
        "uv run ynam [COMMAND] [OPTIONS]",
        "```",
        "",
        "## Global Options",
        "",
        "| Option | Description |",
        "|--------|-------------|",
        "| `--help` | Show help message and exit |",
        "",
        "## Commands",
        "",
    ]

    # Get all commands from the app
    commands = sorted(
        app.registered_commands,
        key=lambda x: x.name or (x.callback.__name__ if x.callback else ""),
    )
    for command_obj in commands:
        command_name = command_obj.name or (command_obj.callback.__name__ if command_obj.callback else "unknown")
        lines.append(generate_command_doc(command_name, command_obj))
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    """Generate and write CLI reference documentation."""
    output_path = Path(__file__).parent.parent / "docs" / "reference" / "cli-commands.md"

    doc = generate_cli_reference()

    output_path.write_text(doc)
    print(f"Generated CLI reference at {output_path}")


if __name__ == "__main__":
    main()
