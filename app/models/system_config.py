"""
SystemConfig model — single key/value config store.

Used for:
- test_mobile_override_enabled:  "true" | "false"
- test_mobile_number:            "+91XXXXXXXXXX"
- underwriting_mode:             "AUTO" | "MANUAL"  (used in 8.6.4)
"""

from sqlalchemy import Column, Integer, String
from app.db.base import Base


class SystemConfig(Base):
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False, index=True)
    value = Column(String, nullable=True)
