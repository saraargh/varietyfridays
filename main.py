"""Main bot file for Variety Friday Discord Bot."""

import discord
from discord import app_commands
from discord.ext import commands, tasks
from data_manager import DataManager
import config
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.reactions = True

bot = commands.Bot(command_prefix="/", intents=intents)
data = DataManager()

NUMBER_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

# Helper functions
def is_allowed_role(interaction: discord.Interaction):
    return any(role.name.lower() in [r.lower() for r in config.ALLOWED_ROLES] for role in interaction.user.roles)

def get_vote_message():
    if data.vote_message_id and bot.get_channel(config.VOICE_CHANNEL_NAME):
        return bot.get_channel(config.VOICE_CHANNEL_NAME).fetch_message(data.vote_message_id)
    return None

# ---------- COMMANDS ----------

@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} commands.")
    except Exception as e:
        logger.error(f"Error syncing commands: {e}")

# CREATE EVENT
@bot.tree.command(name="createevent", description="Create the Variety Friday event")
async def createevent(interaction: discord.Interaction):
    guild = bot.get_guild(config.GUILD_ID)
    start_time = discord.utils.utcnow().replace(hour=config.EVENT_START_HOUR, minute=0, second=0)
    event = await guild.create_scheduled_event(
        name=config.EVENT_NAME,
        description=config.EVENT_DESCRIPTION,
        start_time=start_time,
        privacy_level=discord.PrivacyLevel.guild_only,
        entity_type=discord.EntityType.voice,
        channel=bot.get_channel(config.VOICE_CHANNEL_ID)
    )
    data.last_event_id = event.id
    await interaction.response.send_message(f"Event created: {event.name} ({event.url})", ephemeral=True)

# REGISTER
@bot.tree.command(name="register", description="Announce registration for the event")
async def register(interaction: discord.Interaction):
    if not data.last_event_id:
        await interaction.response.send_message("No event exists. Please create an event first.", ephemeral=True)
        return
    guild = bot.get_guild(config.GUILD_ID)
    event = await guild.fetch_scheduled_event(data.last_event_id)
    msg = await interaction.channel.send(
        f"@everyone **Variety Friday is coming!**\nReact below if you're coming!\nEvent link: {event.url}"
    )
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    data.reminder_message_id = msg.id
    await interaction.response.send_message("Registration message sent.", ephemeral=True)

# REMINDER
@bot.tree.command(name="reminder", description="Send a reminder for the event")
async def reminder(interaction: discord.Interaction):
    if not data.last_event_id:
        await interaction.response.send_message("No event exists. Please create an event first.", ephemeral=True)
        return
    guild = bot.get_guild(config.GUILD_ID)
    event = await guild.fetch_scheduled_event(data.last_event_id)
    msg = await interaction.channel.send(
        f"@everyone **Reminder: Variety Friday is happening soon!**\nReact below if you're coming!\nEvent link: {event.url}"
    )
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    data.reminder_message_id = msg.id
    await interaction.response.send_message("Reminder sent.", ephemeral=True)

# ADD GAME
@bot.tree.command(name="addgame", description="Add a game to vote on")
@app_commands.describe(game="The game you want to add")
async def addgame(interaction: discord.Interaction, game: str):
    if len(data.games) >= 10:
        await interaction.response.send_message("You cannot add more than 10 games.", ephemeral=True)
        return
    added = data.add_game(game)
    if added:
        games_list = "\n".join(f"{i+1}. {g}" for i, g in enumerate(data.games))
        await interaction.response.send_message(f"Game added!\nCurrent games:\n{games_list}")
    else:
        await interaction.response.send_message("That game is already in the list.", ephemeral=True)

# REMOVE GAME
@bot.tree.command(name="removegame", description="Remove a game from the list")
@app_commands.describe(game="The game to remove")
async def removegame(interaction: discord.Interaction, game: str):
    if not is_allowed_role(interaction):
        await interaction.response.send_message("You do not have permission to do this.", ephemeral=True)
        return
    removed = data.remove_game(game)
    if removed:
        await interaction.response.send_message(f"{game} removed.")
    else:
        await interaction.response.send_message(f"{game} not found.", ephemeral=True)

# LIST GAMES
@bot.tree.command(name="listgames", description="List all current games")
async def listgames(interaction: discord.Interaction):
    if not data.games:
        await interaction.response.send_message("No games added yet.", ephemeral=True)
        return
    games_list = "\n".join(f"{i+1}. {g}" for i, g in enumerate(data.games))
    await interaction.response.send_message(f"Current games:\n{games_list}")

