"""Main bot file for Variety Friday."""

import discord
from discord import app_commands, Interaction
from discord.ext import commands, tasks
from data_manager import DataManager
import config

# -------------------------
# Bot Setup
# -------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True  # Needed for privileged intents

bot = commands.Bot(command_prefix="/", intents=intents)
data_manager = DataManager()

# Emoji list for votes
VOTE_EMOJIS = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]

# -------------------------
# Helper Functions
# -------------------------
def has_allowed_role(interaction: Interaction) -> bool:
    return any(role.name.lower() in [r.lower() for r in config.ALLOWED_ROLES] 
               for role in interaction.user.roles)

async def send_dm(user: discord.User, message: str):
    try:
        await user.send(message)
    except:
        pass

def format_games_list():
    if not data_manager.games:
        return "No games added yet."
    return "\n".join(f"{i+1}. {g}" for i, g in enumerate(data_manager.games))

def format_participants():
    if not data_manager.yes_participants:
        return "No participants yet."
    return "\n".join(f"<@{uid}>" for uid in data_manager.yes_participants)

# -------------------------
# Commands
# -------------------------
@bot.tree.command(name="createevent", description="Create the Discord event.")
async def createevent(interaction: Interaction):
    guild = interaction.guild
    event = await guild.create_scheduled_event(
        name=config.EVENT_NAME,
        description=config.EVENT_DESCRIPTION,
        start_time=discord.utils.utcnow(),
        end_time=discord.utils.utcnow() + discord.timedelta(hours=config.EVENT_DURATION_HOURS),
        entity_type=discord.EntityType.voice,
        channel=discord.Object(id=config.VOICE_CHANNEL_ID),
    )
    data_manager.last_event_id = event.id
    await interaction.response.send_message(f"Event created: {event.name} (ID: {event.id})", ephemeral=True)

