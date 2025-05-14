import sys
import os
import threading
import discord
import psycopg2
import aiohttp, io, asyncio, re, datetime
from io import BytesIO

from discord.ext import commands
from discord.ext.commands import has_permissions
from discord import Webhook
from threading import Thread
from flask import Flask
from tools.dataIO import fileIO
from db import create_room, list_rooms, room_exists, add_channel_to_room, get_connected_webhooks
from keep_alive import keep_alive


config_location = fileIO("config/config.json", "load") #LOAD JSON FILE
infomation = fileIO("config/infomation.json", "load") #LOAD JSON FILE
emojiReplace = fileIO("config/emoji_id.json", "load") #LOAD JSON FILE
regisletInfo = fileIO("config/regislet.json", "load") #LOAD JSON FILE
stattingDB = fileIO("config/stattingDB.json", "load")
ignoredID = fileIO("config/ignoreID.json", "load")

Shards = config_location["Shards"] #GET SHARD/VER FROM JSON FILE
def get_prefix(client, message): ##first we define get_prefix
    #prefixes = fileIO("config/prefixes.json", "load")
    prefix = None #prefixes.get(str(message.guild.id), None)
    if prefix is None:
        prefix = "Miri"
        save_prefix(prefix, message)
    return prefix

def save_prefix(prefix, message):
    prefixes = fileIO("config/prefixes.json", "load")
    prefixes[str(message.guild.id)] = prefix
    fileIO("config/prefixes.json", "save", prefixes)

IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".webm", ".mp4"]
FAKE_EMOJI_REGEX = r'\[:([^\]:]+):\]\((https?://[^\)]+)\)'

def extract_image_urls(content: str):
    return [
        url for url in re.findall(r'https?://\S+', content)
        if any(url.lower().endswith(ext) for ext in IMAGE_EXTENSIONS)
    ]

def replace_fake_emojis(text: str):
    return re.sub(FAKE_EMOJI_REGEX, lambda m: f"[{m.group(1)}]({m.group(2)})", text)

def replace_custom_emojis_with_image_url(content: str, guild_emojis: list):
    emoji_pattern = r':([a-zA-Z0-9_]+):'
    matches = re.findall(emoji_pattern, content)

    for emoji_name in matches:
        # Look for the custom emoji in the server's emojis
        emoji = discord.utils.get(guild_emojis, name=emoji_name)
        if emoji:
            # Replace the emoji name with the emoji's image URL
            emoji_url = f"https://cdn.discordapp.com/emojis/{emoji.id}.{'gif' if emoji.animated else 'png'}"
            content = content.replace(f":{emoji_name}:", f"[:{emoji_name}:]({emoji_url})")

    return content
#INIT UR BOT
intents = discord.Intents.all()
intents.message_content = True
bot = commands.AutoShardedBot(intents=intents, shard_count = Shards, command_prefix=get_prefix, activity = discord.Game(name="Ping me + help for help OwO"))

#DON'T WORRY ABOUT THIS
bot.remove_command('help')

#def get_user_data(user_id):
#    cursor.execute("SELECT exp, level FROM user_levels WHERE user_id = %s", (user_id,))
#    data = cursor.fetchone()
#    if data:
#        return data
#    else:
#        # Explicitly set initial experience and level
#        cursor.execute("INSERT INTO user_levels (user_id, exp, level) VALUES (%s, %s, %s)",
#                       (user_id, 0, 1))
#        conn.commit()
#        return (0, 1)
#def add_experience(user_id, exp_gain=1):
#    exp, level = get_user_data(user_id)
#    new_exp = exp + exp_gain
#    next_level_exp = level * 100
#
#    if new_exp >= next_level_exp:
#        new_exp -= next_level_exp
#        level += 1
#        cursor.execute("UPDATE user_levels SET exp = %s, level = %s WHERE user_id = %s",
#                       (new_exp, level, user_id))
#        conn.commit()
#        return level  # level-up happened
#    else:
#        cursor.execute("UPDATE user_levels SET exp = %s WHERE user_id = %s", (new_exp, user_id))
#        conn.commit()
#        return None  # no level-up
        
