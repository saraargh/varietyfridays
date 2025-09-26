import discord
from discord.ext import commands, tasks
from discord import app_commands, Embed
import asyncio
from data_manager import DataManager
import config

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.reactions = True  # Required for reaction tracking

bot = commands.Bot(command_prefix="/", intents=intents)
tree = bot.tree
data = DataManager()

GUILD_ID = 1398508733709029428
VOICE_CHANNEL_ID = 1404143716234432714

# ------------------------
# Helper functions
# ------------------------

def create_event_embed():
    embed = Embed(
        title=f"{config.EVENT_NAME} Created!",
        description=f"{config.EVENT_DESCRIPTION}\nReact ✅ to register for the event.\nUse /addgame to add games for voting!",
        color=discord.Color.green()
    )
    if data.games:
        embed.add_field(name="Current Games", value="\n".join(data.games), inline=False)
    return embed

def create_reminder_embed():
    embed = Embed(
        title=f"{config.EVENT_NAME} Reminder!",
        description="React ✅ if you are attending!",
        color=discord.Color.blue()
    )
    return embed

def create_vote_embed():
    if not data.games:
        return None
    description = ""
    for idx, game in enumerate(data.games, start=1):
        description += f"{idx}. {game}\n"
    embed = Embed(
        title="Vote for the next game!",
        description=description,
        color=discord.Color.orange()
    )
    return embed

# ------------------------
# Commands
# ------------------------

@tree.command(name="createevent", description="Create a new event")
async def createevent(interaction: discord.Interaction):
    """Creates a new event and announces it."""
    # Save last_event_id placeholder (can be a timestamp or counter)
    data.last_event_id = int(interaction.created_at.timestamp())
    embed = create_event_embed()
    message = await interaction.channel.send(embed=embed)
    data.vote_message_id = message.id
    await message.add_reaction("✅")
    await interaction.response.send_message("Event created and announced!", ephemeral=True)

@tree.command(name="register", description="Register for the current event")
async def register(interaction: discord.Interaction):
    """Registers the user for the event."""
    user_id = interaction.user.id
    data.add_yes_participant(user_id)
    try:
        await interaction.user.send(f"Thanks for registering for {config.EVENT_NAME}! See you there 🎮")
    except:
        pass
    await interaction.response.send_message("You are now registered!", ephemeral=True)

@tree.command(name="reminder", description="Send a reminder for participants")
async def reminder(interaction: discord.Interaction):
    """Sends a reminder message where users can react to register."""
    embed = create_reminder_embed()
    msg = await interaction.channel.send(embed=embed)
    data.reminder_message_id = msg.id
    await msg.add_reaction("✅")
    await interaction.response.send_message("Reminder sent!", ephemeral=True)

@tree.command(name="addgame", description="Add a game to the event")
@app_commands.describe(name="Name of the game")
async def addgame(interaction: discord.Interaction, name: str):
    if data.add_game(name):
        await interaction.response.send_message(f"Game '{name}' added!", ephemeral=True)
    else:
        await interaction.response.send_message(f"Game '{name}' is already in the list!", ephemeral=True)

@tree.command(name="removegame", description="Remove a game from the event")
@app_commands.describe(name="Name of the game")
async def removegame(interaction: discord.Interaction, name: str):
    if data.remove_game(name):
        await interaction.response.send_message(f"Game '{name}' removed!", ephemeral=True)
    else:
        await interaction.response.send_message(f"Game '{name}' was not found!", ephemeral=True)

@tree.command(name="listgames", description="List all games for the event")
async def listgames(interaction: discord.Interaction):
    games = data.games
    if not games:
        await interaction.response.send_message("No games added yet.", ephemeral=True)
    else:
        await interaction.response.send_message("\n".join(f"{i+1}. {g}" for i, g in enumerate(games)), ephemeral=True)

@tree.command(name="startvote", description="Start a vote for the next game")
async def startvote(interaction: discord.Interaction):
    embed = create_vote_embed()
    if embed is None:
        await interaction.response.send_message("No games to vote on!", ephemeral=True)
        return
    msg = await interaction.channel.send(embed=embed)
    data.vote_message_id = msg.id
    for i in range(len(data.games)):
        await msg.add_reaction(f"{i+1}\N{COMBINING ENCLOSING KEYCAP}")
    await interaction.response.send_message("Voting started!", ephemeral=True)

@tree.command(name="endvote", description="End the current vote and announce the winner")
async def endvote(interaction: discord.Interaction):
    channel = interaction.channel
    try:
        msg = await channel.fetch_message(data.vote_message_id)
    except:
        await interaction.response.send_message("Vote message not found!", ephemeral=True)
        return
    votes = [0] * len(data.games)
    for reaction in msg.reactions:
        if reaction.emoji[0].isdigit():
            idx = int(reaction.emoji[0]) - 1
            votes[idx] = reaction.count - 1  # subtract bot's own reaction
    if not votes or max(votes) == 0:
        await interaction.response.send_message("No votes were cast.", ephemeral=True)
        return
    winner_idx = votes.index(max(votes))
    winner = data.games[winner_idx]
    embed = Embed(
        title="Vote ended!",
        description=f"Thanks for voting! The winner is **{winner}** 🏆",
        color=discord.Color.gold()
    )
    await channel.send(embed=embed)
    await interaction.response.send_message("Vote ended and winner announced.", ephemeral=True)

@tree.command(name="participants", description="Show participants going to the event")
async def participants(interaction: discord.Interaction):
    yes_users = [f"<@{uid}>" for uid in data.yes_participants]
    no_users = [f"<@{uid}>" for uid in data.no_participants]
    embed = Embed(title="Participants", color=discord.Color.purple())
    embed.add_field(name="✅ Going", value="\n".join(yes_users) if yes_users else "None", inline=False)
    embed.add_field(name="❌ Not Going", value="\n".join(no_users) if no_users else "None", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="startevent", description="Announce that the event is starting")
async def startevent(interaction: discord.Interaction):
    yes_users = [bot.get_user(uid) for uid in data.yes_participants]
    mention_text = ", ".join(u.mention for u in yes_users if u)
    msg = await interaction.channel.send(f"{config.EVENT_NAME} is starting! {mention_text}")
    for user in yes_users:
        if user:
            try:
                await user.send(f"{config.EVENT_NAME} is starting now! See you in {VOICE_CHANNEL_ID} 🎮")
            except:
                pass
    await interaction.response.send_message("Event started and notifications sent.", ephemeral=True)

# ------------------------
# Reaction listener
# ------------------------

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    if reaction.message.id == data.vote_message_id:
        return  # votes handled in /endvote
    if reaction.message.id == data.reminder_message_id:
        if str(reaction.emoji) == "✅":
            data.add_yes_participant(user.id)

@bot.event
async def on_reaction_remove(reaction, user):
    if user.bot:
        return
    if reaction.message.id == data.reminder_message_id:
        if str(reaction.emoji) == "✅":
            data.remove_yes_participant(user.id)

# ------------------------
# Bot startup
# ------------------------

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print(f"Error syncing commands: {e}")

bot.run(config.TOKEN)
