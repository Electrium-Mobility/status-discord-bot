import discord
import gspread
from discord.ext import commands, tasks
from dotenv import load_dotenv
import os
import asyncio
from oauth2client.service_account import ServiceAccountCredentials

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")

# Check environment variables
if not TOKEN:
    print("❌ Error: DISCORD_TOKEN not found in .env")
    exit(1)
if not SHEET_ID:
    print("❌ Error: SHEET_ID not found in .env")
    exit(1)

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID).worksheet("Sheet1")

# Discord bot setup
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"{bot.user.name} is connected!")
    auto_sync_roles.start()

@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

@bot.command()
async def checkapps(ctx):
    rows = sheet.get_all_records()
    await ctx.send(f"Found {len(rows)} applications.")
    
    if rows:
        latest = rows[-1]
        try:
            await ctx.send(f"Latest applicant: {latest['First Name']} {latest['Last Name']} - {latest['Role']}")
        except KeyError:
            await ctx.send("❌ Could not find proper column headers like 'First Name', 'Last Name', 'Role'.")

@bot.command(name="sync_roles")
@commands.has_permissions(manage_roles=True)
async def sync_roles(ctx):
    await ctx.send("🔄 Syncing roles...")
    guild = ctx.guild
    data = sheet.get_all_records()

    for entry in data:
        username = entry.get("Discord Username")
        status = entry.get("Status")

        if not username or not status:
            continue

        member = discord.utils.get(guild.members, name=username)
        if not member:
            print(f"❌ Member not found: {username}")
            continue

        role = discord.utils.get(guild.roles, name=status)
        if role:
            # Check if user already has the correct role
            if role in member.roles:
                print(f"⏭️ {username} already has {role.name} role, skipping")
                continue
            
            # Remove all status roles first to avoid multiple roles
            status_roles = ["Incoming", "Active", "Previous"]
            for status_role_name in status_roles:
                status_role = discord.utils.get(guild.roles, name=status_role_name)
                if status_role and status_role in member.roles:
                    await member.remove_roles(status_role)
            
            # Add new role
            await member.add_roles(role)
            print(f"✅ Assigned {role.name} to {username}")
        else:
            print(f"❌ Role not found: {status}")

    await ctx.send("✅ Role sync complete.")