@bot.event
async def on_ready():
    #THIS RUN WHEN BOT START UP
    print("Login info:\nUser: {}\nUser ID: {}".format(bot.user.name, bot.user.id))

@bot.event
async def on_command(command):
    ...
import discord

@bot.command()
async def check_roles(ctx):
    guild = ctx.guild
    bot = ctx.me  # Get the bot's own member object
    
    # Loop through all roles in the server
    for role in guild.roles:
        role_name = role.name
        role_position = role.position  # Position of the role in the hierarchy
        print(f"Role: {role_name}, Position: {role_position}")

        # List members who have this role
        members_with_role = [member for member in guild.members if role in member.roles]
        if members_with_role:
            print(f"  Members with role '{role_name}':")
            for member in members_with_role:
                print(f"    - {member.display_name} (ID: {member.id})")
        else:
            print(f"  No members have the role '{role_name}'")

    # Also print the bot's own top role position
    bot_top_role_position = max(role.position for role in bot.roles)
    print(f"Bot's top role position: {bot_top_role_position}")
    print(f"Bot's highest role: {bot.top_role.name}")

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    # Check if the nickname has actually changed
    if before.nick != after.nick:
        # Ignore if the bot itself is making the change
        if after.id == bot.user.id:
            return

        # Wait briefly to ensure audit logs are updated
        await asyncio.sleep(1)

        guild = after.guild
        
        # Check the audit logs to see who made the change
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.member_update):
            if entry.target.id == after.id:
                changer = entry.user

                # If the changer is the user themselves or the bot, do nothing
                if changer.id == after.id or changer.id == bot.user.id:
                    return  # Ignore if the user or bot made the change

                # If someone else made the change, revert it
                try:
                    await after.edit(nick=before.nick, reason="Nickname reverted - changed by someone else.")
                    print(f"Reverted nickname of {after.display_name} (changed by {changer.display_name})")
                except discord.Forbidden:
                    print("Bot doesn't have permission to change nicknames.")
                except discord.HTTPException as e:
                    print(f"Failed to revert nickname: {e}")
                break  # Stop after the first successful revert
