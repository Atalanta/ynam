"""Configuration file management for ynam."""

import os
import tomllib
from pathlib import Path
from typing import Any, Optional

import tomli_w


DEFAULT_CONFIG_PATH = Path.home() / ".ynam" / "config.toml"


def get_config_path() -> Path:
    """Get the config file path.

    Returns:
        Path to the config file.
    """
    return DEFAULT_CONFIG_PATH


def create_default_config(config_path: Optional[Path] = None) -> None:
    """Create default config file with secure permissions.

    Args:
        config_path: Path to config file. If None, uses default location.
    """
    if config_path is None:
        config_path = get_config_path()

    config_path.parent.mkdir(parents=True, exist_ok=True)

    default_config = {
        "sources": [],
    }

    with open(config_path, "wb") as f:
        tomli_w.dump(default_config, f)

    os.chmod(config_path, 0o600)


def load_config(config_path: Optional[Path] = None) -> dict[str, Any]:
    """Load configuration from TOML file.

    Args:
        config_path: Path to config file. If None, uses default location.

    Returns:
        Configuration dictionary.

    Raises:
        FileNotFoundError: If config file doesn't exist.
    """
    if config_path is None:
        config_path = get_config_path()

    with open(config_path, "rb") as f:
        return tomllib.load(f)


def save_config(config: dict[str, Any], config_path: Optional[Path] = None) -> None:
    """Save configuration to TOML file.

    Args:
        config: Configuration dictionary.
        config_path: Path to config file. If None, uses default location.
    """
    if config_path is None:
        config_path = get_config_path()

    with open(config_path, "wb") as f:
        tomli_w.dump(config, f)

    os.chmod(config_path, 0o600)


def get_source(name: str, config_path: Optional[Path] = None) -> Optional[dict[str, Any]]:
    """Get a source configuration by name.

    Args:
        name: Source name.
        config_path: Path to config file. If None, uses default location.

    Returns:
        Source configuration dictionary or None if not found.
    """
    config = load_config(config_path)

    for source in config.get("sources", []):
        if source.get("name") == name:
            return source

    return None


def add_source(source: dict[str, Any], config_path: Optional[Path] = None) -> None:
    """Add or update a source configuration.

    Args:
        source: Source configuration dictionary.
        config_path: Path to config file. If None, uses default location.
    """
    config = load_config(config_path)

    sources = config.get("sources", [])
    source_name = source.get("name")

    for i, existing_source in enumerate(sources):
        if existing_source.get("name") == source_name:
            sources[i] = source
            break
    else:
        sources.append(source)

    config["sources"] = sources
    save_config(config, config_path)
