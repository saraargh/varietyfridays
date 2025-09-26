"""Main bot code for Variety Friday Discord Bot."""
import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
from datetime import datetime, timedelta
import logging

import config
from data_manager import DataManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix="/", intents=intents)
tree = bot.tree
data_manager = DataManager()

# ---------- HELPERS ----------
def is_allowed(interaction: discord.Interaction) -> bool:
    """Check if the user has any allowed roles."""
    return any(role.name.lower() in [r.lower() for r in config.ALLOWED_ROLES]
               for role in interaction.user.roles)

# ---------- EVENT CREATION ----------
@tree.command(name="create_event", description="Create a Variety Friday event")
async def create_event(interaction: discord.Interaction):
    if not is_allowed(interaction):
        await interaction.response.send_message("You are not allowed to create events.", ephemeral=True)
        return
    
    event_time = datetime.now() + timedelta(hours=config.EVENT_START_HOUR)
    embed = discord.Embed(
        title=f"{config.EVENT_NAME} is coming!",
        description=config.EVENT_DESCRIPTION,
        color=discord.Color.blurple()
    )
    embed.add_field(name="Starts at", value=event_time.strftime("%Y-%m-%d %H:%M %Z"), inline=False)
    
    msg = await interaction.channel.send(embed=embed)
    data_manager.last_event_id = msg.id
    await interaction.response.send_message("Event created!", ephemeral=True)

# ---------- GAME MANAGEMENT ----------
@tree.command(name="add_game", description="Add a game to the event")
@app_commands.describe(game="Name of the game to add")
async def add_game(interaction: discord.Interaction, game: str):
    if not is_allowed(interaction):
        await interaction.response.send_message("You are not allowed to add games.", ephemeral=True)
        return
    if data_manager.add_game(game):
        await interaction.response.send_message(f"Game '{game}' added!")
    else:
        await interaction.response.send_message(f"Game '{game}' is already in the list.")

@tree.command(name="remove_game", description="Remove a game from the event")
@app_commands.describe(game="Name of the game to remove")
async def remove_game(interaction: discord.Interaction, game: str):
    if not is_allowed(interaction):
        await interaction.response.send_message("You are not allowed to remove games.", ephemeral=True)
        return
    if data_manager.remove_game(game):
        await interaction.response.send_message(f"Game '{game}' removed!")
    else:
        await interaction.response.send_message(f"Game '{game}' not found.")

# ---------- PARTICIPANT REGISTRATION ----------
@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    """Track ✅/❌ reactions to register attendance."""
    if payload.message_id != data_manager.last_event_id:
        return

    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    if member.bot:
        return
    
    if str(payload.emoji) == "✅":
        data_manager.add_yes_participant(member.id)
        await member.send(f"You have registered as attending {config.EVENT_NAME}.")
    elif str(payload.emoji) == "❌":
        data_manager.add_no_participant(member.id)
        await member.send(f"You have registered as NOT attending {config.EVENT_NAME}.")

@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    """Handle removing reaction."""
    if payload.message_id != data_manager.last_event_id:
        return
    
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    if member.bot:
        return
    
    if str(payload.emoji) == "✅":
        data_manager.remove_yes_participant(member.id)
    elif str(payload.emoji) == "❌":
        data_manager.remove_no_participant(member.id)

@tree.command(name="participants", description="Show yes/no participants")
async def participants(interaction: discord.Interaction):
    yes_users = [f"<@{uid}>" for uid in data_manager.yes_participants]
    no_users = [f"<@{uid}>" for uid in data_manager.no_participants]
    
    embed = discord.Embed(title="Participants", color=discord.Color.green())
    embed.add_field(name="✅ Yes", value="\n".join(yes_users) or "None", inline=False)
    embed.add_field(name="❌ No", value="\n".join(no_users) or "None", inline=False)
    
    await interaction.response.send_message(embed=embed)

# ---------- VOTING ----------
@tree.command(name="vote", description="Vote for a game")
@app_commands.describe(game_number="Number of the game to vote for")
async def vote(interaction: discord.Interaction, game_number: int):
    if not 1 <= game_number <= len(data_manager.games):
        await interaction.response.send_message("Invalid game number.", ephemeral=True)
        return
    
    selected_game = data_manager.games[game_number - 1]
    if hasattr(data_manager, "votes"):
        if interaction.user.id in data_manager.votes:
            prev = data_manager.votes[interaction.user.id]
            data_manager.votes[interaction.user.id] = selected_game
            await interaction.response.send_message(f"Changed your vote to {selected_game}.", ephemeral=True)
        else:
            data_manager.votes[interaction.user.id] = selected_game
            await interaction.response.send_message(f"You voted for {selected_game}.", ephemeral=True)
    else:
        data_manager.votes = {interaction.user.id: selected_game}
        await interaction.response.send_message(f"You voted for {selected_game}.", ephemeral=True)

@tree.command(name="endvote", description="End the vote and announce the winner")
async def endvote(interaction: discord.Interaction):
    if not hasattr(data_manager, "votes") or not data_manager.votes:
        await interaction.response.send_message("No votes yet!", ephemeral=True)
        return
    
    vote_counts = {}
    for vote in data_manager.votes.values():
        vote_counts[vote] = vote_counts.get(vote, 0) + 1
    
    winner = max(vote_counts, key=vote_counts.get)
    
    embed = discord.Embed(
        title="Voting Ended!",
        description=f"Thanks for voting! 🎉\n🏆 **{winner}** is the winner!",
        color=discord.Color.gold()
    )
    await interaction.channel.send(embed=embed)
    
    # Clear votes after announcement
    data_manager.votes = {}

# ---------- REMINDERS ----------
@tasks.loop(minutes=60)
async def reminder_task():
    if data_manager.last_event_id is None:
        return
    
    channel = bot.get_channel(config.VOICE_CHANNEL_NAME)
    if channel is None:
        return
    
    yes_mentions = [f"<@{uid}>" for uid in data_manager.yes_participants]
    if yes_mentions:
        msg = await channel.send(f"Reminder: {config.EVENT_NAME} is happening soon! {' '.join(yes_mentions)}")
        data_manager.reminder_message_id = msg.id

@bot.event
async def on_ready():
    await tree.sync()
    reminder_task.start()
    logger.info(f"Logged in as {bot.user}!")

# ---------- RUN ----------
bot.run(config.TOKEN)