@bot.event
async def on_message(message):
    if message.author.bot or message.webhook_id:
        await bot.process_commands(message)
        return

    connected_channels = get_connected_webhooks(message.channel.id)
    if not connected_channels:
        if "<@589793989922783252>" in message.content and "help" in message.content.lower():
            messageDes = get_help_message(bot, message)
            em = discord.Embed(title="**Commands List**", description=messageDes, color=discord.Color.blue())
            await message.channel.send(embed=em)
        await bot.process_commands(message)
        return

    # Load attachments as raw bytes
    fileBytes = []
    try:
        if message.attachments:
            async with aiohttp.ClientSession() as session:
                for eachFile in message.attachments:
                    async with session.get(eachFile.url) as resp:
                        img_bytes = await resp.read()
                        fileBytes.append((img_bytes, eachFile.filename))
    except:
        fileBytes = []

    # Prepare reply embed
    def replace_custom_emojis(text):
        pattern = r'<(a?):(\w+):(\d+)>'
        return re.sub(pattern, lambda m: f"https://cdn.discordapp.com/emojis/{m.group(3)}.{'gif' if m.group(1) == 'a' else 'png'}", text)

    reply_embed = None
    if message.reference:
        try:
            replyMsg = await message.channel.fetch_message(message.reference.message_id)

            reply_embed = discord.Embed(color=discord.Color.blue())
            reply_content = replyMsg.content.strip()

            # Convert emojis in content to image URLs
            reply_content = replace_custom_emojis(reply_content)

            image_extensions = [".png", ".jpg", ".jpeg", ".gif", ".webp"]
            is_image_url = any(reply_content.lower().endswith(ext) for ext in image_extensions)

            if is_image_url:
                reply_embed.set_image(url=reply_content)
            elif reply_content:
                reply_embed.description = reply_content

            # Fallback: check for attachments with image files
            if replyMsg.attachments:
                for att in replyMsg.attachments:
                    if any(att.filename.lower().endswith(ext) for ext in image_extensions):
                        reply_embed.set_image(url=att.url)
                        break

            reply_embed.set_author(
                name=replyMsg.author.display_name,
                icon_url=replyMsg.author.avatar.url if replyMsg.author.avatar else discord.Embed.Empty
            )

        except Exception as e:
            print(f"[Reply Embed Error] {e}")
            reply_embed = None

    # Function to check if a message contains only emojis and no text
    def is_standalone_emoji(emoji_tag: str, content: str):
        """
        Check if the emoji tag appears standalone (not part of a larger sentence).
        """
        # Make sure the emoji tag is surrounded by spaces or is at the beginning/end of the string
        pattern = rf'(^|\s){re.escape(emoji_tag)}(\s|$)'
        return bool(re.search(pattern, content))

    # Function to replace custom emoji tags with their image URLs
    def replace_emoji_with_url(content: str):
        """
        Replace custom emoji tags like <:emoji_name:emoji_id> with the image URL, 
        but only if the emoji tag is standalone (not part of text).
        """
        # Match custom emoji tags <:emoji_name:emoji_id>
        custom_emoji_pattern = r'<(a?):([a-zA-Z0-9_]+):(\d+)>'

        def emoji_replacement(match):
            animated = match.group(1) == 'a'  # Check if the emoji is animated
            emoji_name = match.group(2)
            emoji_id = match.group(3)
            emoji_tag = f"<:{emoji_name}:{emoji_id}>"

            # Ensure the emoji is standalone
            if is_standalone_emoji(emoji_tag, content):
                # Replace the emoji with its URL
                return f"https://cdn.discordapp.com/emojis/{emoji_id}.{'gif' if animated else 'png'}"
            else:
                # If not standalone, return the emoji tag as is
                return emoji_tag

        # Replace custom emojis with their image URLs
        return re.sub(custom_emoji_pattern, emoji_replacement, content)

    # Webhook sending logic
    async with aiohttp.ClientSession() as session:
        for channel_id, webhook_url in connected_channels:
            try:
                if str(channel_id) == str(message.channel.id):
                    continue  # Skip the same channel
                
                guild = await bot.fetch_guild(message.guild.id)
                webhook = discord.Webhook.from_url(webhook_url, session=session)
                
                # Prepare the webhook message dictionary
                send_kwargs = {
                    "username": f"{message.author.global_name or message.author.name} || {guild.name}",
                    "avatar_url": str(message.author.avatar) if message.author.avatar else None,
                    "embeds": [],
                    "files": [],  # Ensure files list is initialized
                    "content": message.content,  # Start with original content
                }

                # Replace custom emoji tags with their image URLs in the content
                replaced_content = replace_emoji_with_url(message.content)

                # Update content with replaced emoji URLs
                send_kwargs["content"] = replaced_content

                # Append the fileBytes if there are any attachments
                if fileBytes:
                    send_kwargs["files"] = [discord.File(BytesIO(file[0]), file[1]) for file in fileBytes]

                if reply_embed:
                    send_kwargs["embeds"].append(reply_embed)

                # Send the message via webhook
                await webhook.send(**send_kwargs)

            except Exception as e:
                continue

    await bot.process_commands(message)

def replaceEmoji(text):
    for key in emojiReplace.keys():
        text = text.replace(key, emojiReplace[key])
    return text

#@bot.command()
#async def level(ctx):
#    exp, level = get_user_data(ctx.author.id)
#    await ctx.send(f"{ctx.author.mention}, you are level {level} with {exp} XP.")

def get_help_message(client, message):
    helpMessage = f"""**My Current Prefix is: `{get_prefix(bot, message)}` \n1. {get_prefix(bot, message)}info [event, lvling, foodbuff, mats]
2. {get_prefix(bot, message)}regislet all/Regislet Name
3. {get_prefix(bot, message)}prefix [Prefix You Want] (ADMIN ONLY)
4. {get_prefix(bot, message)}list (ADMIN ONLY)
5. {get_prefix(bot, message)}join #Channel [ROOM] (ADMIN ONLY)
6. {get_prefix(bot, message)}create [RoomName] (ADMIN ONLY)
    **"""
    return helpMessage
