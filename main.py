"""Main bot file for Variety Friday Discord Bot."""
import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.enums import EventType
import asyncio
import logging
from datetime import datetime, timedelta
import pytz

import config
from data_manager import DataManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.reactions = True
intents.messages = True

bot = commands.Bot(command_prefix="/", intents=intents)
tree = bot.tree
data = DataManager()

# -------------------------
# Helpers
# -------------------------
def has_allowed_role(interaction: discord.Interaction):
    member = interaction.user
    return any(role.name.lower() in [r.lower() for r in config.ALLOWED_ROLES] for role in member.roles)

def get_number_emoji(index: int):
    emojis = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    return emojis[index]

# -------------------------
# Event Commands
# -------------------------
@tree.command(name="createevent", description="Create the Variety Friday event")
async def createevent(interaction: discord.Interaction):
    guild = bot.get_guild(config.GUILD_ID)
    start_time = datetime.now(pytz.timezone(config.TIMEZONE)) + timedelta(days=0)
    end_time = start_time + timedelta(hours=config.EVENT_DURATION_HOURS)
    
    event = await guild.create_scheduled_event(
        name=config.EVENT_NAME,
        description=config.EVENT_DESCRIPTION,
        start_time=start_time,
        end_time=end_time,
        privacy_level=discord.PrivacyLevel.guild_only,
        entity_type=discord.EntityType.voice,
        channel_id=config.VOICE_CHANNEL_ID
    )
    data.last_event_id = event.id
    await interaction.response.send_message(f"Event created: {event.name}", ephemeral=True)

