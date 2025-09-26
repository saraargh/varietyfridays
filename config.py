"""Configuration settings for the Variety Friday Discord Bot."""
import os
from typing import List

# Bot token
TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise ValueError("TOKEN environment variable is required")

# Permissions
ALLOWED_ROLES: List[str] = ["server sorter outerer", "sazzles"]

# Discord settings
GUILD_ID = 987654321098765432  # <-- Replace with your real server ID
VOICE_CHANNEL_NAME = 1404143716234432714  # <-- Replace with your real voice channel ID

# Event settings
EVENT_NAME = "Variety Friday"
EVENT_DESCRIPTION = "Join us for Variety Friday! 🎮"
EVENT_DURATION_HOURS = 6
EVENT_START_HOUR = 21  # 9 PM UK time
TIMEZONE = "Europe/London"

# Limits
MAX_VOTING_OPTIONS = 10