class SecondEventDropdown(discord.ui.Select):
    def __init__(self, infoType, user, Type=None):
        self.user = user
        self.info = infoType
        self.ActionType = Type
        optionss = []
        for key in infomation[self.ActionType][infoType.lower()]:
            optionss.append(discord.SelectOption(label=key.title(), value=key.lower()))
        super().__init__(placeholder="Choose Kind Of Info You Want To See", options=optionss)
    async def interaction_check(self, interaction: discord.Interaction):
        return self.user.id == interaction.user.id
    async def callback(self, interaction: discord.Interaction):
        data = infomation[self.ActionType][(self.info).lower()][self.values[0].lower()]
        messageDescripton =  replaceEmoji(data['message'])
        em = discord.Embed(title=f"**{self.values[0].title()}**",description=messageDescripton, color=discord.Color.blue())
        em.set_author(name="Phoenix Bloodline")
        if len(data['footer'])>0: 
            footermsg = (self.info).title()+"\n"+data['footer']
            em.set_footer(text=f"{footermsg}")
        if len(data['image'])>0: em.set_image(url=data['image'])
        em.set_thumbnail(url="https://cdn.discordapp.com/icons/875310053257777152/2f50786dd6d1665a01fe12f60e412de1.webp?size=96") 
        await interaction.response.edit_message(embed=em)

class FirstEventDropdown(discord.ui.Select):
    def __init__(self, infoType, user):
        self.user = user
        self.info = infoType
        optionss = []
        for key in infomation[infoType].keys():
            optionss.append(discord.SelectOption(label=key.title(), value=key.lower()))
        super().__init__(placeholder=f"Choose {infoType.title()} You Want To See", options=optionss)
    async def interaction_check(self, interaction: discord.Interaction):
        return self.user.id == interaction.user.id
    async def callback(self, interaction: discord.Interaction):
        if self.info in ["event", "mats"]:
            self.view.add_item(SecondEventDropdown(self.values[0],self.user, self.info))
            if len(self.view.children) == 3:
                self.view.remove_item(self.view.children[1])
            await interaction.response.edit_message(embed=None,view=self.view)
        else:
            data = infomation[self.info][self.values[0]]
            messageDescripton =  replaceEmoji(data['message'])
            print(len(messageDescripton))
            em = discord.Embed(title=f"**{self.values[0].title()}**",description=messageDescripton, color=discord.Color.blue())
            em.set_author(name="Phoenix Bloodline")
            if len(data['footer'])>0: 
                footermsg = (self.info).title()+"\n"+data['footer']
                em.set_footer(text=f"{footermsg}")
            if len(data['image'])>0: em.set_image(url=data['image'])
            em.set_thumbnail(url="https://cdn.discordapp.com/icons/875310053257777152/2f50786dd6d1665a01fe12f60e412de1.webp?size=96") 
            await interaction.response.edit_message(embed=em)
class EventView(discord.ui.View):
    def __init__(self, infotype, user):
        super().__init__()
        self.user = user
        self.add_item(FirstEventDropdown(infotype, self.user))
    async def interaction_check(self, interaction: discord.Interaction):
        return self.user.id == interaction.user.id


