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

@bot.tree.command(name="check-sheet-members", description="Check if Google Sheet members are in Discord server (all worksheets)")
@discord.app_commands.default_permissions(manage_roles=True)
async def check_sheet_members_slash(interaction: discord.Interaction):
    """Check if all members from all Google Sheet worksheets are present in the Discord server"""
    try:
        await interaction.response.defer()
    except discord.errors.NotFound:
        # Interaction token expired, try to send a regular response
        return
    
    guild = interaction.guild
    
    try:
        # Get the Google Sheet (spreadsheet object)
        spreadsheet = client.open_by_key(SHEET_ID)
        
        # Get all worksheets in the spreadsheet
        all_worksheets = spreadsheet.worksheets()
        
        # Get Discord server members
        discord_members = {member.name.lower(): member for member in guild.members}
        discord_display_names = {member.display_name.lower(): member for member in guild.members}
        
        print("🔍 Starting Google Sheet member check for ALL worksheets...")
        print(f"📊 Found {len(all_worksheets)} worksheets")
        print(f"👥 Total Discord members: {len(guild.members)}")
        
        # Results for all worksheets
        worksheet_results = {}
        total_found = 0
        total_missing = 0
        total_empty = 0
        total_processed = 0
        
        # Check each worksheet
        for worksheet in all_worksheets:
            worksheet_name = worksheet.title
            print(f"\n📋 Checking worksheet: {worksheet_name}")
            
            try:
                # Get all data from this worksheet
                all_records = worksheet.get_all_records()
                
                if not all_records:
                    print(f"⚠️  Worksheet '{worksheet_name}' is empty or has no data")
                    continue
                
                # Lists to track results for this worksheet
                found_members = []
                missing_members = []
                empty_username_rows = []
                
                # Check each person in this worksheet
                for i, record in enumerate(all_records, start=2):  # Start from row 2 (accounting for header)
                    first_name = record.get('First Name', '').strip()
                    last_name = record.get('Last Name', '').strip()
                    discord_username = record.get('Discord Username', '').strip()
                    uwaterloo_email = record.get('UWaterloo Email', '').strip()
                    
                    if not discord_username:
                        empty_username_rows.append({
                            'row': i,
                            'name': f"{first_name} {last_name}",
                            'first_name': first_name,
                            'last_name': last_name,
                            'uwaterloo_email': uwaterloo_email
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
                            'uwaterloo_email': uwaterloo_email,
                            'matched_member': matched_member
                        })
                        print(f"✅ Found: {first_name} {last_name} ({discord_username})")
                    else:
                        missing_members.append({
                            'row': i,
                            'name': f"{first_name} {last_name}",
                            'discord_username': discord_username,
                            'uwaterloo_email': uwaterloo_email
                        })
                        print(f"❌ Missing: {first_name} {last_name} ({discord_username})")
                
                # Store results for this worksheet
                worksheet_results[worksheet_name] = {
                    'found': found_members,
                    'missing': missing_members,
                    'empty': empty_username_rows,
                    'total': len(all_records)
                }
                
                # Update totals
                total_found += len(found_members)
                total_missing += len(missing_members)
                total_empty += len(empty_username_rows)
                total_processed += len(all_records)
                
                print(f"📊 {worksheet_name}: {len(found_members)} found, {len(missing_members)} missing, {len(empty_username_rows)} empty")
                
            except Exception as worksheet_error:
                print(f"❌ Error processing worksheet '{worksheet_name}': {str(worksheet_error)}")
                continue
        
        # Print overall summary to console
        print("\n" + "="*60)
        print("📋 COMPLETE GOOGLE SHEET MEMBER CHECK SUMMARY")
        print("="*60)
        print(f"📊 Worksheets checked: {len(worksheet_results)}")
        print(f"✅ Total found in Discord: {total_found}")
        print(f"❌ Total missing from Discord: {total_missing}")
        print(f"⚠️  Total empty Discord usernames: {total_empty}")
        print(f"📊 Total records processed: {total_processed}")
        print("="*60)
        
        # Send summary to Discord
        summary_msg = f"📋 **Complete Google Sheet Member Check**\n"
        summary_msg += f"📊 Worksheets checked: **{len(worksheet_results)}**\n"
        summary_msg += f"✅ Total found: **{total_found}**\n"
        summary_msg += f"❌ Total missing: **{total_missing}**\n"
        if total_empty > 0:
            summary_msg += f"⚠️ Total empty usernames: **{total_empty}**\n"
        summary_msg += f"📊 Total processed: **{total_processed}**\n\n"
        
        # Add detailed results for each worksheet
        for worksheet_name, results in worksheet_results.items():
            found_count = len(results['found'])
            missing_count = len(results['missing'])
            empty_count = len(results['empty'])
            
            summary_msg += f"📋 **{worksheet_name}**\n"
            summary_msg += f"   ✅ Found: {found_count} | ❌ Missing: {missing_count}"
            if empty_count > 0:
                summary_msg += f" | ⚠️ Empty: {empty_count}"
            summary_msg += "\n"
            
            # List missing members for this worksheet
            if results['missing']:
                summary_msg += f"   Missing members:\n"
                for member in results['missing']:
                    email_info = f" - {member['uwaterloo_email']}" if member['uwaterloo_email'] else ""
                    summary_msg += f"   • {member['name']} ({member['discord_username']}){email_info}\n"
            summary_msg += "\n"
        
        # Check if message is too long for Discord (2000 character limit)
        if len(summary_msg) > 1900:  # Leave some buffer
            # Send base summary first
            base_msg = f"📋 **Complete Google Sheet Member Check**\n"
            base_msg += f"📊 Worksheets checked: **{len(worksheet_results)}**\n"
            base_msg += f"✅ Total found: **{total_found}**\n"
            base_msg += f"❌ Total missing: **{total_missing}**\n"
            if total_empty > 0:
                base_msg += f"⚠️ Total empty usernames: **{total_empty}**\n"
            base_msg += f"📊 Total processed: **{total_processed}**\n\n"
            
            await interaction.followup.send(base_msg)
            
            # Send detailed results for each worksheet in separate messages
            for worksheet_name, results in worksheet_results.items():
                found_count = len(results['found'])
                missing_count = len(results['missing'])
                empty_count = len(results['empty'])
                
                worksheet_msg = f"📋 **{worksheet_name}**\n"
                worksheet_msg += f"✅ Found: {found_count} | ❌ Missing: {missing_count}"
                if empty_count > 0:
                    worksheet_msg += f" | ⚠️ Empty: {empty_count}"
                worksheet_msg += "\n\n"
                
                # Add missing members
                if results['missing']:
                    worksheet_msg += f"❌ **Missing members:**\n"
                    for member in results['missing']:
                        email_info = f" - {member['uwaterloo_email']}" if member['uwaterloo_email'] else ""
                        line = f"• {member['name']} ({member['discord_username']}){email_info}\n"
                        if len(worksheet_msg + line) > 1900:
                            await interaction.followup.send(worksheet_msg)
                            worksheet_msg = f"📋 **{worksheet_name}** (continued)\n" + line
                        else:
                            worksheet_msg += line
                
                if worksheet_msg.strip():
                    await interaction.followup.send(worksheet_msg)
        else:
            await interaction.followup.send(summary_msg)
        
    except Exception as e:
        error_msg = f"❌ Error checking sheet members: {str(e)}"
        print(error_msg)
        await interaction.followup.send(error_msg)

bot.run(TOKEN)