@bot.command(name="promote")
@commands.has_permissions(manage_roles=True)
async def promote(ctx):
    await ctx.send("🔁 Promoting roles: Incoming → Active, Active → Previous...")
    
    # First sync with Google Sheet to ensure consistency
    await ctx.send("📋 Syncing with Google Sheet first...")
    
    # Call sync_roles function to ensure consistency
    await sync_roles(ctx)
    
    await ctx.send("✅ Pre-sync complete. Now promoting roles...")

    guild = ctx.guild
    incoming_role = discord.utils.get(guild.roles, name="Incoming")
    active_role = discord.utils.get(guild.roles, name="Active")
    previous_role = discord.utils.get(guild.roles, name="Previous")

    # Track changes for sheet updates
    sheet_updates = []

    for member in guild.members:
        member_updated = False
        
        # Previous role users remain unchanged
        if previous_role in member.roles:
            print(f"{member.name}: Previous (no change)")
            continue

        if active_role in member.roles:
            await member.remove_roles(active_role)
            await member.add_roles(previous_role)
            print(f"{member.name}: Active → Previous")
            # Update sheet: Active → Previous
            sheet_updates.append((member.name, "Previous"))
            member_updated = True

        if incoming_role in member.roles:
            await member.remove_roles(incoming_role)
            await member.add_roles(active_role)
            print(f"{member.name}: Incoming → Active")
            # Update sheet: Incoming → Active
            sheet_updates.append((member.name, "Active"))
            member_updated = True

    # Update Google Sheet
    if sheet_updates:
        await ctx.send("📝 Updating Google Sheet...")
        sheet_success = False
        try:
            # Find the Status column
            headers = sheet.row_values(1)
            status_col = None
            discord_col = None
            
            for i, header in enumerate(headers):
                if header.lower() in ['status', 'state']:
                    status_col = i + 1  # gspread uses 1-indexed
                if header.lower() in ['discord username', 'discord', 'username']:
                    discord_col = i + 1
            
            if status_col and discord_col:
                # Get all Discord usernames at once to avoid multiple API calls
                discord_values = sheet.col_values(discord_col)
                
                for discord_name, new_status in sheet_updates:
                    # Find the row with this Discord username
                    try:
                        # Find the row number for this Discord username
                        for row_num, cell_value in enumerate(discord_values, 1):
                            if cell_value.strip().lower() == discord_name.lower():
                                # Update the status in that row
                                sheet.update_cell(row_num, status_col, new_status)
                                print(f"📝 Updated sheet: {discord_name} → {new_status}")
                                break
                    except Exception as e:
                        print(f"❌ Error updating sheet for {discord_name}: {e}")
                        await ctx.send(f"⚠️ Failed to update sheet for {discord_name}: Network error")
                
                sheet_success = True
            else:
                await ctx.send("❌ Could not find 'Status' or 'Discord Username' columns in sheet")
                
        except Exception as e:
            await ctx.send(f"❌ Error updating Google Sheet: Network timeout or connection error")
            print(f"Sheet update error: {e}")
        
        if sheet_success:
            await ctx.send("✅ Role promotion and sheet update complete.")
        else:
            await ctx.send("⚠️ Role promotion completed, but sheet update failed. Please check manually.")
    else:
        await ctx.send("✅ Role promotion complete (no changes needed).")

@bot.command(name="setstatus")
@commands.has_permissions(manage_roles=True)
async def setstatus(ctx, member: discord.Member, status: str):
    """Set a member's status and update both Discord role and Google Sheet"""
    await ctx.send(f"🔄 Setting {member.name} status to {status}...")
    
    # Update Discord role
    guild = ctx.guild
    role = discord.utils.get(guild.roles, name=status)
    
    if role:
        # Remove all status roles first
        status_roles = ["Incoming", "Active", "Previous"]
        for status_role_name in status_roles:
            status_role = discord.utils.get(guild.roles, name=status_role_name)
            if status_role and status_role in member.roles:
                await member.remove_roles(status_role)
        
        # Add new role
        await member.add_roles(role)
        print(f"✅ Assigned {role.name} to {member.name}")
        
        # Update Google Sheet
        try:
            headers = sheet.row_values(1)
            status_col = None
            discord_col = None
            
            for i, header in enumerate(headers):
                if header.lower() in ['status', 'state']:
                    status_col = i + 1
                if header.lower() in ['discord username', 'discord', 'username']:
                    discord_col = i + 1
            
            if status_col and discord_col:
                discord_values = sheet.col_values(discord_col)
                
                user_found = False
                for row_num, cell_value in enumerate(discord_values, 1):
                    if cell_value.strip().lower() == member.name.lower():
                        sheet.update_cell(row_num, status_col, status)
                        print(f"📝 Updated sheet: {member.name} → {status}")
                        await ctx.send(f"✅ Updated {member.name} status to {status} in both Discord and sheet!")
                        user_found = True
                        break
                
                if not user_found:
                    # Add new user to sheet with known information
                    next_row = len(discord_values) + 1
                    sheet.update_cell(next_row, discord_col, member.name)
                    sheet.update_cell(next_row, status_col, status)
                    print(f"📝 Added new user to sheet: {member.name} → {status}")
                    await ctx.send(f"✅ Updated {member.name} status to {status} in Discord and added to sheet!\n⚠️ **Please complete the remaining information for {member.name} in the Google Sheet.**")
            else:
                await ctx.send("❌ Could not find 'Status' or 'Discord Username' columns in sheet")
                
        except Exception as e:
            await ctx.send(f"❌ Error updating Google Sheet: {e}")
            print(f"Sheet update error: {e}")
    else:
        await ctx.send(f"❌ Role '{status}' not found. Available roles: {[r.name for r in guild.roles if r.name in ['Incoming', 'Active', 'Previous']]}")

