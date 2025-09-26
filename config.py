"""Configuration settings for the Variety Friday Discord Bot."""
import os
from typing import List

# Bot configuration
TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise ValueError("TOKEN environment variable is required")

# Permissions
ALLOWED_ROLES: List[str] = ["server sorter outerer", "sazzles"]

# Discord settings
VOICE_CHANNEL_NAME = "gamechat1"

# Event settings
EVENT_NAME = "Variety Friday"
EVENT_DESCRIPTION = "Join us for Variety Friday! 🎮"
EVENT_DURATION_HOURS = 6
EVENT_START_HOUR = 21  # 9 PM UK time
TIMEZONE = "Europe/London"

# Limits
MAX_VOTING_OPTIONS = 10