@bot.tree.command(name="register", description="Announce the event and register participants.")
async def register(interaction: Interaction):
    if not data_manager.last_event_id:
        await interaction.response.send_message("No event exists. Use /createevent first.", ephemeral=True)
        return

    guild = interaction.guild
    event = await guild.fetch_scheduled_event(data_manager.last_event_id)
    embed = discord.Embed(
        title=f"{config.EVENT_NAME} Registration",
        description=f"Event: {event.name}\nReact below if you're coming!\n{event.url}",
        color=discord.Color.green()
    )
    msg = await interaction.channel.send("@everyone", embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    data_manager.vote_message_id = msg.id
    await interaction.response.send_message("Registration message posted.", ephemeral=True)

@bot.tree.command(name="reminder", description="Send a reminder message for the event.")
async def reminder(interaction: Interaction):
    if not data_manager.last_event_id:
        await interaction.response.send_message("No event exists. Use /createevent first.", ephemeral=True)
        return

    guild = interaction.guild
    event = await guild.fetch_scheduled_event(data_manager.last_event_id)
    embed = discord.Embed(
        title=f"{config.EVENT_NAME} Reminder",
        description=f"Event: {event.name}\nReact below if you're coming!\n{event.url}",
        color=discord.Color.blue()
    )
    msg = await interaction.channel.send("@everyone", embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    data_manager.reminder_message_id = msg.id
    await interaction.response.send_message("Reminder message posted.", ephemeral=True)

@bot.tree.command(name="addgame", description="Add a game to vote on.")
async def addgame(interaction: Interaction, game_name: str):
    if len(data_manager.games) >= config.MAX_VOTING_OPTIONS:
        await interaction.response.send_message(f"Cannot add more than {config.MAX_VOTING_OPTIONS} games.", ephemeral=True)
        return
    if data_manager.add_game(game_name):
        await interaction.response.send_message(f"Game added: {game_name}\nCurrent games:\n{format_games_list()}", ephemeral=True)
    else:
        await interaction.response.send_message("Game already exists.", ephemeral=True)

@bot.tree.command(name="removegame", description="Remove a game (allowed roles only).")
async def removegame(interaction: Interaction, game_name: str):
    if not has_allowed_role(interaction):
        await interaction.response.send_message("You don't have permission to do this.", ephemeral=True)
        return
    if data_manager.remove_game(game_name):
        await interaction.response.send_message(f"Game removed: {game_name}\nCurrent games:\n{format_games_list()}", ephemeral=True)
    else:
        await interaction.response.send_message("Game not found.", ephemeral=True)

@bot.tree.command(name="resetgames", description="Reset all games (allowed roles only).")
async def resetgames(interaction: Interaction):
    if not has_allowed_role(interaction):
        await interaction.response.send_message("You don't have permission to do this.", ephemeral=True)
        return
    data_manager.clear_games()
    await interaction.response.send_message("All games cleared.", ephemeral=True)

@bot.tree.command(name="listgames", description="List all games.")
async def listgames(interaction: Interaction):
    await interaction.response.send_message(format_games_list(), ephemeral=True)

@bot.tree.command(name="participants", description="List participants who said yes.")
async def participants(interaction: Interaction):
    await interaction.response.send_message(format_participants(), ephemeral=True)

@bot.tree.command(name="startvote", description="Start a vote on games (allowed roles only).")
async def startvote(interaction: Interaction):
    if not has_allowed_role(interaction):
        await interaction.response.send_message("You don't have permission.", ephemeral=True)
        return
    if not data_manager.games:
        await interaction.response.send_message("No games to vote on.", ephemeral=True)
        return
    desc = "\n".join(f"{VOTE_EMOJIS[i]} {game}" for i, game in enumerate(data_manager.games))
    embed = discord.Embed(title="Vote for a game!", description=desc, color=discord.Color.purple())
    msg = await interaction.channel.send(embed=embed)
    for i in range(len(data_manager.games)):
        await msg.add_reaction(VOTE_EMOJIS[i])
    data_manager.vote_message_id = msg.id
    await interaction.response.send_message("Vote started.", ephemeral=True)

@bot.tree.command(name="endvote", description="End voting and announce the winner (allowed roles only).")
async def endvote(interaction: Interaction):
    if not has_allowed_role(interaction):
        await interaction.response.send_message("You don't have permission.", ephemeral=True)
        return
    if not data_manager.vote_message_id:
        await interaction.response.send_message("No active vote.", ephemeral=True)
        return
    channel = interaction.channel
    try:
        msg = await channel.fetch_message(data_manager.vote_message_id)
    except:
        await interaction.response.send_message("Vote message not found.", ephemeral=True)
        return

    counts = [0]*len(data_manager.games)
    for reaction in msg.reactions:
        if reaction.emoji in VOTE_EMOJIS:
            idx = VOTE_EMOJIS.index(reaction.emoji)
            counts[idx] = reaction.count - 1  # exclude bot's own reaction

    max_votes = max(counts)
    winners = [data_manager.games[i] for i, c in enumerate(counts) if c == max_votes]
    winner_text = ", ".join(winners)
    await interaction.channel.send(f"Thanks for voting! The winner is: **{winner_text}** 🏆")
    data_manager.vote_message_id = None

@bot.tree.command(name="startevent", description="Announce the event is starting and DM participants.")
async def startevent(interaction: Interaction):
    if not data_manager.last_event_id:
        await interaction.response.send_message("No event exists.", ephemeral=True)
        return
    guild = interaction.guild
    event = await guild.fetch_scheduled_event(data_manager.last_event_id)
    await interaction.channel.send(f"{config.EVENT_NAME} is starting now! @everyone")
    for uid in data_manager.yes_participants:
        user = guild.get_member(uid)
        if user:
            await send_dm(user, f"{config.EVENT_NAME} is starting! See you there!")

@bot.tree.command(name="help", description="Show available commands.")
async def help_command(interaction: Interaction):
    help_text = ""
    for cmd in bot.tree.walk_commands():
        # Skip commands if user cannot run (role restriction)
        if cmd.name in ["removegame", "resetgames", "startvote", "endvote"]:
            if not has_allowed_role(interaction):
                continue
        help_text += f"/{cmd.name} - {cmd.description}\n"
    await interaction.response.send_message(help_text or "No commands available.", ephemeral=True)

# -------------------------
# Reactions Handling
# -------------------------
@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return

    if payload.message_id not in [data_manager.vote_message_id, data_manager.reminder_message_id]:
        return

    if str(payload.emoji) == "✅":
        data_manager.add_yes_participant(payload.user_id)
        user = bot.get_user(payload.user_id)
        await send_dm(user, f"Thanks for registering for {config.EVENT_NAME}! See you there.")
    elif str(payload.emoji) == "❌":
        data_manager.add_no_participant(payload.user_id)

@bot.event
async def on_raw_reaction_remove(payload):
    if payload.user_id == bot.user.id:
        return
    if payload.message_id not in [data_manager.vote_message_id, data_manager.reminder_message_id]:
        return
    if str(payload.emoji) == "✅":
        data_manager.remove_yes_participant(payload.user_id)
    elif str(payload.emoji) == "❌":
        data_manager.remove_no_participant(payload.user_id)

# -------------------------
# Run Bot
# -------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

bot.run(config.TOKEN)
