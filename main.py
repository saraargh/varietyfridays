"""Variety Friday Discord Bot - Main application."""
import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging

import config
from data_manager import DataManager
from utils import (
    is_allowed, create_variety_event, delete_event_safely,
    get_voting_emojis, safe_send_dm, create_games_embed,
    create_participants_embed
)

# ------------------ Logging ------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ------------------ Bot Class ------------------
class VarietyFridayBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True
        intents.guilds = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

        self.data = DataManager()
        self._vote_message = None
        self._reminder_message = None
        self._last_event = None

    async def setup_hook(self):
        await self.tree.sync()
        logger.info("Command tree synced")

    async def on_ready(self):
        logger.info(f"✅ Logged in as {self.user} (ID: {self.user.id if self.user else 'Unknown'})")
        logger.info(f"Connected to {len(self.guilds)} guilds")

    async def on_command_error(self, ctx, error):
        logger.error(f"Command error: {error}")

    async def get_vote_message(self, channel):
        if self._vote_message:
            return self._vote_message
        if self.data.vote_message_id:
            try:
                self._vote_message = await channel.fetch_message(self.data.vote_message_id)
                return self._vote_message
            except discord.NotFound:
                self.data.vote_message_id = None
        return None

    async def get_reminder_message(self, channel):
        if self._reminder_message:
            return self._reminder_message
        if self.data.reminder_message_id:
            try:
                self._reminder_message = await channel.fetch_message(self.data.reminder_message_id)
                return self._reminder_message
            except discord.NotFound:
                self.data.reminder_message_id = None
        return None

    async def get_last_event(self, guild):
        if self._last_event:
            return self._last_event
        if self.data.last_event_id:
            try:
                self._last_event = guild.get_scheduled_event(self.data.last_event_id)
                return self._last_event
            except Exception:
                self.data.last_event_id = None
        return None

# ------------------ Initialize ------------------
bot = VarietyFridayBot()

# ======================== GAME COMMANDS ========================
@bot.tree.command(name="addgame", description="Suggest a game for Variety Friday")
async def addgame(interaction: discord.Interaction, name: str):
    game_name = name.strip()
    if not game_name:
        await interaction.response.send_message("⚠️ Game name cannot be empty!", ephemeral=True)
        return
    if bot.data.add_game(game_name):
        await interaction.response.send_message(f"✅ `{game_name}` has been added!")
        logger.info(f"Game '{game_name}' added by {interaction.user}")
    else:
        await interaction.response.send_message(f"⚠️ `{game_name}` has already been suggested!", ephemeral=True)

@bot.tree.command(name="listgames", description="See suggested games")
async def listgames(interaction: discord.Interaction):
    embed = create_games_embed(bot.data.games)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="removegame", description="Remove a suggested game")
async def removegame(interaction: discord.Interaction, name: str):
    if not is_allowed(interaction):
        await interaction.response.send_message("⛔ You don't have permission.", ephemeral=True)
        return
    game_name = name.strip()
    if bot.data.remove_game(game_name):
        await interaction.response.send_message(f"🗑️ `{game_name}` has been removed!")
    else:
        await interaction.response.send_message(f"⚠️ `{game_name}` not found.", ephemeral=True)

@bot.tree.command(name="resetgames", description="Clear all suggested games")
async def resetgames(interaction: discord.Interaction):
    if not is_allowed(interaction):
        await interaction.response.send_message("⛔ You don't have permission.", ephemeral=True)
        return
    bot.data.clear_games()
    await interaction.response.send_message("🗑️ Game list reset!")

