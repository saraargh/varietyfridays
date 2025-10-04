"""Main bot for Variety Friday."""
import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import pytz
import logging

import config
from data_manager import DataManager

#keep alive#
from keep_alive import keep_alive

keep_alive()  # starts the server in another thread

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
            embed.add_field(name=f"/{cmd.name}", value=cmd.description, inline=False)
        except:
            continue
    await interaction.response.send_message(embed=embed, ephemeral=False)

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

    # Calculate start time for the next Friday
    tz = pytz.timezone(config.TIMEZONE)
    now = datetime.datetime.now(tz)

    # Weekday: Monday=0, ..., Friday=4, Sunday=6
    days_until_friday = (4 - now.weekday() + 7) % 7
    if days_until_friday == 0 and now.hour >= config.EVENT_START_HOUR:
        days_until_friday = 7  # If today is Friday but the time has passed, pick next Friday

    start_time = now.replace(hour=config.EVENT_START_HOUR, minute=0, second=0, microsecond=0) + datetime.timedelta(days=days_until_friday)
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
    await interaction.response.send_message(f"Event created: {event.name} for {start_time.strftime('%A, %d %B %Y %H:%M %Z')}", ephemeral=True)

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

    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("✅")  # Yes
    await msg.add_reaction("❌")  # No
    await msg.add_reaction("❔")  # Maybe

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

    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("✅")  # Yes
    await msg.add_reaction("❌")  # No
    await msg.add_reaction("❔")  # Maybe

    data.reminder_message_id = msg.id
    await interaction.response.send_message("Reminder sent!", ephemeral=True)

# -------------------------
# Games commands
# -------------------------
@bot.tree.command(name="addgame", description="Add a game to vote on")
async def addgame(interaction: discord.Interaction, name: str):
    # Block adding games if voting is open
    if data.vote_message_id is not None:
        embed = discord.Embed(
            title="🚨🚨 **TOO LATE!** 🚨🚨",
            description=f"**{interaction.user.mention} just tried to add a game while voting is already open!**\n\n"
                        f"Be earlier next time ⏰",
            color=discord.Color.red()
        )
        embed.set_image(url="https://media3.giphy.com/media/v1.Y2lkPTZjMDliOTUyeHZhc251N2RmYXh2eGs3ajZ1dXh3cHNkcTQ1c2ZwN3Fxd2pvMjV2OSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/cqdBfG6mFamru/giphy.gif")

        msg = await interaction.channel.send(embed=embed)
        for emoji in ["⏰", "❌", "😂"]:
            await msg.add_reaction(emoji)
        return

    # List of blocked keywords
    blocked_keywords = ["death note", "dn", "dnkw", "death note killer within"]
    name_clean = name.lower().replace(" ", "")
    if any(keyword.replace(" ", "") in name_clean for keyword in blocked_keywords):
        embed = discord.Embed(
            title="🚨🚨 **BLOCKED GAME ATTEMPT!** 🚨🚨",
            description=f"**{interaction.user.mention} just tried to add Death Note!**\n"
                        f"**It's Variety Friday, please add a different game!**",
            color=discord.Color.red()
        )
        embed.set_image(url="https://media4.giphy.com/media/v1.Y2lkPTZjMDliOTUycmdtenhjMXJkaXY4c2JqMnpwcnYwZHFvcW9jMzlqMzh3ejNwY3dwdyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/L9xNendArFokw/giphy.gif")  

        msg = await interaction.channel.send(embed=embed)
        for emoji in ["🚨", "❌", "😱"]:
            await msg.add_reaction(emoji)
        return

    # Add game normally
    if data.addgame(name):
        games_list = ", ".join(data.games)
        await interaction.response.send_message(f"Game added: {name}\nCurrent games: {games_list}", ephemeral=False)
    else:
        await interaction.response.send_message(
            "Cannot add more than 10 games or game already exists.",
            ephemeral=False
        )
@bot.tree.command(name="removegame", description="Remove a game (roles only)")
async def removegame(interaction: discord.Interaction, name: str):
    if not allowed(interaction):
        await interaction.response.send_message("You don't have permission to remove games.", ephemeral=True)
        return
    if data.removegame(name):
        await interaction.response.send_message(f"Removed game: {name}", ephemeral=False)
    else:
        await interaction.response.send_message("Game not found.", ephemeral=True)

@bot.tree.command(name="listgames", description="List all current games")
async def listgames(interaction: discord.Interaction):
    if not data.games:
        await interaction.response.send_message("No games added yet.", ephemeral=False)
        return
    
    await interaction.response.send_message(
        "Current games:\n" + "\n".join(f"{i+1}. {g}" for i, g in enumerate(data.games)),
        ephemeral=False
    )

@bot.tree.command(name="resetgames", description="Reset all games (roles only)")
async def resetgames(interaction: discord.Interaction):
    if not allowed(interaction):
        await interaction.response.send_message("You don't have permission to reset games.", ephemeral=True)
        return
    data.resetgames()
    await interaction.response.send_message("All games have been reset.", ephemeral=False)

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
        elif str(reaction.emoji) == "❔":
            data.add_maybe_participant(user.id)

@bot.event
async def on_reaction_remove(reaction, user):
    if user.bot:
        return
    if reaction.message.id in [data.reminder_message_id]:
        if str(reaction.emoji) == "✅":
            data.remove_yes_participant(user.id)
        elif str(reaction.emoji) == "❌":
            data.remove_no_participant(user.id)
        elif str(reaction.emoji) == "❔":
            data.remove_maybe_participant(user.id)

