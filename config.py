"""Configuration settings for the Variety Friday Discord Bot."""
import os
from typing import List

# ------------------------
# Bot Token
# ------------------------
TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise ValueError("TOKEN environment variable is required")

# ------------------------
# Guild / Channel Settings
# ------------------------
GUILD_ID = 1398508733709029428  # Your server ID
VOICE_CHANNEL_ID = 1404143716234432714  # Your voice channel ID

# ------------------------
# Permissions
# ------------------------
ALLOWED_ROLES: List[str] = ["server sorter outerer", "sazzles"]

# ------------------------
# Event Settings
# ------------------------
EVENT_NAME = "Variety Friday"
EVENT_DESCRIPTION = "Join us for Variety Friday! 🎮"
EVENT_DURATION_HOURS = 6
EVENT_START_HOUR = 21  # 9 PM UK time
TIMEZONE = "Europe/London"

# ------------------------
# Voting / Games
# ------------------------
MAX_VOTING_OPTIONS = 10
