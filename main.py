"""Main bot for Variety Friday."""
import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import pytz
import logging

import config
from data_manager import DataManager

# -------------------------
# Logging
# -------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------
# Bot setup
# -------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)
data = DataManager()

# -------------------------
# Helper functions
# -------------------------
def allowed(ctx: discord.Interaction) -> bool:
    """Check if user has allowed roles."""
    if not ctx.user.guild:
        return False
    user_roles = [role.name.lower() for role in ctx.user.roles]
    allowed_roles = [r.lower() for r in config.ALLOWED_ROLES]
    return any(role in allowed_roles for role in user_roles)

def get_guild(bot: commands.Bot) -> discord.Guild:
    return bot.get_guild(config.GUILD_ID)

# -------------------------
# Bot events
# -------------------------
@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    logger.info("------")
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} commands")
    except Exception as e:
        logger.error(f"Error syncing commands: {e}")

# -------------------------
# /help command
# -------------------------
@bot.tree.command(name="help", description="Show available commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="Variety Friday Commands", color=discord.Color.blue())
    for cmd in bot.tree.walk_commands():
        try:
            # Only show commands the user is allowed to use
            if cmd.default_permission or allowed(interaction):
                embed.add_field(name=f"/{cmd.name}", value=cmd.description, inline=False)
        except:
            continue
    await interaction.response.send_message(embed=embed, ephemeral=True)

# -------------------------
# /createevent
# -------------------------
@bot.tree.command(name="createevent", description="Create a new Variety Friday event")
async def createevent(interaction: discord.Interaction):
    guild = get_guild(bot)
    if not guild:
        await interaction.response.send_message("Guild not found.", ephemeral=True)
        return

    voice_channel = guild.get_channel(config.VOICE_CHANNEL_ID)
    if not voice_channel:
        await interaction.response.send_message("Voice channel not found.", ephemeral=True)
        return

    # Calculate start and end times
    tz = pytz.timezone(config.TIMEZONE)
    now = datetime.datetime.now(tz)
    start_time = now.replace(hour=config.EVENT_START_HOUR, minute=0, second=0, microsecond=0)
    if start_time < now:
        start_time += datetime.timedelta(days=1)
    end_time = start_time + datetime.timedelta(hours=config.EVENT_DURATION_HOURS)

    # Create Discord event
    event = await guild.create_scheduled_event(
        name=config.EVENT_NAME,
        start_time=start_time.astimezone(pytz.UTC),
        end_time=end_time.astimezone(pytz.UTC),
        description=config.EVENT_DESCRIPTION,
        privacy_level=discord.PrivacyLevel.guild_only,
        entity_type=discord.EntityType.voice,
        channel=voice_channel
    )

    data.last_event_id = event.id
    await interaction.response.send_message(f"Event created: {event.name}", ephemeral=True)

# -------------------------
# /register
# -------------------------
@bot.tree.command(name="register", description="Announce the event and allow people to register")
async def register(interaction: discord.Interaction):
    guild = get_guild(bot)
    if not guild or not data.last_event_id:
        await interaction.response.send_message("No event exists. Please create one first.", ephemeral=True)
        return

    event = await guild.fetch_scheduled_event(data.last_event_id)
    if not event:
        await interaction.response.send_message("Event not found.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"{config.EVENT_NAME} is coming!",
        description=f"React below if you're attending!\n[event link 🗓️]({event.url})\nDon't forget to add your game suggestions using /addgame so we can vote later!",
        color=discord.Color.green()
    )

    msg = await interaction.channel.send("@everyone", embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")

    data.reminder_message_id = msg.id
    await interaction.response.send_message("Registration message sent!", ephemeral=True)

# -------------------------
# /reminder
# -------------------------
@bot.tree.command(name="reminder", description="Send a reminder about the event")
async def reminder(interaction: discord.Interaction):
    guild = get_guild(bot)
    if not guild or not data.last_event_id:
        await interaction.response.send_message("No event exists. Please create one first.", ephemeral=True)
        return

    event = await guild.fetch_scheduled_event(data.last_event_id)
    if not event:
        await interaction.response.send_message("Event not found.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"{config.EVENT_NAME} Reminder!",
        description=f"React below if you're attending!\n[event link 🗓️]({event.url})",
        color=discord.Color.gold()
    )

    msg = await interaction.channel.send("@everyone", embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    data.reminder_message_id = msg.id
    await interaction.response.send_message("Reminder sent!", ephemeral=True)

# -------------------------
# Games commands
# -------------------------
@bot.tree.command(name="addgame", description="Add a game to vote on")
async def addgame(interaction: discord.Interaction, name: str):
    if data.addgame(name):
        games_list = ", ".join(data.games)
        await interaction.response.send_message(f"Game added: {name}\nCurrent games: {games_list}", ephemeral=True)
    else:
        await interaction.response.send_message("Cannot add more than 10 games or game already exists.", ephemeral=True)

@bot.tree.command(name="removegame", description="Remove a game (roles only)")
async def removegame(interaction: discord.Interaction, name: str):
    if not allowed(interaction):
        await interaction.response.send_message("You don't have permission to remove games.", ephemeral=True)
        return
    if data.removegame(name):
        await interaction.response.send_message(f"Removed game: {name}", ephemeral=True)
    else:
        await interaction.response.send_message("Game not found.", ephemeral=True)

@bot.tree.command(name="listgames", description="List all current games")
async def listgames(interaction: discord.Interaction):
    if not data.games:
        await interaction.response.send_message("No games added yet.", ephemeral=True)
        return
    await interaction.response.send_message("Current games:\n" + "\n".join(f"{i+1}. {g}" for i, g in enumerate(data.games)), ephemeral=True)

@bot.tree.command(name="resetgames", description="Reset all games (roles only)")
async def resetgames(interaction: discord.Interaction):
    if not allowed(interaction):
        await interaction.response.send_message("You don't have permission to reset games.", ephemeral=True)
        return
    data.resetgames()
    await interaction.response.send_message("All games have been reset.", ephemeral=True)

# -------------------------
# Participants tracking
# -------------------------
@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    if reaction.message.id in [data.reminder_message_id]:
        if str(reaction.emoji) == "✅":
            data.add_yes_participant(user.id)
            try:
                await user.send(f"Thanks for registering for {config.EVENT_NAME}! See you there!")
            except:
                pass
        elif str(reaction.emoji) == "❌":
            data.add_no_participant(user.id)

@bot.event
async def on_reaction_remove(reaction, user):
    if user.bot:
        return
    if reaction.message.id in [data.reminder_message_id]:
        if str(reaction.emoji) == "✅":
            data.remove_yes_participant(user.id)
        elif str(reaction.emoji) == "❌":
            data.remove_no_participant(user.id)

@bot.tree.command(name="participants", description="Show who is attending")
async def participants(interaction: discord.Interaction):
    yes_users = [f"<@{uid}>" for uid in data.yes_participants]
    no_users = [f"<@{uid}>" for uid in data.no_participants]
    embed = discord.Embed(title="Event Participants", color=discord.Color.blue())
    embed.add_field(name="✅ Yes", value="\n".join(yes_users) or "None", inline=False)
    embed.add_field(name="❌ No", value="\n".join(no_users) or "None", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# -------------------------
# Voting commands (roles only)
# -------------------------
@bot.tree.command(name="startvote", description="Start voting on games (roles only)")
async def startvote(interaction: discord.Interaction):
    if not allowed(interaction):
        await interaction.response.send_message("You don't have permission to start voting.", ephemeral=True)
        return
    if not data.games:
        await interaction.response.send_message("No games to vote on.", ephemeral=True)
        return

    description = "\n".join(f"{i+1}\u20E3 {g}" for i, g in enumerate(data.games))
    embed = discord.Embed(title="Game Voting!", description=description, color=discord.Color.purple())
    msg = await interaction.channel.send(embed=embed)

    for i in range(len(data.games)):
        await msg.add_reaction(f"{i+1}\u20E3")  # 1️⃣ 2️⃣ 3️⃣ etc

    data.vote_message_id = msg.id
    await interaction.response.send_message("Voting started!", ephemeral=True)

@bot.tree.command(name="endvote", description="End voting and announce winner (roles only)")
async def endvote(interaction: discord.Interaction):
    if not allowed(interaction):
        await interaction.response.send_message("You don't have permission to end voting.", ephemeral=True)
        return
    if not data.vote_message_id:
        await interaction.response.send_message("No active voting message.", ephemeral=True)
        return

    channel = interaction.channel
    try:
        msg = await channel.fetch_message(data.vote_message_id)
    except:
        await interaction.response.send_message("Vote message not found.", ephemeral=True)
        return

    # Count reactions
    vote_counts = {}
    for i, game in enumerate(data.games):
        emoji = f"{i+1}\u20E3"
        reaction = discord.utils.get(msg.reactions, emoji=emoji)
        if reaction:
            vote_counts[game] = reaction.count - 1  # subtract bot's own reaction
        else:
            vote_counts[game] = 0

    # Determine winner
    if vote_counts:
        max_votes = max(vote_counts.values())
        winners = [g for g, v in vote_counts.items() if v == max_votes]
        winner_text = ", ".join(winners)
    else:
        winner_text = "No votes cast."

    await interaction.channel.send(f"Voting ended! Winner(s): {winner_text}")
    data.vote_message_id = None

# -------------------------
# Start event command
# -------------------------
@bot.tree.command(name="startevent", description="Announce the start of the event")
async def startevent(interaction: discord.Interaction):
    if not allowed(interaction):
        await interaction.response.send_message("You don't have permission to start the event.", ephemeral=True)
        return

    yes_users = [f"<@{uid}>" for uid in data.yes_participants]
    announce_msg = await interaction.channel.send(f"@everyone {config.EVENT_NAME} is starting!")
    for uid in data.yes_participants:
        user = await bot.fetch_user(uid)
        if user:
            try:
                await user.send(f"{config.EVENT_NAME} is starting now! See you there!")
            except:
                pass

    await interaction.response.send_message("Event started announcements sent!", ephemeral=True)

# -------------------------
# Run bot
# -------------------------
bot.run(config.TOKEN)