@tree.command(name="register", description="Announce the event and allow users to RSVP")
async def register(interaction: discord.Interaction):
    if not data.last_event_id:
        await interaction.response.send_message("No event exists yet! Create one first with /createevent.", ephemeral=True)
        return
    
    guild = bot.get_guild(config.GUILD_ID)
    event = await guild.fetch_scheduled_event(data.last_event_id)
    
    embed = discord.Embed(
        title=f"{config.EVENT_NAME} is coming!",
        description=f"Event link: [Click here 🗓️]({event.url})\n\nReact below if you’re coming!\nDon't forget to add your game suggestions using /addgame so we can vote later!",
        color=discord.Color.green()
    )
    
    msg = await interaction.channel.send(content="@everyone", embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    
    data.reminder_message_id = msg.id
    await interaction.response.send_message("Register message sent!", ephemeral=True)

@tree.command(name="reminder", description="Send a reminder for the event")
async def reminder(interaction: discord.Interaction):
    if not data.last_event_id:
        await interaction.response.send_message("No event exists yet!", ephemeral=True)
        return
    
    guild = bot.get_guild(config.GUILD_ID)
    event = await guild.fetch_scheduled_event(data.last_event_id)
    
    embed = discord.Embed(
        title=f"Reminder: {config.EVENT_NAME}",
        description=f"Event link: [Click here 🗓️]({event.url})\n\nReact below if you’re coming!",
        color=discord.Color.orange()
    )
    msg = await interaction.channel.send(content="@everyone", embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    
    data.reminder_message_id = msg.id
    await interaction.response.send_message("Reminder sent!", ephemeral=True)

@tree.command(name="startevent", description="Announce that the event is starting")
async def startevent(interaction: discord.Interaction):
    if not data.last_event_id:
        await interaction.response.send_message("No event exists yet!", ephemeral=True)
        return
    
    guild = bot.get_guild(config.GUILD_ID)
    event = await guild.fetch_scheduled_event(data.last_event_id)
    
    msg = await interaction.channel.send(f"@everyone {config.EVENT_NAME} is starting now!")
    
    for user_id in data.yes_participants:
        user = guild.get_member(user_id)
        if user:
            try:
                await user.send(f"Hey! {config.EVENT_NAME} is starting. See you there! {event.url}")
            except:
                pass
    
    await interaction.response.send_message("Event start announced!", ephemeral=True)

# -------------------------
# Game Commands
# -------------------------
@tree.command(name="addgame", description="Add a game to vote on")
async def addgame(interaction: discord.Interaction, game: str):
    if len(data.games) >= config.MAX_VOTING_OPTIONS:
        await interaction.response.send_message("Cannot add more than 10 games.", ephemeral=True)
        return
    if data.addgame(game):
        await interaction.response.send_message(f"Game added! Current games: {', '.join(data.games)}", ephemeral=True)
    else:
        await interaction.response.send_message("Game already exists or limit reached.", ephemeral=True)

@tree.command(name="listgames", description="List all current games")
async def listgames(interaction: discord.Interaction):
    if not data.games:
        await interaction.response.send_message("No games added yet.", ephemeral=True)
        return
    await interaction.response.send_message(f"Current games: {', '.join(data.games)}", ephemeral=True)

@tree.command(name="removegame", description="Remove a game (admin only)")
async def removegame(interaction: discord.Interaction, game: str):
    if not has_allowed_role(interaction):
        await interaction.response.send_message("You don't have permission to remove games.", ephemeral=True)
        return
    if data.removegame(game):
        await interaction.response.send_message(f"Game removed! Current games: {', '.join(data.games)}", ephemeral=True)
    else:
        await interaction.response.send_message("Game not found.", ephemeral=True)

@tree.command(name="resetgames", description="Reset all games (admin only)")
async def resetgames(interaction: discord.Interaction):
    if not has_allowed_role(interaction):
        await interaction.response.send_message("You don't have permission to reset games.", ephemeral=True)
        return
    data.resetgames()
    await interaction.response.send_message("All games reset.", ephemeral=True)

# -------------------------
# Voting Commands
# -------------------------
@tree.command(name="startvote", description="Start voting on games (admin only)")
async def startvote(interaction: discord.Interaction):
    if not has_allowed_role(interaction):
        await interaction.response.send_message("You don't have permission to start a vote.", ephemeral=True)
        return
    if not data.games:
        await interaction.response.send_message("No games added to vote on.", ephemeral=True)
        return
    
    desc = "\n".join([f"{get_number_emoji(i)} {g}" for i, g in enumerate(data.games)])
    embed = discord.Embed(title="Vote for the game!", description=desc, color=discord.Color.blurple())
    msg = await interaction.channel.send(embed=embed)
    
    for i in range(len(data.games)):
        await msg.add_reaction(get_number_emoji(i))
    
    data.vote_message_id = msg.id
    await interaction.response.send_message("Vote started!", ephemeral=True)

@tree.command(name="endvote", description="End voting and announce winner (admin only)")
async def endvote(interaction: discord.Interaction):
    if not has_allowed_role(interaction):
        await interaction.response.send_message("You don't have permission to end a vote.", ephemeral=True)
        return
    if not data.vote_message_id:
        await interaction.response.send_message("No vote in progress.", ephemeral=True)
        return
    
    channel = interaction.channel
    try:
        msg = await channel.fetch_message(data.vote_message_id)
    except:
        await interaction.response.send_message("Could not fetch vote message.", ephemeral=True)
        return
    
    counts = {g: 0 for g in data.games}
    for reaction in msg.reactions:
        if reaction.emoji in ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]:
            index = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"].index(reaction.emoji)
            if index < len(data.games):
                counts[data.games[index]] = reaction.count - 1  # minus bot reaction
    
    winner = max(counts, key=counts.get)
    await channel.send(f"Thanks for voting! 🏆 {winner} is the winner!")
    data.vote_message_id = None

# -------------------------
# Participants Command
# -------------------------
@tree.command(name="participants", description="See who is attending")
async def participants(interaction: discord.Interaction):
    if not data.yes_participants:
        await interaction.response.send_message("No participants yet.", ephemeral=True)
        return
    guild = bot.get_guild(config.GUILD_ID)
    mentions = [guild.get_member(uid).mention for uid in data.yes_participants if guild.get_member(uid)]
    await interaction.response.send_message(f"Attending participants:\n{', '.join(mentions)}", ephemeral=True)

# -------------------------
# Help Command
# -------------------------
@tree.command(name="help", description="Show available commands")
async def help(interaction: discord.Interaction):
    commands_list = [
        ("createevent", "Create the Variety Friday event"),
        ("register", "Announce the event and allow users to RSVP"),
        ("reminder", "Send a reminder for the event"),
        ("startevent", "Announce that the event is starting"),
        ("addgame", "Add a game to vote on"),
        ("listgames", "List all current games"),
        ("removegame", "Remove a game (admin only)"),
        ("resetgames", "Reset all games (admin only)"),
        ("startvote", "Start voting on games (admin only)"),
        ("endvote", "End voting and announce winner (admin only)"),
        ("participants", "See who is attending")
    ]
    
    member = interaction.user
    visible_commands = []
    for cmd, desc in commands_list:
        if "admin only" in desc.lower():
            if any(role.name.lower() in [r.lower() for r in config.ALLOWED_ROLES] for role in member.roles):
                visible_commands.append(f"/{cmd} - {desc}")
        else:
            visible_commands.append(f"/{cmd} - {desc}")
    
    embed = discord.Embed(title="Available Commands", description="\n".join(visible_commands), color=discord.Color.blue())
    await interaction.response.send_message(embed=embed, ephemeral=True)

# -------------------------
# Reaction Handling
# -------------------------
@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    if reaction.message.id not in [data.reminder_message_id, data.vote_message_id]:
        return
    
    if str(reaction.emoji) == "✅":
        data.add_yes_participant(user.id)
        try:
            await user.send(f"Thanks for registering for {config.EVENT_NAME}! See you there!")
        except:
            pass
    elif str(reaction.emoji) == "❌":
        data.add_no_participant(user.id)

@bot.event
async def on_ready():
    logger.info(f"Bot logged in as {bot.user}")
    await tree.sync()
    logger.info("Command tree synced")

bot.run(config.TOKEN)
