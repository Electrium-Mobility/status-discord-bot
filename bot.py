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
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME" )

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
sheet = client.open_by_key(SHEET_ID).worksheet(WORKSHEET_NAME)

# Discord bot setup
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ {bot.user} has connected to Discord!")
    print(f"📊 Bot is in {len(bot.guilds)} guilds")
    
    # Sync slash commands with Discord
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")
    
    # Start the auto sync task
    auto_sync_roles.start()

@bot.tree.command(name="ping", description="Test if the bot is responding")
async def ping_slash(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!")

@bot.tree.command(name="checkapps", description="Check the number of applications in the Google Sheet")
async def checkapps_slash(interaction: discord.Interaction):
    rows = sheet.get_all_records()
    await interaction.response.send_message(f"Found {len(rows)} applications.")
    
    if rows:
        latest = rows[-1]
        try:
            await interaction.followup.send(f"Latest applicant: {latest['First Name']} {latest['Last Name']} - {latest['Role']}")
        except KeyError:
            await interaction.followup.send("❌ Could not find proper column headers like 'First Name', 'Last Name', 'Role'.")

@bot.tree.command(name="sync_roles", description="Sync Discord roles with Google Sheet data")
@discord.app_commands.default_permissions(manage_roles=True)
async def sync_roles_slash(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Syncing roles...")
    await _sync_roles_internal(interaction.guild)
    await interaction.followup.send("✅ Role sync complete.")

async def _sync_roles_internal(guild):
    """Internal function to sync roles without interaction responses"""
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

@bot.tree.command(name="promote", description="Promote all Active members to Previous and Incoming to Active")
@discord.app_commands.default_permissions(manage_roles=True)
async def promote_slash(interaction: discord.Interaction):
    await interaction.response.send_message("🔁 Promoting roles: Incoming → Active, Active → Previous...")
    
    # First sync with Google Sheet to ensure consistency
    await interaction.followup.send("📋 Syncing with Google Sheet first...")
    
    # Call sync_roles function to ensure consistency
    await _sync_roles_internal(interaction.guild)
    
    await interaction.followup.send("✅ Pre-sync complete. Now promoting roles...")

    guild = interaction.guild
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
        await interaction.followup.send("📝 Updating Google Sheet...")
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
                        await interaction.followup.send(f"⚠️ Failed to update sheet for {discord_name}: Network error")
                
                sheet_success = True
            else:
                await interaction.followup.send("❌ Could not find 'Status' or 'Discord Username' columns in sheet")
                
        except Exception as e:
            await interaction.followup.send(f"❌ Error updating Google Sheet: Network timeout or connection error")
            print(f"Sheet update error: {e}")
        
        if sheet_success:
            await interaction.followup.send("✅ Role promotion and sheet update complete.")
        else:
            await interaction.followup.send("⚠️ Role promotion completed, but sheet update failed. Please check manually.")
    else:
        await interaction.followup.send("✅ Role promotion complete (no changes needed).")

@bot.tree.command(name="setstatus", description="Set a member's status and update both Discord role and Google Sheet")
@discord.app_commands.default_permissions(manage_roles=True)
async def setstatus_slash(interaction: discord.Interaction, member: discord.Member, status: str):
    """Set a member's status and update both Discord role and Google Sheet"""
    await interaction.response.send_message(f"🔄 Setting {member.mention}'s status to {status}...")
    
    guild = interaction.guild
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
                        await interaction.followup.send(f"✅ Updated {member.name} status to {status} in both Discord and sheet!")
                        user_found = True
                        break
                
                if not user_found:
                    # Add new user to sheet with known information
                    next_row = len(discord_values) + 1
                    sheet.update_cell(next_row, discord_col, member.name)
                    sheet.update_cell(next_row, status_col, status)
                    print(f"📝 Added new user to sheet: {member.name} → {status}")
                    await interaction.followup.send(f"✅ Updated {member.name} status to {status} in Discord and added to sheet!\n⚠️ **Please complete the remaining information for {member.name} in the Google Sheet.**")
            else:
                await interaction.followup.send("❌ Could not find 'Status' or 'Discord Username' columns in sheet")
                
        except Exception as e:
            await interaction.followup.send(f"❌ Error updating Google Sheet: {e}")
            print(f"Sheet update error: {e}")
    else:
        await interaction.followup.send(f"❌ Role '{status}' not found. Available roles: {[r.name for r in guild.roles if r.name in ['Incoming', 'Active', 'Previous']]}")

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

@bot.tree.command(name="who-intersection", description="Find members who have both specified roles")
@discord.app_commands.default_permissions(manage_roles=True)
async def who_intersection_slash(interaction: discord.Interaction, role1_name: str, role2_name: str):
    """Find members who have both specified roles"""
    guild = interaction.guild
    
    # Find the roles
    role1 = discord.utils.get(guild.roles, name=role1_name)
    role2 = discord.utils.get(guild.roles, name=role2_name)
    
    if not role1:
        await interaction.response.send_message(f"❌ Role '{role1_name}' not found")
        return
    
    if not role2:
        await interaction.response.send_message(f"❌ Role '{role2_name}' not found")
        return
    
    # Find intersection of members with both roles
    intersection_number = 0
    for member in guild.members:
        if role1 in member.roles and role2 in member.roles:
            intersection_number += 1
    
    if intersection_number == 0:
        await interaction.response.send_message(f"📭 No members found with both '{role1_name}' and '{role2_name}' roles")
        return
    
    await interaction.response.send_message(f"👥 **{intersection_number}** members have both {role1_name} and {role2_name} roles")
    
    print(f"✅ Listed {intersection_number} members with roles {role1_name} & {role2_name}")

@bot.tree.command(name="ping-intersection", description="Mention members who have both specified roles")
@discord.app_commands.default_permissions(manage_roles=True)
async def ping_intersection_slash(interaction: discord.Interaction, role1_name: str, role2_name: str):
    """Mention members who have both specified roles"""
    guild = interaction.guild
    
    # Find the roles
    role1 = discord.utils.get(guild.roles, name=role1_name)
    role2 = discord.utils.get(guild.roles, name=role2_name)
    
    if not role1:
        await interaction.response.send_message(f"❌ Role '{role1_name}' not found")
        return
    
    if not role2:
        await interaction.response.send_message(f"❌ Role '{role2_name}' not found")
        return
    
    # Find intersection of members with both roles
    intersection_members = []
    for member in guild.members:
        if role1 in member.roles and role2 in member.roles:
            intersection_members.append(member)
    
    if not intersection_members:
        await interaction.response.send_message(f"📭 No members found with both '{role1_name}' and '{role2_name}' roles")
        return
    
    # Create mention string
    mentions = " ".join([member.mention for member in intersection_members])
    
    # Send message with mentions
    await interaction.response.send_message(f"🔔 **Pinging members with both {role1_name} and {role2_name} roles:**\n{mentions}")
    
    print(f"✅ Pinged {len(intersection_members)} members with roles {role1_name} & {role2_name}")

@bot.tree.command(name="check-sheet-members", description="Check if Google Sheet members are in Discord server")
@discord.app_commands.default_permissions(manage_roles=True)
async def check_sheet_members_slash(interaction: discord.Interaction):
    """Check if all members from Google Sheet are present in the Discord server"""
    try:
        await interaction.response.defer()
    except discord.errors.NotFound:
        # Interaction token expired, try to send a regular response
        return
    
    guild = interaction.guild
    
    try:
        # Get all data from the Google Sheet
        all_records = sheet.get_all_records()
        
        # Get Discord server members
        discord_members = {member.name.lower(): member for member in guild.members}
        discord_display_names = {member.display_name.lower(): member for member in guild.members}
        
        # Lists to track results
        found_members = []
        missing_members = []
        empty_username_rows = []
        
        print("🔍 Starting Google Sheet member check...")
        print(f"📊 Total records in sheet: {len(all_records)}")
        print(f"👥 Total Discord members: {len(guild.members)}")
        
        # Check each person in the sheet
        for i, record in enumerate(all_records, start=2):  # Start from row 2 (accounting for header)
            first_name = record.get('First Name', '').strip()
            last_name = record.get('Last Name', '').strip()
            discord_username = record.get('Discord Username', '').strip()
            
            if not discord_username:
                empty_username_rows.append({
                    'row': i,
                    'name': f"{first_name} {last_name}",
                    'first_name': first_name,
                    'last_name': last_name
                })
                continue
            
            # Try to find the member in Discord
            found = False
            matched_member = None
            
            # Check by exact username match (case insensitive)
            if discord_username.lower() in discord_members:
                found = True
                matched_member = discord_members[discord_username.lower()]
            # Check by display name match (case insensitive)
            elif discord_username.lower() in discord_display_names:
                found = True
                matched_member = discord_display_names[discord_username.lower()]
            
            if found:
                found_members.append({
                    'row': i,
                    'name': f"{first_name} {last_name}",
                    'discord_username': discord_username,
                    'matched_member': matched_member
                })
                print(f"✅ Found: {first_name} {last_name} ({discord_username}) -> {matched_member.display_name}")
            else:
                missing_members.append({
                    'row': i,
                    'name': f"{first_name} {last_name}",
                    'discord_username': discord_username
                })
                print(f"❌ Missing: {first_name} {last_name} ({discord_username})")
        
        # Print summary to console
        print("\n" + "="*50)
        print("📋 GOOGLE SHEET MEMBER CHECK SUMMARY")
        print("="*50)
        print(f"✅ Found in Discord: {len(found_members)}")
        print(f"❌ Missing from Discord: {len(missing_members)}")
        print(f"⚠️  Empty Discord Username: {len(empty_username_rows)}")
        print(f"📊 Total processed: {len(all_records)}")
        
        if missing_members:
            print(f"\n❌ MISSING MEMBERS ({len(missing_members)}):")
            for member in missing_members:
                print(f"   Row {member['row']}: {member['name']} ({member['discord_username']})")
        
        if empty_username_rows:
            print(f"\n⚠️  EMPTY DISCORD USERNAME ({len(empty_username_rows)}):")
            for member in empty_username_rows:
                print(f"   Row {member['row']}: {member['name']}")
        
        print("="*50)
        
        # Send summary to Discord
        summary_msg = f"📋 **Google Sheet Member Check Complete**\n"
        summary_msg += f"✅ Found in Discord: **{len(found_members)}**\n"
        summary_msg += f"❌ Missing from Discord: **{len(missing_members)}**\n"
        if empty_username_rows:
            summary_msg += f"⚠️ Empty Discord Username: **{len(empty_username_rows)}**\n"
        summary_msg += f"📊 Total processed: **{len(all_records)}**\n\n"
        
        # Add detailed missing members list (only show who's missing)
        if missing_members:
            summary_msg += f"❌ **Missing Members:**\n"
            for member in missing_members:
                summary_msg += f"• {member['name']} ({member['discord_username']})\n"
        
        # Check if message is too long for Discord (2000 character limit)
        if len(summary_msg) > 1900:  # Leave some buffer
            # Split into multiple messages
            base_msg = f"📋 **Google Sheet Member Check Complete**\n"
            base_msg += f"✅ Found in Discord: **{len(found_members)}**\n"
            base_msg += f"❌ Missing from Discord: **{len(missing_members)}**\n"
            if empty_username_rows:
                base_msg += f"⚠️ Empty Discord Username: **{len(empty_username_rows)}**\n"
            base_msg += f"📊 Total processed: **{len(all_records)}**\n\n"
            
            await interaction.followup.send(base_msg)
            
            # Send missing members in chunks
            if missing_members:
                missing_msg = f"❌ **Missing Members:**\n"
                for member in missing_members:
                    line = f"• {member['name']} ({member['discord_username']})\n"
                    if len(missing_msg + line) > 1900:
                        await interaction.followup.send(missing_msg)
                        missing_msg = line
                    else:
                        missing_msg += line
                if missing_msg.strip():
                    await interaction.followup.send(missing_msg)
        else:
            await interaction.followup.send(summary_msg)
        
    except Exception as e:
        error_msg = f"❌ Error checking sheet members: {str(e)}"
        print(error_msg)
        await interaction.followup.send(error_msg)

bot.run(TOKEN)