# ======================== VOTING COMMANDS ========================
@bot.tree.command(name="startvote", description="Start voting on suggested games")
async def startvote(interaction: discord.Interaction):
    if not is_allowed(interaction):
        await interaction.response.send_message("⛔ You don't have permission.", ephemeral=True)
        return
    games = bot.data.games
    if not games:
        await interaction.response.send_message("📭 No games to vote on.", ephemeral=True)
        return
    if len(games) > config.MAX_VOTING_OPTIONS:
        await interaction.response.send_message(f"⚠️ Too many games. Max {config.MAX_VOTING_OPTIONS}.", ephemeral=True)
        return
    embed = discord.Embed(
        title="🗳️ Variety Friday Vote",
        description="\n".join(f"{i+1}. {g}" for i, g in enumerate(games)),
        color=discord.Color.green()
    )
    vote_message = await interaction.channel.send(embed=embed)
    bot._vote_message = vote_message
    bot.data.vote_message_id = vote_message.id
    for i, _ in enumerate(games):
        await vote_message.add_reaction(get_voting_emojis()[i])
    await interaction.response.send_message("✅ Voting started!", ephemeral=True)

@bot.tree.command(name="endvote", description="End vote and announce winner")
async def endvote(interaction: discord.Interaction):
    if not is_allowed(interaction):
        await interaction.response.send_message("⛔ You don't have permission.", ephemeral=True)
        return
    vote_message = await bot.get_vote_message(interaction.channel)
    if not vote_message:
        await interaction.response.send_message("⚠️ No active vote.", ephemeral=True)
        return
    games = bot.data.games
    counts = [reaction.count - 1 for reaction in vote_message.reactions if reaction.emoji in get_voting_emojis()]
    if counts:
        max_votes = max(counts)
        winners = [games[i] for i, c in enumerate(counts) if c == max_votes]
        desc = f"The winner is **{winners[0]}** with {max_votes} votes!" if len(winners) == 1 else \
               f"Tie with {max_votes} votes each:\n" + "\n".join(f"• {w}" for w in winners)
        embed = discord.Embed(title="🏆 Vote Result", description=desc, color=discord.Color.gold())
        await interaction.channel.send(embed=embed)
    bot._vote_message = None
    bot.data.vote_message_id = None
    await interaction.response.send_message("✅ Vote ended.", ephemeral=True)

# ======================== EVENT COMMANDS ========================
@bot.tree.command(name="createevent", description="Create the Variety Friday event")
async def createevent(interaction: discord.Interaction):
    if not is_allowed(interaction):
        await interaction.response.send_message("⛔ You don't have permission.", ephemeral=True)
        return
    await delete_event_safely(interaction.guild, bot.data.last_event_id)
    event = await create_variety_event(interaction.guild)
    if not event:
        await interaction.response.send_message("❌ Failed to create event.", ephemeral=True)
        return
    bot._last_event = event
    bot.data.last_event_id = event.id
    await interaction.response.send_message(f"✅ Event created: {event.url}")

# ======================== REGISTRATION & REMINDER ========================
@bot.tree.command(name="register", description="Announce registration & game suggestions")
async def register(interaction: discord.Interaction):
    allowed_roles = config.ALLOWED_ROLES + ["Administrator"]
    if not is_allowed(interaction, allowed_roles):
        await interaction.response.send_message("⛔ You don't have permission.", ephemeral=True)
        return
    last_event = await bot.get_last_event(interaction.guild)
    if not last_event:
        await interaction.response.send_message("⚠️ No event created yet.", ephemeral=True)
        return
    embed = discord.Embed(
        title="📢 Variety Friday Registration",
        description=f"@everyone Variety Friday is coming up! 🎉\nReact below to register:\n✅ Yes\n❌ No\nSuggest games with `/addgame`!",
        color=discord.Color.purple()
    )
    embed.add_field(name="Event Link", value=f"[Join here]({last_event.url})")
    msg = await interaction.channel.send(embed=embed)
    bot._reminder_message = msg
    bot.data.reminder_message_id = msg.id
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    await interaction.response.send_message("✅ Registration announcement posted!", ephemeral=True)

@bot.tree.command(name="reminder", description="Remind users to register & add games")
async def reminder(interaction: discord.Interaction):
    last_event = await bot.get_last_event(interaction.guild)
    if not last_event:
        await interaction.response.send_message("⚠️ No event created yet.", ephemeral=True)
        return
    embed = discord.Embed(
        title="⏰ Reminder: Variety Friday is coming!",
        description=f"@everyone Remember to register with reactions and suggest games using `/addgame`!",
        color=discord.Color.blurple()
    )
    embed.add_field(name="Event Link", value=f"[Join here]({last_event.url})")
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ Reminder sent!", ephemeral=True)

