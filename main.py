# main.py — Part 1
import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.utils import get
from zoneinfo import ZoneInfo
import datetime
from data_manager import DataManager
from config import TOKEN, GUILD_ID, VOICE_CHANNEL_ID, ALLOWED_ROLES, MAX_VOTING_OPTIONS, EVENT_NAME, EVENT_DESCRIPTION, EVENT_DURATION_HOURS

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="/", intents=intents)
data_manager = DataManager()

GUILD = None

@bot.event
async def on_ready():
    global GUILD
    GUILD = bot.get_guild(GUILD_ID)
    print(f"Bot is ready. Logged in as {bot.user} in guild {GUILD.name}")
# main.py — Part 2
# -------------------------
# Game commands
# -------------------------
@bot.tree.command(name="addgame", description="Add a game suggestion")
@app_commands.describe(game="Name of the game to add")
async def addgame(interaction: discord.Interaction, game: str):
    if not is_allowed(interaction.user):
        await interaction.response.send_message("You cannot use this command.", ephemeral=True)
        return

    if data_manager.addgame(game):
        await interaction.response.send_message(f"Game '{game}' added!", ephemeral=True)
    else:
        await interaction.response.send_message("Game already exists or max games reached.", ephemeral=True)

@bot.tree.command(name="removegame", description="Remove a game suggestion")
@app_commands.describe(game="Name of the game to remove")
async def removegame(interaction: discord.Interaction, game: str):
    if not is_allowed(interaction.user):
        await interaction.response.send_message("You cannot use this command.", ephemeral=True)
        return

    if data_manager.removegame(game):
        await interaction.response.send_message(f"Game '{game}' removed!", ephemeral=True)
    else:
        await interaction.response.send_message("Game not found.", ephemeral=True)

@bot.tree.command(name="listgames", description="List all suggested games")
async def listgames(interaction: discord.Interaction):
    games = data_manager.games
    if games:
        await interaction.response.send_message("\n".join(f"{i+1}. {g}" for i, g in enumerate(games)), ephemeral=True)
    else:
        await interaction.response.send_message("No games suggested yet.", ephemeral=True)

@bot.tree.command(name="resetgames", description="Clear all game suggestions")
async def resetgames(interaction: discord.Interaction):
    if not is_allowed(interaction.user):
        await interaction.response.send_message("You cannot use this command.", ephemeral=True)
        return

    data_manager.resetgames()
    await interaction.response.send_message("All games cleared.", ephemeral=True)

# -------------------------
# Vote commands
# -------------------------
@bot.tree.command(name="startvote", description="Start voting on games")
async def startvote(interaction: discord.Interaction):
    if not is_allowed(interaction.user):
        await interaction.response.send_message("You cannot use this command.", ephemeral=True)
        return

    games = data_manager.games[:MAX_VOTING_OPTIONS]
    if not games:
        await interaction.response.send_message("No games to vote on.", ephemeral=True)
        return

    description = "\n".join(f"{i+1}. {game}" for i, game in enumerate(games))
    embed = create_embed("Vote for your game!", description)
    msg = await interaction.channel.send(embed=embed)
    emojis = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"][:len(games)]
    for e in emojis:
        await msg.add_reaction(e)
    data_manager.vote_message_id = msg.id
    await interaction.response.send_message("Vote started!", ephemeral=True)

@bot.tree.command(name="endvote", description="End voting")
async def endvote(interaction: discord.Interaction):
    if not is_allowed(interaction.user):
        await interaction.response.send_message("You cannot use this command.", ephemeral=True)
        return

    data_manager.vote_message_id = None
    await interaction.response.send_message("Voting ended.", ephemeral=True)

# -------------------------
# Participants
# -------------------------
@bot.tree.command(name="participants", description="List participants who responded")
async def participants(interaction: discord.Interaction):
    yes = data_manager.yes_participants
    no = data_manager.no_participants
    await interaction.response.send_message(f"✅ Yes: {len(yes)}\n❌ No: {len(no)}", ephemeral=True)

# -------------------------
# Help command
# -------------------------
@bot.tree.command(name="help", description="Show all available commands")
async def help(interaction: discord.Interaction):
    commands_list = []
    for cmd in bot.tree.walk_commands():
        if not cmd.hidden:
            if cmd.guild_ids is None or is_allowed(interaction.user):
                commands_list.append(f"/{cmd.name} — {cmd.description}")
    await interaction.response.send_message("\n".join(commands_list), ephemeral=True)

# -------------------------
# Start bot
# -------------------------
bot.run(TOKEN)
