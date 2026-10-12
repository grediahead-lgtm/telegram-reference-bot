"""telegram-reference-bot: a small FAQ and catalog bot for a small business. Standard library only."""
from .config import ConfigError, load_config, validate_config
from .bot import Bot, match_faq

__all__ = ["Bot", "ConfigError", "load_config", "match_faq", "validate_config"]