# ======================== START EVENT COMMAND ========================
@bot.tree.command(name="start_event", description="Announce event is starting & DM participants")
async def start_event(interaction: discord.Interaction):
    allowed_roles = config.ALLOWED_ROLES + ["Administrator"]
    if not is_allowed(interaction, allowed_roles):
        await interaction.response.send_message("⛔ You don't have permission.", ephemeral=True)
        return
    last_event = await bot.get_last_event(interaction.guild)
    if not last_event:
        await interaction.response.send_message("⚠️ No event created yet.", ephemeral=True)
        return
    await interaction.channel.send(f"@everyone 🎉 Variety Friday is starting now! Join the event: {last_event.url}")
    guild = interaction.guild
    for user_id in bot.data.yes_participants:
        member = guild.get_member(user_id)
        if member:
            try:
                await member.send(f"🎮 Variety Friday is starting now! Join the event: {last_event.url}")
            except Exception as e:
                logger.warning(f"Failed to DM {member}: {e}")
    await interaction.response.send_message("✅ Event start announced and DMs sent!", ephemeral=True)

# ======================== PARTICIPANTS COMMAND ========================
@bot.tree.command(name="participants", description="Show who has registered for Variety Friday")
async def participants(interaction: discord.Interaction):
    yes_participants = [interaction.guild.get_member(uid).display_name for uid in bot.data.yes_participants if interaction.guild.get_member(uid)]
    no_participants = [interaction.guild.get_member(uid).display_name for uid in bot.data.no_participants if interaction.guild.get_member(uid)]
    if not yes_participants and not no_participants:
        await interaction.response.send_message("📭 Nobody has registered yet.")
        return
    embed = create_participants_embed(yes_participants, no_participants)
    await interaction.response.send_message(embed=embed)

# ======================== HELP COMMAND ========================
@bot.tree.command(name="help", description="Show available commands")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="🤖 Variety Friday Bot Commands", color=discord.Color.blurple())
    embed.add_field(
        name="🎮 General Commands",
        value=(
            "`/addgame <name>` – Suggest a game\n"
            "`/listgames` – Show all suggested games\n"
            "`/participants` – Show who's attending\n"
            "`/help` – Show this help menu"
        ),
        inline=False
    )
    embed.add_field(
        name="🛠️ Admin / Allowed Roles Commands",
        value=(
            "`/removegame <name>` – Remove a game\n"
            "`/resetgames` – Clear game list\n"
            "`/startvote` – Start voting\n"
            "`/endvote` – End voting & announce winner\n"
            "`/createevent` – Create Variety Friday event\n"
            "`/register` – Announce registration\n"
            "`/reminder` – Remind to register & suggest games\n"
            "`/start_event` – Announce event is starting & DM participants"
        ),
        inline=False
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ======================== REACTION HANDLERS ========================
@bot.event
async def on_raw_reaction_add(payload):
    if bot.user and payload.user_id == bot.user.id:
        return
    if bot.data.reminder_message_id and payload.message_id == bot.data.reminder_message_id:
        guild = bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        if not member or member.bot:
            return
        if str(payload.emoji) == "✅":
            bot.data.add_yes_participant(member.id)
            await safe_send_dm(member, "🎉 Thanks for signing up for **Variety Friday**! See you there!")
        elif str(payload.emoji) == "❌":
            bot.data.add_no_participant(member.id)

@bot.event
async def on_raw_reaction_remove(payload):
    if bot.user and payload.user_id == bot.user.id:
        return
    if bot.data.reminder_message_id and payload.message_id == bot.data.reminder_message_id:
        if str(payload.emoji) == "✅":
            bot.data.remove_yes_participant(payload.user_id)
        elif str(payload.emoji) == "❌":
            bot.data.remove_no_participant(payload.user_id)

# ======================== BOT LIFECYCLE & MAIN ========================
def main():
    if config.TOKEN:
        bot.run(config.TOKEN)
    else:
        logger.error("TOKEN not set")
        raise ValueError("TOKEN environment variable is required")

if __name__ == "__main__":
    main()
