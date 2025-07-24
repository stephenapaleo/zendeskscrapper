"""Configuration management for Zendesk scraper."""
import os
import yaml
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv


class Config:
    """Configuration manager that loads settings from environment variables and YAML files."""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize configuration manager.
        
        Args:
            config_path: Path to the YAML configuration file
        """
        self.config_path = Path(config_path)
        self._config = {}
        self._load_config()
    
    def _load_config(self):
        """Load configuration from environment variables and YAML file."""
        # Load environment variables from .env file
        load_dotenv()
        
        # Load YAML configuration
        if self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                yaml_content = f.read()
                # Replace environment variables in YAML content
                yaml_content = self._substitute_env_vars(yaml_content)
                self._config = yaml.safe_load(yaml_content)
        else:
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
    
    def _substitute_env_vars(self, content: str) -> str:
        """Substitute environment variables in YAML content.
        
        Args:
            content: YAML content with ${VAR} placeholders
            
        Returns:
            Content with environment variables substituted
        """
        import re
        
        def replace_var(match):
            var_name = match.group(1)
            return os.getenv(var_name, match.group(0))
        
        return re.sub(r'\$\{([^}]+)\}', replace_var, content)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key.
        
        Args:
            key: Configuration key (supports dot notation, e.g., 'zendesk.subdomain')
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_zendesk_config(self) -> Dict[str, str]:
        """Get Zendesk API configuration.
        
        Returns:
            Dictionary with Zendesk API settings
        """
        subdomain = self.get('zendesk.subdomain')
        email = self.get('zendesk.email')
        api_token = self.get('zendesk.api_token')
        
        if not all([subdomain, email, api_token]):
            missing = []
            if not subdomain: missing.append('ZENDESK_SUBDOMAIN')
            if not email: missing.append('ZENDESK_EMAIL')  
            if not api_token: missing.append('ZENDESK_API_TOKEN')
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        
        return {
            'subdomain': subdomain,
            'email': email,
            'api_token': api_token,
            'base_url': f"https://{subdomain}.zendesk.com/api/v2"
        }
    
    def get_rate_limit_config(self) -> Dict[str, int]:
        """Get rate limiting configuration.
        
        Returns:
            Dictionary with rate limiting settings
        """
        return {
            'requests_per_minute': self.get('rate_limiting.requests_per_minute', 700),
            'retry_attempts': self.get('rate_limiting.retry_attempts', 3),
            'backoff_factor': self.get('rate_limiting.backoff_factor', 2)
        }
    
    def get_output_config(self) -> Dict[str, Any]:
        """Get output configuration.
        
        Returns:
            Dictionary with output settings
        """
        return {
            'base_directory': self.get('output.base_directory', 'output'),
            'date_format': self.get('output.date_format', '%Y-%m-%d %H:%M:%S'),
            'categories': self.get('categories', {})
        }
    
    def get_category_config(self, category: str) -> Dict[str, Any]:
        """Get configuration for a specific category.
        
        Args:
            category: Category name (e.g., 'tickets', 'users')
            
        Returns:
            Dictionary with category configuration
        """
        return self.get(f'categories.{category}', {})


# Global configuration instance
config = Config() 