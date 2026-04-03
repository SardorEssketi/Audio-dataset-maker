"""
User configuration model.
Stores per-user pipeline settings.
Sensitive values (tokens) are encrypted.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, func
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.database import Base


class UserConfig(Base):
    """
    User configuration model.
    Stores key-value pairs for user settings.
    Tokens and other sensitive values are encrypted before storage.
    """
    __tablename__ = "user_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    config_key = Column(String(100), nullable=False)
    config_value = Column(Text, nullable=True)  # JSON for nested structures
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<UserConfig(id={self.id}, user_id={self.user_id}, key='{self.config_key}')>"