@bot.tree.command(name="participants", description="Show who is attending")
async def participants(interaction: discord.Interaction):
    yes_users = [f"<@{uid}>" for uid in data.yes_participants]
    no_users = [f"<@{uid}>" for uid in data.no_participants]
    maybe_users = [f"<@{uid}>" for uid in data.maybe_participants]
    embed = discord.Embed(title="Event Participants", color=discord.Color.blue())
    embed.add_field(name="✅ Yes", value="\n".join(yes_users) or "None", inline=False)
    embed.add_field(name="❌ No", value="\n".join(no_users) or "None", inline=False)
    embed.add_field(name="❔ Maybe", value="\n".join(maybe_users) or "None", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=False)

# -------------------------
# End vote with tie logic
# -------------------------
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

    vote_counts = {}
    for i, game in enumerate(data.games):
        emoji = f"{i+1}\u20E3"
        reaction = discord.utils.get(msg.reactions, emoji=emoji)
        vote_counts[game] = reaction.count - 1 if reaction else 0

    max_votes = max(vote_counts.values(), default=0)
    winners = [g for g, v in vote_counts.items() if v == max_votes]

    if len(winners) == 0:
        embed = discord.Embed(
            title="No votes were cast 😢",
            description="Nobody voted, so no game was chosen.",
            color=discord.Color.dark_gray()
        )
        await channel.send(embed=embed)

    elif len(winners) == 1:
        winner_text = winners[0]
        embed = discord.Embed(
            title=f"🏆 {winner_text} WINS! 🏆",
            description=f"Variety Friday will be playing **{winner_text}**! 🎉",
            color=discord.Color.green()
        )
        embed.set_image(url="https://media1.giphy.com/media/v1.Y2lkPTZjMDliOTUyM2g0dWVqcnBpcTN1NGJzMDYyMnY4OHFwMXZiOHlyOXJ1MGQ2aTdwMCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/blSTtZehjAZ8I/giphy.gif")
        await channel.send(embed=embed)

    else:
        # Tie detected
        tied_games_text = "\n".join(f"{i+1}. {g}" for i, g in enumerate(winners))
        embed = discord.Embed(
            title="⚠️ IT'S A TIE! ⚠️",
            description=f"The following games have tied:\n{tied_games_text}\n\nReact to vote again to break the tie!",
            color=discord.Color.red()
        )
        embed.set_image(url="https://media0.giphy.com/media/v1.Y2lkPTZjMDliOTUya2pmcnM5Y25kcGprZmlhbnVycDlmNjIxa2FhYWFkYWI2czBzenRmcyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/xT3i0VNrc6Ny7bxfJm/giphy.gif")
        tie_msg = await channel.send(embed=embed)

        # Add numeric reactions for tiebreak
        for i in range(len(winners)):
            await tie_msg.add_reaction(f"{i+1}\u20E3")
        await tie_msg.add_reaction("🅰️")  # "All of them" option

        data.tie_message_id = tie_msg.id
        data.tie_options = winners
        data.vote_message_id = None  # Reset main vote

# -------------------------
# End tiebreak command
# -------------------------
@bot.tree.command(name="endtiebreak", description="End the tiebreak voting and announce winner")
async def endtiebreak(interaction: discord.Interaction):
    if not allowed(interaction):
        await interaction.response.send_message("You don't have permission.", ephemeral=True)
        return
    if not getattr(data, 'tie_message_id', None):
        await interaction.response.send_message("No active tiebreak voting.", ephemeral=True)
        return

    channel = interaction.channel
    try:
        msg = await channel.fetch_message(data.tie_message_id)
    except:
        await interaction.response.send_message("Tiebreak vote message not found.", ephemeral=True)
        return

    tie_counts = {}
    for i, game in enumerate(data.tie_options):
        emoji = f"{i+1}\u20E3"
        reaction = discord.utils.get(msg.reactions, emoji=emoji)
        tie_counts[game] = reaction.count - 1 if reaction else 0

    # Check "All of them" option
    all_reaction = discord.utils.get(msg.reactions, emoji="🅰️")
    if all_reaction and all_reaction.count > 1:
        winner_text = "All of them"
    else:
        max_votes = max(tie_counts.values(), default=0)
        winners = [g for g, v in tie_counts.items() if v == max_votes]
        winner_text = winners[0] if winners else "No votes cast"

    embed = discord.Embed(
        title=f"🎉 Tie Broken! 🎉",
        description=f"Variety Friday will be playing **{winner_text}**! 🏆",
        color=discord.Color.green()
    )
    embed.set_image(url="https://media1.giphy.com/media/v1.Y2lkPTZjMDliOTUyM2g0dWVqcnBpcTN1NGJzMDYyMnY4OHFwMXZiOHlyOXJ1MGQ2aTdwMCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/blSTtZehjAZ8I/giphy.gif")
    await channel.send(embed=embed)

    data.tie_message_id = None
    data.tie_options = None

# -------------------------
# Start event command
# -------------------------
@bot.tree.command(name="startevent", description="Announce the start of the event")
async def startevent(interaction: discord.Interaction):
    if not allowed(interaction):
        await interaction.response.send_message("You don't have permission to start the event.", ephemeral=True)
        return

    yes_users = [f"<@{uid}>" for uid in data.yes_participants]
    announce_msg = await interaction.channel.send(f"{config.EVENT_NAME} is starting!")
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