class regisletAllView(discord.ui.View):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.currentPage = 1
    async def interaction_check(self, interaction: discord.Interaction):
        return self.user.id == interaction.user.id
    @discord.ui.button(label="◄", style = discord.ButtonStyle.primary)
    async def goPrev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.currentPage -= 1
        if self.currentPage <= 0:
            self.currentPage = 1
        if (0+(10*(self.currentPage))) >= len(regisletInfo):
            maxrecord = len(regisletInfo)
        else:
            maxrecord = (0+(10*(self.currentPage)))
        minrecord = (0+(10*(self.currentPage-1)))
        RegisletKey = [key for key in regisletInfo.keys()]
        totalText = ""
        for i in range(minrecord, maxrecord):
            totalText += f"### {RegisletKey[i]} :REGISLET:\n**- Max Level: " + str(regisletInfo[RegisletKey[i]]["maxLevel"]) + "\n- Effect: " + regisletInfo[RegisletKey[i]]["description"] + "\n- Can Get In Stoodie: " + str(regisletInfo[RegisletKey[i]]["level"]) + "**\n"
        totalText = replaceEmoji(totalText)
        em = discord.Embed(title=f"All Regislet",description=totalText, color=discord.Color.blue())
        em.set_footer(text=f"{self.currentPage}/{int(round((len(regisletInfo)/10+0.5),0))}")
        await interaction.response.edit_message(embed=em)
        
    @discord.ui.button(label="►", style = discord.ButtonStyle.primary)
    async def goNext(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.currentPage += 1
        if self.currentPage > round((len(regisletInfo)/10+0.5),0):
            self.currentPage = 1
        if (0+(10*(self.currentPage))) >= len(regisletInfo):
            maxrecord = len(regisletInfo)
        else:
            maxrecord = (0+(10*(self.currentPage)))
        minrecord = (0+(10*(self.currentPage-1)))
        
        RegisletKey = [key for key in regisletInfo.keys()]
        totalText = ""
        for i in range(minrecord, maxrecord):
            totalText += f"### {RegisletKey[i]} :REGISLET:\n**- Max Level: " + str(regisletInfo[RegisletKey[i]]["maxLevel"]) + "\n- Effect: " + regisletInfo[RegisletKey[i]]["description"] + "\n- Can Get In Stoodie: " + str(regisletInfo[RegisletKey[i]]["level"]) + "**\n"
        totalText = replaceEmoji(totalText)
        em = discord.Embed(title=f"All Regislet",description=totalText, color=discord.Color.blue())
        em.set_footer(text=f"{self.currentPage}/{int(round((len(regisletInfo)/10+0.5),0))}")
        await interaction.response.edit_message(embed=em)
class regisletChooseView(discord.ui.View):
    def __init__(self, data, user):
        self.user = user
        super().__init__()
        self.add_item(regisletChoose(data, self.user))
    async def interaction_check(self, interaction: discord.Interaction):
        return self.user.id == interaction.user.id
        
class regisletChoose(discord.ui.Select):
    def __init__(self, data, user):
        self.user = user
        optionss = []
        for regislet in data:
            optionss.append(discord.SelectOption(label=regislet, value=regislet))
        super().__init__(placeholder=f"Choose Regislet You Want To See", options=optionss)
    async def interaction_check(self, interaction: discord.Interaction):
        return self.user.id == interaction.user.id
    async def callback(self, interaction: discord.Interaction):
        regislet = self.values[0]
        text = f"**- Max Level: " + str(regisletInfo[regislet]["maxLevel"]) + "\n- Effect: " + regisletInfo[regislet]["description"] + "\n- Can Get In Stoodie: " + str(regisletInfo[regislet]["level"]) + "**"
        em = discord.Embed(title=f"{regislet}",description=text, color=discord.Color.blue())
        await interaction.response.edit_message(embed=em)
    
async def checkMember(ctx):
    roles = [y.name.lower() for y in ctx.message.author.roles]
    if 'member' not in roles:
        await ctx.send(f"<@{ctx.message.author.id}> You Are Not A Member")
        return False
    return True
@bot.command(administrator=True)
async def ignore(ctx, *, id):
    print(id)
    #await ctx.channel.send(f"IGNORED <@{id}>")
@bot.command(administrator=True)    
async def create(ctx, *, roomName=""):
    if not roomName:
        await ctx.send("Please specify a room name.")
        return

    create_room(roomName)
    await ctx.send(f"Room `{roomName}` created.")

@bot.command(administrator=True)
async def list(ctx):
    rooms = list_rooms()
    if not rooms:
        await ctx.send("No rooms found.")
        return

    desc = ""
    for i, (name, count) in enumerate(rooms, 1):
        desc += f"**{i}. {name} ({count}/10)**\n\n"

    embed = discord.Embed(title="List of Linked Rooms", description=desc, color=discord.Color.blue())
    await ctx.send(embed=embed)

@bot.command(administrator=True)
async def join(ctx, args="", *, room=""):
    if not args or not room:
        await ctx.send(f"Usage: `{get_prefix(bot, ctx)}join #channel room_name`")
        return

    try:
        channel_id = args.strip()[2:-1]
        room_id = room_exists(room)

        if not room_id:
            await ctx.send(f"Room `{room}` does not exist.")
            return

        channel = await bot.fetch_channel(channel_id)
        webhook = await channel.create_webhook(name=f"{room}_webhook")

        add_channel_to_room(room, channel_id, webhook.url)
        await ctx.send(f"Channel {args} connected to `{room}`.")
    except Exception as e:
        await ctx.send(f"Error: {str(e)}")
@bot.command()
async def regislet(ctx, *, args="None"):
    #if not (await checkMember(ctx)): return
    if args=="None": 
        await ctx.send(f"Please Use Command With Info You Need: `{get_prefix(bot, ctx)}regislet all/Regislet Name`")
        return
    regisletName = [name for name in regisletInfo.keys()]
    argsLower = args.lower()
    if argsLower == "all": 
        view = regisletAllView(ctx.message.author)
        RegisletKey = [key for key in regisletInfo.keys()]
        totalText = ""
        for i in range(0, 10):
            totalText += f"### {RegisletKey[i]} :REGISLET:\n**- Max Level: " + str(regisletInfo[RegisletKey[i]]["maxLevel"]) + "\n- Effect: " + regisletInfo[RegisletKey[i]]["description"] + "\n- Can Get In Stoodie: " + str(regisletInfo[RegisletKey[i]]["level"]) + "**\n"
        totalText = replaceEmoji(totalText)
        em = discord.Embed(title=f"All Regislet",description=totalText, color=discord.Color.blue())
        em.set_footer(text=f"1/{int(round((len(regisletInfo)/10+0.5),0))}")
        await ctx.send(view=view,embed=em, delete_after=180)
    else:
        count = 0
        for name in regisletName:
            if argsLower not in name.lower(): continue
            count+=1
        if count == 0:
            await ctx.send(f"Cannot Find Info About {args} Regislet", delete_after=7)
            return
        elif count == 1:
            regislet = ""
            for name in regisletName:
                if argsLower in name.lower():
                    regislet = name
            text = f"**- Max Level: " + str(regisletInfo[regislet]["maxLevel"]) + "\n- Effect: " + regisletInfo[regislet]["description"] + "\n- Can Get In Stoodie: " + str(regisletInfo[regislet]["level"]) + "**"
            em = discord.Embed(title=f"{regislet}",description=text, color=discord.Color.blue())
            await ctx.send(embed=em, delete_after=180)
        else:
            data = []
            for name in regisletName:
                if argsLower in name.lower(): data.append(name)
            view = regisletChooseView(data, ctx.message.author)
            await ctx.send(view=view, delete_after=180)

@bot.command()
async def refresh(ctx):
    global config_location, infomation, emojiReplace, regisletInfo, globalChatID
    if str(ctx.message.author.id) not in config_location["Owner"]: return
    try:
        #LOAD JSON FILE
        config_location = fileIO("config/config.json", "load") 
        infomation = fileIO("config/infomation.json", "load")
        emojiReplace = fileIO("config/emoji_id.json", "load") 
        regisletInfo = fileIO("config/regislet.json", "load")
        stattingDB = fileIO("config/stattingDB.json", "load") 
        globalChatID = fileIO("config/global_chat_guild_id.json", "load")
        await ctx.send("DATA REFRESHED")
        
    except Exception as err:
        await print(err)

@bot.command()
async def help(ctx):
    #if not (await checkMember(ctx)): return
    message = get_help_message(bot, ctx)
    em = discord.Embed(title=f"**Commands List**",description=message, color=discord.Color.blue())
    await ctx.send(embed=em)
    
@bot.command()
async def board(ctx):
    descriptionText = "**1B823A - Tame a pet level 55**\n- Reward: 100 Spinas"
    em = discord.Embed(title=f"**QUEST BOARD**",description=descriptionText, color=discord.Color.blue())
    em.set_author(name="Phoenix Bloodline")
    await ctx.send(embed=em)
@bot.command()
async def quest(ctx):
    descriptionText = "You don't have any ongoing quest"
    em = discord.Embed(title=f"**QUEST RECEIVED**",description=descriptionText, color=discord.Color.blue())
    em.set_author(name="Phoenix Bloodline")
    await ctx.send(embed=em)
@bot.command(pass_context=True)
@has_permissions(administrator=True)
async def prefix(ctx, prefix=None):
    #if not (await checkMember(ctx)): return
    prefix = prefix.replace(" ", "")
    save_prefix(prefix, ctx)
    await ctx.send(f"Prefix Changed To **{get_prefix(bot, ctx)}**")
    return
#@bot.command(pass_context=True)
#async def fill(ctx, *, requirement):
#    SplitStats = requirement.split("/")
#    finalRequirement = [stat.split(" ") for stat in SplitStats]
#    
#    #GATHER INFORMATION FROM MSG
#    filltype = str(finalRequirement.pop(0)[0]).lower()
#    pot_original = finalRequirement.pop(0)[1]
#    prof_level = finalRequirement.pop(0)[1]
#    positive = []
#    negative = []
#    for i in range(len(finalRequirement)):
#        if float(finalRequirement[i][1])>0:
#            positive.append(finalRequirement[i])
#        else:
#            negative.append(finalRequirement[i])
#            
#    
#    highest_mats_per_step = 0
#    
#    #CALC REDUCTION VALUE(DEFAULT PROF-10%)
#    mats_reduction_overall = (1-((math.round(prof_level / 10) + math.round(prof_level / 50)) / 100)) * 0.9
#    
#    
#    print(filltype, pot_original, prof_level, finalRequirement)
#    print(positive)
#    print(negative)
@bot.command(pass_context=True)
async def info(ctx, infotype=None):
    #if not (await checkMember(ctx)): return
    view = None
    em = None
    listcommand = ["event", "lvling", "foodbuff", "mats", "regislet"]
    if infotype==None or infotype not in listcommand: 
        await ctx.send(f"<@{ctx.message.author.id}> Please use command with info you need \n`{get_prefix(bot, ctx)}info [event, lvling, foodbuff, mats, regislet]`")
        return
    
    """if infotype == "lvling":
        em = discord.Embed(title=f"**Leveling Guide**",description=infomation["lvling"]["message"], color=discord.Color.blue())
        em.set_author(name="Phoenix Bloodline")
        if len(infomation["lvling"]['footer'])>0: 
            footermsg = "Leveling\n"+infomation["lvling"]['footer']
            em.set_footer(text=f"{footermsg}")
        if len(infomation["lvling"]['image'])>0: em.set_image(url=infomation["lvling"]['image'])
        em.set_thumbnail(url="https://cdn.discordapp.com/icons/875310053257777152/2f50786dd6d1665a01fe12f60e412de1.webp?size=96") 
    else:"""
    view = EventView(infotype, ctx.message.author)
    msg = await ctx.send(f"<@{ctx.message.author.id}> {infotype.title()} Info",view=view,embed=em, delete_after=180)
    await msg.add_reaction("❌")
    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) == "❌" and reaction.message.id == msg.id  #<---- The check performed
    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=180.0, check=check) #<--- Waiting for the reaction
        await msg.delete()
    except asyncio.TimeoutError:  #<---- If the user doesn't respond
        pass
def run_bot():
    TOKEN = os.environ.get("TOKEN")  # or hardcode temporarily for testing

    if not TOKEN:
        print("Missing TOKEN in environment variables.")
        return

    try:
        bot.run(TOKEN)
    except Exception as e:
        print(f"Error starting bot: {e}")


# ========== Main Start ==========
if __name__ == '__main__':
    # Start the Flask keep-alive server in a thread
    Thread(target=keep_alive).start()

    # Run the bot in the main thread (important!)
    run_bot()
