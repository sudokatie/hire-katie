"""Configuration loading and validation."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8081


@dataclass
class DatabaseConfig:
    url: str = "sqlite:///data/hire_katie.db"


@dataclass
class StripeConfig:
    secret_key: str = ""
    publishable_key: str = ""
    webhook_secret: str = ""
    price_id: str = ""


@dataclass
class EmailConfig:
    from_address: str = "blackabee@gmail.com"
    from_name: str = "Katie"
    templates_dir: str = "src/templates/email"


@dataclass
class AdminConfig:
    password: str = ""


@dataclass
class Config:
    server: ServerConfig = field(default_factory=ServerConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    stripe: StripeConfig = field(default_factory=StripeConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    admin: AdminConfig = field(default_factory=AdminConfig)


_config: Optional[Config] = None


def load_config(config_dir: Optional[Path] = None) -> Config:
    """Load configuration from yaml files and environment variables.
    
    Priority (highest to lowest):
    1. Environment variables
    2. config/local.yaml
    3. config/config.yaml
    4. Defaults
    """
    global _config
    
    if _config is not None:
        return _config
    
    if config_dir is None:
        config_dir = Path(__file__).parent.parent / "config"
    
    config = Config()
    
    # Load base config
    base_config_path = config_dir / "config.yaml"
    if base_config_path.exists():
        with open(base_config_path) as f:
            data = yaml.safe_load(f) or {}
            _merge_config(config, data)
    
    # Load local overrides
    local_config_path = config_dir / "local.yaml"
    if local_config_path.exists():
        with open(local_config_path) as f:
            data = yaml.safe_load(f) or {}
            _merge_config(config, data)
    
    # Environment variable overrides
    if env_val := os.environ.get("STRIPE_SECRET_KEY"):
        config.stripe.secret_key = env_val
    if env_val := os.environ.get("STRIPE_PUBLISHABLE_KEY"):
        config.stripe.publishable_key = env_val
    if env_val := os.environ.get("STRIPE_WEBHOOK_SECRET"):
        config.stripe.webhook_secret = env_val
    if env_val := os.environ.get("ADMIN_PASSWORD"):
        config.admin.password = env_val
    if env_val := os.environ.get("DATABASE_URL"):
        config.database.url = env_val
    
    _config = config
    return config


def _merge_config(config: Config, data: dict) -> None:
    """Merge yaml data into config object."""
    if "server" in data:
        if "host" in data["server"]:
            config.server.host = data["server"]["host"]
        if "port" in data["server"]:
            config.server.port = data["server"]["port"]
    
    if "database" in data:
        if "url" in data["database"]:
            config.database.url = data["database"]["url"]
    
    if "stripe" in data:
        if "secret_key" in data["stripe"]:
            config.stripe.secret_key = data["stripe"]["secret_key"]
        if "publishable_key" in data["stripe"]:
            config.stripe.publishable_key = data["stripe"]["publishable_key"]
        if "webhook_secret" in data["stripe"]:
            config.stripe.webhook_secret = data["stripe"]["webhook_secret"]
        if "price_id" in data["stripe"]:
            config.stripe.price_id = data["stripe"]["price_id"]
    
    if "email" in data:
        if "from_address" in data["email"]:
            config.email.from_address = data["email"]["from_address"]
        if "from_name" in data["email"]:
            config.email.from_name = data["email"]["from_name"]
        if "templates_dir" in data["email"]:
            config.email.templates_dir = data["email"]["templates_dir"]
    
    if "admin" in data:
        if "password" in data["admin"]:
            config.admin.password = data["admin"]["password"]


def get_config() -> Config:
    """Get the current configuration. Loads if not already loaded."""
    global _config
    if _config is None:
        return load_config()
    return _config


def reset_config() -> None:
    """Reset configuration (for testing)."""
    global _config
    _config = None
