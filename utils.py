"""Utility functions for the Variety Friday Discord Bot."""
import discord
import datetime
import logging
from zoneinfo import ZoneInfo
from typing import Optional, List
from discord import EntityType, PrivacyLevel

import config

logger = logging.getLogger(__name__)

def is_allowed(interaction: discord.Interaction) -> bool:
    """Check if user has permission to use admin commands."""
    # Ensure we have a guild member, not just a user
    if not hasattr(interaction, 'guild') or not interaction.guild:
        return False
    
    # Get the member from the guild
    member = interaction.guild.get_member(interaction.user.id)
    if not member:
        return False
    
    # Check if user is an administrator
    if member.guild_permissions.administrator:
        return True
    
    # Check if user has required roles
    user_roles = [r.name.lower() for r in member.roles]
    return any(role.lower() in [r.lower() for r in config.ALLOWED_ROLES] for role in user_roles)

async def create_variety_event(guild: discord.Guild) -> Optional[discord.ScheduledEvent]:
    """Create a Variety Friday event."""
    try:
        # Find the voice channel
        voice_channel = discord.utils.get(guild.voice_channels, name=config.VOICE_CHANNEL_NAME)
        if not voice_channel:
            logger.error(f"Voice channel '{config.VOICE_CHANNEL_NAME}' not found")
            return None

        # Calculate next Friday at 9 PM UK time
        uk_tz = ZoneInfo(config.TIMEZONE)
        now_uk = datetime.datetime.now(uk_tz)

        # Calculate days until next Friday
        days_ahead = 4 - now_uk.weekday()  # Friday is weekday 4
        if days_ahead <= 0:
            # If it's Friday and before 9 PM, schedule for today
            if now_uk.weekday() == 4 and now_uk.hour < config.EVENT_START_HOUR:
                days_ahead = 0
            else:
                # Otherwise, schedule for next Friday
                days_ahead += 7

        # Set the event time
        friday_uk = now_uk + datetime.timedelta(days=days_ahead)
        start_time_uk = friday_uk.replace(
            hour=config.EVENT_START_HOUR, 
            minute=0, 
            second=0, 
            microsecond=0
        )
        end_time_uk = start_time_uk + datetime.timedelta(hours=config.EVENT_DURATION_HOURS)

        # Convert to UTC
        start_time_utc = start_time_uk.astimezone(datetime.timezone.utc)
        end_time_utc = end_time_uk.astimezone(datetime.timezone.utc)

        # Create the event
        event = await guild.create_scheduled_event(
            name=config.EVENT_NAME,
            description=config.EVENT_DESCRIPTION,
            start_time=start_time_utc,
            end_time=end_time_utc,
            privacy_level=PrivacyLevel.guild_only,
            entity_type=EntityType.voice,
            channel=voice_channel
        )
        
        logger.info(f"Created event: {event.name} at {start_time_uk}")
        return event
        
    except Exception as e:
        logger.error(f"Failed to create event: {e}")
        return None

async def delete_event_safely(guild: discord.Guild, event_id: Optional[int]) -> bool:
    """Safely delete an event by ID."""
    if not event_id:
        return True
    
    try:
        event = guild.get_scheduled_event(event_id)
        if event:
            await event.delete()
            logger.info(f"Deleted event: {event.name}")
        return True
    except Exception as e:
        logger.warning(f"Could not delete event {event_id}: {e}")
        return False

def get_voting_emojis() -> List[str]:
    """Get the list of voting emojis."""
    return ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

async def safe_send_dm(member: discord.Member, message: str) -> bool:
    """Safely send a DM to a member."""
    try:
        await member.send(message)
        return True
    except discord.HTTPException:
        logger.warning(f"Could not send DM to {member.display_name}")
        return False
    except Exception as e:
        logger.error(f"Error sending DM to {member.display_name}: {e}")
        return False

def create_games_embed(games: List[str], title: str = "🎮 Variety Friday Suggestions") -> discord.Embed:
    """Create an embed for displaying games."""
    if not games:
        return discord.Embed(
            title=title,
            description="📭 No games suggested yet.",
            color=discord.Color.blue()
        )
    
    description = "\n".join(f"- {game}" for game in games)
    return discord.Embed(
        title=title,
        description=description,
        color=discord.Color.blue()
    )

def create_participants_embed(yes_participants: List[str], no_participants: List[str]) -> discord.Embed:
    """Create an embed for displaying participants."""
    embed = discord.Embed(title="📋 Variety Friday Participants", color=discord.Color.teal())
    
    yes_list = "\n".join(yes_participants) if yes_participants else "Nobody yet"
    no_list = "\n".join(no_participants) if no_participants else "Nobody yet"
    
    embed.add_field(name="✅ Attending", value=yes_list, inline=True)
    embed.add_field(name="❌ Not Attending", value=no_list, inline=True)
    
    return embed