@tasks.loop(hours=24)
async def auto_sync_roles():
    await bot.wait_until_ready()
    print("🔁 Auto-sync running...")
    for guild in bot.guilds:
        data = sheet.get_all_records()
        for entry in data:
            username = entry.get("Discord Username")
            status = entry.get("Status")

            if not username or not status:
                continue

            member = discord.utils.get(guild.members, name=username)
            if not member:
                print(f"❌ Member not found (auto): {username}")
                continue

            role = discord.utils.get(guild.roles, name=status)
            if role:
                # Check if user already has the correct role
                if role in member.roles:
                    print(f"⏭️ [Auto] {username} already has {role.name} role, skipping")
                    continue
                
                # Remove all status roles first to avoid multiple roles
                status_roles = ["Incoming", "Active", "Previous"]
                for status_role_name in status_roles:
                    status_role = discord.utils.get(guild.roles, name=status_role_name)
                    if status_role and status_role in member.roles:
                        await member.remove_roles(status_role)
                
                # Add new role
                await member.add_roles(role)
                print(f"✅ [Auto] Assigned {role.name} to {username}")
            else:
                print(f"❌ [Auto] Role not found: {status}")

@bot.command(name="who-intersection")
@commands.has_permissions(manage_roles=True)
async def who_intersection(ctx, role1_name: str, role2_name: str):
    """How many members have both specified roles"""
    guild = ctx.guild
    
    # Find the roles
    role1 = discord.utils.get(guild.roles, name=role1_name)
    role2 = discord.utils.get(guild.roles, name=role2_name)
    
    if not role1:
        await ctx.send(f"❌ Role '{role1_name}' not found")
        return
    
    if not role2:
        await ctx.send(f"❌ Role '{role2_name}' not found")
        return
    
    # Find intersection of members with both roles
    intersection_number = 0
    for member in guild.members:
        if role1 in member.roles and role2 in member.roles:
            intersection_number += 1
    
    if intersection_number == 0:
        await ctx.send(f"📭 No members found with both '{role1_name}' and '{role2_name}' roles")
        return
    
    await ctx.send(f"👥 **{intersection_number}** members have both {role1_name} and {role2_name} roles")
    
    print(f"✅ Listed {intersection_number} members with roles {role1_name} & {role2_name}")

@bot.command(name="ping-intersection")
@commands.has_permissions(manage_roles=True)
async def ping_intersection(ctx, role1_name: str, role2_name: str):
    """Mention members who have both specified roles"""
    guild = ctx.guild
    
    # Find the roles
    role1 = discord.utils.get(guild.roles, name=role1_name)
    role2 = discord.utils.get(guild.roles, name=role2_name)
    
    if not role1:
        await ctx.send(f"❌ Role '{role1_name}' not found")
        return
    
    if not role2:
        await ctx.send(f"❌ Role '{role2_name}' not found")
        return
    
    # Find intersection of members with both roles
    intersection_members = []
    for member in guild.members:
        if role1 in member.roles and role2 in member.roles:
            intersection_members.append(member)
    
    if not intersection_members:
        await ctx.send(f"📭 No members found with both '{role1_name}' and '{role2_name}' roles")
        return
    
    # Create mention string
    mentions = " ".join([member.mention for member in intersection_members])
    
    # Send message with mentions
    await ctx.send(f"🔔 **Pinging members with both {role1_name} and {role2_name} roles:**\n{mentions}")
    
    print(f"✅ Pinged {len(intersection_members)} members with roles {role1_name} & {role2_name}")

bot.run(TOKEN)