# RESET GAMES
@bot.tree.command(name="resetgames", description="Reset all games")
async def resetgames(interaction: discord.Interaction):
    if not is_allowed_role(interaction):
        await interaction.response.send_message("You do not have permission to do this.", ephemeral=True)
        return
    data.clear_games()
    await interaction.response.send_message("All games have been reset.")

# PARTICIPANTS
@bot.tree.command(name="participants", description="See who is attending")
async def participants(interaction: discord.Interaction):
    if not data.yes_participants:
        await interaction.response.send_message("No one has registered yet.")
        return
    members = []
    for uid in data.yes_participants:
        member = interaction.guild.get_member(uid)
        if member:
            members.append(member.display_name)
    await interaction.response.send_message("Participants:\n" + "\n".join(members))

# START VOTE
@bot.tree.command(name="startvote", description="Start voting for games")
async def startvote(interaction: discord.Interaction):
    if not is_allowed_role(interaction):
        await interaction.response.send_message("You do not have permission.", ephemeral=True)
        return
    if not data.games:
        await interaction.response.send_message("No games to vote for.", ephemeral=True)
        return
    vote_msg = await interaction.channel.send(
        "**Vote for your favorite game!**\nReact with the number corresponding to your choice."
    )
    data.vote_message_id = vote_msg.id
    for i in range(len(data.games)):
        await vote_msg.add_reaction(NUMBER_EMOJIS[i])
    await interaction.response.send_message("Voting started.", ephemeral=True)

# END VOTE
@bot.tree.command(name="endvote", description="End voting and show winner")
async def endvote(interaction: discord.Interaction):
    if not is_allowed_role(interaction):
        await interaction.response.send_message("You do not have permission.", ephemeral=True)
        return
    if not data.vote_message_id:
        await interaction.response.send_message("No vote in progress.", ephemeral=True)
        return
    channel = interaction.channel
    vote_msg = await channel.fetch_message(data.vote_message_id)
    counts = {i: 0 for i in range(len(data.games))}
    for reaction in vote_msg.reactions:
        if reaction.emoji in NUMBER_EMOJIS:
            index = NUMBER_EMOJIS.index(reaction.emoji)
            counts[index] = reaction.count - 1  # remove bot reaction
    if counts:
        max_votes = max(counts.values())
        winners = [data.games[i] for i, v in counts.items() if v == max_votes]
        winner_text = winners[0] if winners else "No winner"
        embed = discord.Embed(
            title="Voting ended!",
            description=f"Thanks for voting! **{winner_text}** is the winner! 🏆",
            color=discord.Color.green()
        )
        await channel.send(embed=embed)
    data.vote_message_id = None
    await interaction.response.send_message("Vote ended.", ephemeral=True)

# START EVENT
@bot.tree.command(name="startevent", description="Announce the start of the event")
async def startevent(interaction: discord.Interaction):
    msg = await interaction.channel.send("@everyone **Variety Friday is starting now!**")
    for uid in data.yes_participants:
        member = interaction.guild.get_member(uid)
        if member:
            try:
                await member.send("Thanks for registering! Variety Friday is starting now, see you there! 🎮")
            except:
                pass
    await interaction.response.send_message("Event announced.", ephemeral=True)

# HELP
@bot.tree.command(name="help", description="Show available commands")
async def help_command(interaction: discord.Interaction):
    cmds = []
    for cmd in bot.tree.get_commands():
        try:
            if isinstance(cmd, app_commands.Command):
                # check permissions
                if cmd.name in ["removegame", "resetgames", "startvote", "endvote"] and not is_allowed_role(interaction):
                    continue
                cmds.append(f"/{cmd.name} - {cmd.description}")
        except:
            continue
    help_text = "\n".join(cmds)
    await interaction.response.send_message(f"**Available commands:**\n{help_text}", ephemeral=True)

# REACTION LISTENERS
@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    if reaction.message.id == data.reminder_message_id:
        if str(reaction.emoji) == "✅":
            data.add_yes_participant(user.id)
            try:
                await user.send("Thanks for registering for Variety Friday! 🎮")
            except:
                pass
        elif str(reaction.emoji) == "❌":
            data.add_no_participant(user.id)
    elif reaction.message.id == data.reminder_message_id:
        if str(reaction.emoji) == "❌":
            data.add_no_participant(user.id)

bot.run(config.TOKEN)
