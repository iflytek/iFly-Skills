"""Configuration for the package-owned contract adapter."""
import os
from dataclasses import dataclass, field

@dataclass
class Config:
    app_id: str = field(default_factory=lambda: os.environ.get("IFLY_APP_ID", ""))
    api_key: str = field(default_factory=lambda: os.environ.get("IFLY_API_KEY", ""))
    api_secret: str = field(default_factory=lambda: os.environ.get("IFLY_API_SECRET", ""))
    max_input_chars: int = 4000
    max_pdf_pages: int = 8
    timeout: int = 45

    def require_credentials(self):
        if not all(value.strip() for value in (self.app_id, self.api_key, self.api_secret)):
            raise ValueError("IFLY_APP_ID, IFLY_API_KEY and IFLY_API_SECRET are required")
