import discord
from discord import app_commands
from discord.ext import commands
import logging
from data_manager import DataManager
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot and DataManager
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="/", intents=intents)
data_manager = DataManager()

# -------------------------
# Helper functions
# -------------------------
def is_allowed(interaction: discord.Interaction):
    """Check if user has allowed roles."""
    if not config.ALLOWED_ROLES:
        return True
    return any(role.id in config.ALLOWED_ROLES for role in interaction.user.roles)

# -------------------------
# Register command
# -------------------------
@bot.tree.command(name="register", description="Register a game/event")
async def register(interaction: discord.Interaction, game_name: str):
    if not is_allowed(interaction):
        await interaction.response.send_message("You do not have permission to register a game.", ephemeral=True)
        return

    added = data_manager.add_game(game_name)
    if added:
        await interaction.response.send_message(f"Game '{game_name}' added successfully!")
    else:
        await interaction.response.send_message(f"Game '{game_name}' already exists!")

# -------------------------
# Voting system
# -------------------------
@bot.tree.command(name="vote", description="Vote for a game by reacting")
async def vote(interaction: discord.Interaction):
    if not data_manager.games:
        await interaction.response.send_message("No games available to vote on.")
        return

    description = "\n".join(f"{config.VOTE_EMOJIS[i]} {game}" for i, game in enumerate(data_manager.games))
    embed = discord.Embed(title="Vote for a game!", description=description, color=discord.Color.blue())

    vote_message = await interaction.channel.send(embed=embed)
    data_manager.vote_message_id = vote_message.id

    # Add emoji reactions
    for emoji in config.VOTE_EMOJIS[:len(data_manager.games)]:
        await vote_message.add_reaction(emoji)

    # Initialize vote counts
    data_manager.votes = {emoji: 0 for emoji in config.VOTE_EMOJIS[:len(data_manager.games)]}
    await interaction.response.send_message("Voting started!", ephemeral=True)

# -------------------------
# Reaction tracking
# -------------------------
@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    if reaction.message.id != data_manager.vote_message_id:
        return
    if reaction.emoji in data_manager.votes:
        data_manager.votes[reaction.emoji] += 1

@bot.event
async def on_reaction_remove(reaction, user):
    if user.bot:
        return
    if reaction.message.id != data_manager.vote_message_id:
        return
    if reaction.emoji in data_manager.votes and data_manager.votes[reaction.emoji] > 0:
        data_manager.votes[reaction.emoji] -= 1

# -------------------------
# End vote command
# -------------------------
@bot.tree.command(name="endvote", description="End the current vote and announce the winner")
async def endvote(interaction: discord.Interaction):
    votes = data_manager.votes
    games = data_manager.games

    if not votes or not games:
        await interaction.response.send_message("No active votes or games to end.")
        return

    # Determine winner
    winner_emoji = max(votes, key=votes.get)
    winner_index = config.VOTE_EMOJIS.index(winner_emoji)
    winner_game = games[winner_index]

    # Create an embed announcing the winner
    embed = discord.Embed(
        title="Vote Ended",
        description=f"Thanks for voting! 🎉 **{winner_game}** is the winner! 🏆",
        color=discord.Color.green()
    )

    # Optional: show vote counts
    vote_results = "\n".join(
        f"{config.VOTE_EMOJIS[i]} {games[i]} — {votes.get(emoji, 0)} votes"
        for i, emoji in enumerate(config.VOTE_EMOJIS[:len(games)])
    )
    embed.add_field(name="Results", value=vote_results, inline=False)

    await interaction.response.send_message(embed=embed)

    # Reset for next vote
    data_manager.clear_votes()
    data_manager.clear_games()
    data_manager.vote_message_id = None

# -------------------------
# Bot startup
# -------------------------
@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await bot.tree.sync()
    logger.info("Command tree synced!")

bot.run(config.TOKEN)
