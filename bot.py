"""
Discord Bot for Electrium Mobility
==================================

This bot manages Discord roles, Google Sheets integration, and Outline synchronization.

Features:
- Google Sheets integration for member management
- Discord role synchronization
- Outline API integration for group management
- Automated role promotion system
"""

# ============================================================================
# IMPORTS
# ============================================================================

import discord
import gspread
import os
import asyncio
import aiohttp
import json
from discord.ext import commands, tasks
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
from auto_sync_outline import auto_sync_outline_command

# ============================================================================
# ENVIRONMENT CONFIGURATION
# ============================================================================

# Load environment variables
load_dotenv()

# Discord configuration
TOKEN = os.getenv("DISCORD_TOKEN")

# Google Sheets configuration
SHEET_ID = os.getenv("GOOGLE_SHEETS_ID")  # Changed from SHEET_ID to GOOGLE_SHEETS_ID
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME")

# Outline API configuration
OUTLINE_API_URL = os.getenv("OUTLINE_API_URL")
OUTLINE_API_TOKEN = os.getenv("OUTLINE_API_TOKEN")

# Load role mapping configuration
ROLE_MAPPING_FILE = "role_mapping.json"
role_mappings = {}

def load_role_mappings():
    """Load role mappings from JSON configuration file."""
    global role_mappings
    try:
        with open(ROLE_MAPPING_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            role_mappings = config.get('role_mappings', {})
            print(f"✅ Loaded role mappings from {ROLE_MAPPING_FILE}")
            return True
    except FileNotFoundError:
        print(f"⚠️  Warning: {ROLE_MAPPING_FILE} not found. Role mapping will be disabled.")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing {ROLE_MAPPING_FILE}: {e}")
        return False

# Load role mappings on startup
load_role_mappings()

# Validate required environment variables
if not TOKEN:
    print("❌ Error: DISCORD_TOKEN not found in .env")
    exit(1)
if not SHEET_ID:
    print("❌ Error: GOOGLE_SHEETS_ID not found in .env")
    exit(1)

# ============================================================================
# GOOGLE SHEETS SETUP
# ============================================================================

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID).worksheet(WORKSHEET_NAME)

# ============================================================================
# DISCORD BOT SETUP
# ============================================================================

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ============================================================================
# OUTLINE API CLIENT
# ============================================================================

class OutlineAPI:
    """
    Outline API client for managing users and groups.
    
    This class provides methods to interact with the Outline API for:
    - Fetching users and groups
    - Adding/removing users from groups
    - Managing team permissions
    """
    
    def __init__(self, api_url, api_token):
        """
        Initialize the Outline API client.
        
        Args:
            api_url (str): The base URL of the Outline API
            api_token (str): The API token for authentication
        """
        self.api_url = api_url.rstrip('/')
        self.api_token = api_token
        self.headers = {
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json'
        }
    
    async def _make_request(self, endpoint, data=None):
        """
        Make an HTTP request to Outline API.
        
        Args:
            endpoint (str): The API endpoint to call (e.g., 'users.list', 'groups.list')
            data (dict, optional): JSON data to send with the request
            
        Returns:
            dict: The JSON response from the API, or None if failed
        """
        url = f"{self.api_url}/{endpoint}"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, headers=self.headers, json=data or {}) as response:
                    response_text = await response.text()
                    print(f"🔍 Outline API {endpoint}: Status {response.status}")
                    print(f"🔍 Response: {response_text[:500]}...")
                    
                    if response.status == 200:
                        try:
                            return await response.json()
                        except:
                            # If response is not JSON, try to parse the text we already got
                            import json as json_module
                            return json_module.loads(response_text)
                    else:
                        print(f"❌ Outline API error {response.status}: {response_text}")
                        return None
            except Exception as e:
                print(f"❌ Request failed: {str(e)}")
                return None
    
    async def get_users(self):
        """Get all users from Outline with pagination support."""
        all_users = []
        offset = 0
        limit = 25
        
        while True:
            # Make request with pagination parameters
            response = await self._make_request('users.list', {'offset': offset, 'limit': limit})
            
            if not response or 'data' not in response:
                break
                
            users = response['data']
            all_users.extend(users)
            
            # Check if there are more pages
            pagination = response.get('pagination', {})
            total = pagination.get('total', 0)
            
            if len(all_users) >= total or not pagination.get('nextPath'):
                break
                
            offset += limit
        
        # Return in the same format as the original API response
        return {
            'data': all_users,
            'pagination': {
                'total': len(all_users),
                'limit': len(all_users),
                'offset': 0
            },
            'ok': True
        }
    
    async def get_groups(self):
        """Get all groups from Outline."""
        return await self._make_request('groups.list')
    
    async def create_group(self, name, description=None):
        """
        Create a new group in Outline.
        
        Args:
            name (str): The name of the group to create
            description (str): Optional description for the group
            
        Returns:
            dict: The API response, or None if failed
        """
        data = {
            'name': name
        }
        if description:
            data['description'] = description
        return await self._make_request('groups.create', data)
    
    async def add_user_to_group(self, user_id, group_id):
        """
        Add a user to a group.
        
        Args:
            user_id (str): The ID of the user to add
            group_id (str): The ID of the group to add the user to
            
        Returns:
            dict: The API response, or None if failed
        """
        data = {
            'userId': user_id,
            'groupId': group_id
        }
        return await self._make_request('groups.addUser', data)
    
    async def remove_user_from_group(self, user_id, group_id):
        """
        Remove a user from a group.
        
        Args:
            user_id (str): The ID of the user to remove
            group_id (str): The ID of the group to remove the user from
            
        Returns:
            dict: The API response, or None if failed
        """
        data = {
            'userId': user_id,
            'groupId': group_id
        }
        return await self._make_request('groups.removeUser', data)

def get_outline_group_name(discord_role_name):
    """
    Get the corresponding Outline group name for a Discord role.
    
    Args:
        discord_role_name (str): The Discord role name
        
    Returns:
        str: The corresponding Outline group name, or None if no mapping found
    """
    # Check all mapping categories
    for category_name, category_data in role_mappings.items():
        mappings = category_data.get('mappings', {})
        if discord_role_name in mappings:
            return mappings[discord_role_name]
    
    # Check for F25 pattern matching (case insensitive)
    if 'f25' in discord_role_name.lower():
        # Auto-generate group name for F25 projects
        return f"F25-{discord_role_name.replace('F25', '').replace('f25', '').replace('-', '').strip()}"
    
    return None

def get_all_mapped_roles():
    """
    Get all Discord roles that have Outline group mappings.
    
    Returns:
        dict: Dictionary mapping Discord role names to Outline group names
    """
    all_mappings = {}
    for category_name, category_data in role_mappings.items():
        mappings = category_data.get('mappings', {})
        all_mappings.update(mappings)
    return all_mappings

# Initialize Outline API client
outline_api = None
if OUTLINE_API_URL and OUTLINE_API_TOKEN:
    outline_api = OutlineAPI(OUTLINE_API_URL, OUTLINE_API_TOKEN)

# ============================================================================
# BOT EVENT HANDLERS
# ============================================================================

@bot.event
async def on_ready():
    """
    Event handler for when the bot successfully connects to Discord.
    
    This function:
    - Prints connection status
    - Syncs slash commands with Discord
    - Starts the automated role sync task
    """
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

# ============================================================================
# OUTLINE INTEGRATION COMMANDS
# ============================================================================

@bot.tree.command(name="list-roles", description="List all roles in the Discord server")
@discord.app_commands.default_permissions(manage_roles=True)
async def list_roles_slash(interaction: discord.Interaction):
    """
    List all roles in the Discord server with member counts.
    
    This command displays all server roles (excluding @everyone) sorted by position,
    showing the number of members for each role. Long lists are automatically split
    into multiple messages to avoid Discord's message length limit.
    
    Args:
        interaction: The Discord interaction object
    """
    guild = interaction.guild
    
    # Get all roles except @everyone
    roles = [role for role in guild.roles if role.name != "@everyone"]
    
    if not roles:
        await interaction.response.send_message("📭 No roles found in this server")
        return
    
    # Sort roles by position (highest first)
    roles.sort(key=lambda r: r.position, reverse=True)
    
    # Create role list with member counts
    role_info = []
    for role in roles:
        member_count = len(role.members)
        role_info.append(f"• **{role.name}** ({member_count} members)")
    
    # Split into chunks if too long
    role_text = "\n".join(role_info)
    if len(role_text) > 1900:  # Discord message limit is 2000
        # Send in multiple messages
        await interaction.response.send_message(f"🎭 **Server Roles ({len(roles)} total):**")
        
        chunk = ""
        for info in role_info:
            if len(chunk + info + "\n") > 1900:
                await interaction.followup.send(chunk)
                chunk = info + "\n"
            else:
                chunk += info + "\n"
        
        if chunk:
            await interaction.followup.send(chunk)
    else:
        await interaction.response.send_message(f"🎭 **Server Roles ({len(roles)} total):**\n{role_text}")

@bot.tree.command(name="list-outline-groups", description="List all groups in Outline")
@discord.app_commands.default_permissions(manage_roles=True)
async def list_outline_groups_slash(interaction: discord.Interaction):
    """
    List all groups in Outline with member counts.
    
    This command fetches and displays all groups from the connected Outline instance,
    showing the group name and number of members in each group.
    
    Args:
        interaction: The Discord interaction object
    """
    
    if not outline_api:
        await interaction.response.send_message("❌ Outline API not configured. Please set OUTLINE_API_URL and OUTLINE_API_TOKEN in .env file")
        return
    
    await interaction.response.defer()
    
    try:
        response = await outline_api.get_groups()
        if not response:
            await interaction.followup.send("❌ Failed to fetch groups from Outline")
            return
        
        # Handle both string and dict responses
        if isinstance(response, str):
            try:
                import json
                response = json.loads(response)
            except json.JSONDecodeError:
                await interaction.followup.send(f"❌ Invalid JSON response from Outline API: {response[:200]}...")
                return
        
        # Check if response is a dict and has the expected structure
        if not isinstance(response, dict):
            await interaction.followup.send(f"❌ Unexpected response format from Outline API: {type(response)}")
            return
        
        # Handle the actual Outline API response structure
        data = response.get('data', {})
        if isinstance(data, dict):
            groups = data.get('groups', [])
        else:
            groups = data if isinstance(data, list) else []
        
        if not groups:
            await interaction.followup.send("📭 No groups found in Outline")
            return
        
        group_info = []
        for group in groups:
            name = group.get('name', 'Unknown')
            member_count = group.get('memberCount', 0)
            group_info.append(f"• **{name}** ({member_count} members)")
        
        group_text = "\n".join(group_info)
        await interaction.followup.send(f"👥 **Outline Groups ({len(groups)} total):**\n{group_text}")
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error fetching groups: {str(e)}")

@bot.tree.command(name="sync-outline", description="Sync Discord roles with Outline groups")
@discord.app_commands.default_permissions(manage_roles=True)
async def sync_outline_slash(interaction: discord.Interaction, role_name: str = None, group_name: str = None):
    """
    Sync Discord roles with Outline groups.
    
    This command synchronizes members who have a specific Discord role with an Outline group.
    Users are matched by username between Discord and Outline. If no parameters are provided,
    the command shows usage instructions.
    
    Args:
        interaction: The Discord interaction object
        role_name: Name of the Discord role to sync (optional)
        group_name: Name of the Outline group to sync to (optional)
    """
    
    # Check if Outline API is configured
    if not outline_api:
        await interaction.response.send_message("❌ Outline API not configured. Please set OUTLINE_API_URL and OUTLINE_API_TOKEN in .env file")
        return
    
    await interaction.response.defer()
    
    try:
        guild = interaction.guild
        
        # Get Outline users and groups
        outline_users_response = await outline_api.get_users()
        outline_groups_response = await outline_api.get_groups()
        
        if not outline_users_response or not outline_groups_response:
            await interaction.followup.send("❌ Failed to fetch data from Outline API")
            return
        
        # Handle nested response structure for users
        users_data = outline_users_response.get('data', {})
        if isinstance(users_data, dict) and 'users' in users_data:
            outline_users = users_data['users']
        else:
            outline_users = users_data if isinstance(users_data, list) else []
        
        # Handle nested response structure for groups  
        groups_data = outline_groups_response.get('data', {})
        if isinstance(groups_data, dict) and 'groups' in groups_data:
            outline_groups = groups_data['groups']
        else:
            outline_groups = groups_data if isinstance(groups_data, list) else []
        
        # Create username mapping for Outline users
        outline_user_map = {}
        for user in outline_users:
            # Try to extract Discord username from Outline user
            username = user.get('name', '').lower()
            if username:
                outline_user_map[username] = user
        
        # Create group mapping for Outline groups
        outline_group_map = {group.get('name', '').lower(): group for group in outline_groups}
        
        sync_results = []
        
        if role_name and group_name:
            # Sync specific role to specific group
            result = await _sync_role_to_group(guild, role_name, group_name, outline_user_map, outline_group_map)
            sync_results.append(result)
        else:
            # Interactive mode - let user choose
            await interaction.followup.send("🔄 **Available sync options:**\n"
                                          "• Use `/sync-outline role_name group_name` to sync a specific role to a group\n"
                                          "• Use `/list-roles` to see all Discord roles\n"
                                          "• Use `/list-outline-groups` to see all Outline groups")
            return
        
        # Send results
        result_text = "\n".join(sync_results)
        await interaction.followup.send(f"✅ **Sync completed:**\n{result_text}")
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error during sync: {str(e)}")
        print(f"❌ Sync error: {str(e)}")

async def _sync_role_to_group(guild, role_name, group_name, outline_user_map, outline_group_map):
    """
    Sync a specific Discord role to an Outline group.
    
    This helper function performs the actual synchronization between a Discord role
    and an Outline group, matching users by username.
    
    Args:
        guild: The Discord guild object
        role_name: Name of the Discord role
        group_name: Name of the Outline group
        outline_user_map: Dictionary mapping usernames to Outline user objects
        outline_group_map: Dictionary mapping group names to Outline group objects
        
    Returns:
        str: A summary message of the sync operation results
    """
    
    # Find Discord role
    role = discord.utils.get(guild.roles, name=role_name)
    if not role:
        return f"❌ Discord role '{role_name}' not found"
    
    # Find Outline group
    group = outline_group_map.get(group_name.lower())
    if not group:
        return f"❌ Outline group '{group_name}' not found"
    
    # Get Discord members with this role
    discord_members = role.members
    
    sync_count = 0
    error_count = 0
    
    for member in discord_members:
        # Try to find matching Outline user by username
        username = member.name.lower()
        outline_user = outline_user_map.get(username)
        
        if outline_user:
            # Add user to group
            result = await outline_api.add_user_to_group(outline_user['id'], group['id'])
            if result:
                sync_count += 1
                print(f"✅ Added {member.name} to Outline group '{group_name}'")
            else:
                error_count += 1
                print(f"❌ Failed to add {member.name} to Outline group '{group_name}'")
        else:
            error_count += 1
            print(f"❌ No matching Outline user found for Discord user '{member.name}'")
    
    return f"🎭 **{role_name}** → **{group_name}**: {sync_count} synced, {error_count} errors"

# ============================================================================
# BASIC BOT COMMANDS
# ============================================================================

@bot.tree.command(name="ping", description="Test bot responsiveness")
async def ping_slash(interaction: discord.Interaction):
    """
    Test bot responsiveness with a simple ping command.
    
    This command provides a quick way to verify that the bot is online and
    responding to commands. It returns a simple "Pong!" message.
    
    Args:
        interaction: The Discord interaction object
    """
    await interaction.response.send_message("Pong!")

# ============================================================================
# GOOGLE SHEETS INTEGRATION COMMANDS
# ============================================================================

@bot.tree.command(name="checkapps", description="Check the number of applications in the Google Sheet")
async def checkapps_slash(interaction: discord.Interaction):
    """
    Check applications in Google Sheets.
    
    This command retrieves and displays application data from the connected
    Google Sheets document, providing an overview of pending applications.
    
    Args:
        interaction: The Discord interaction object
    """
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
    """
    Sync roles from Google Sheets.
    
    This command synchronizes Discord roles based on data from the connected
    Google Sheets document. It processes applications and assigns appropriate
    roles to users based on their status in the sheet.
    
    Args:
        interaction: The Discord interaction object
    """
    await interaction.response.send_message("🔄 Syncing roles...")
    await _sync_roles_internal(interaction.guild)
    await interaction.followup.send("✅ Role sync complete.")

@bot.tree.command(name="promote", description="Promote all Active members to Previous and Incoming to Active")
@discord.app_commands.default_permissions(manage_roles=True)
async def promote_slash(interaction: discord.Interaction):
    """
    Promote users based on Google Sheets data.
    
    This command promotes users by updating their roles according to a predefined
    promotion cycle: Incoming → Active, Active → Previous.
    
    Args:
        interaction: The Discord interaction object
    """
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
    """
    Set a member's status and update both Discord role and Google Sheet.
    
    This command allows administrators to manually set a member's status,
    updating both their Discord role and the corresponding entry in the
    Google Sheets document.
    
    Args:
        interaction: The Discord interaction object
        member: The Discord member to update
        status: The new status to assign
    """
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

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

async def _sync_roles_internal(guild):
    """
    Internal function to sync roles without interaction responses.
    
    This function handles the core logic for synchronizing Discord roles
    with Google Sheets data without sending interaction responses.
    
    Args:
        guild: The Discord guild object
    """
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

# ============================================================================
# AUTOMATED TASKS
# ============================================================================

@tasks.loop(hours=24)
async def auto_sync_roles():
    """
    Automated task to sync roles every 24 hours.
    
    This task automatically synchronizes Discord roles with Google Sheets
    data on a daily basis to ensure consistency without manual intervention.
    """
    await bot.wait_until_ready()
    print("🔁 Auto-sync running...")
    for guild in bot.guilds:
        await _sync_roles_internal(guild)
    print("✅ Automated role sync complete.")

# ============================================================================
# ROLE INTERSECTION COMMANDS
# ============================================================================

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

# ============================================================================
# AUTO SYNC OUTLINE COMMAND
# ============================================================================

@bot.tree.command(name="debug-users-api", description="Debug Outline users.list API response")
@discord.app_commands.default_permissions(manage_roles=True)
async def debug_users_api_slash(interaction: discord.Interaction):
    """Debug command to check Outline users.list API response structure."""
    if not outline_api:
        await interaction.response.send_message("❌ Outline API not configured")
        return
    
    await interaction.response.defer()
    
    try:
        # Get users response
        users_response = await outline_api.get_users()
        
        if users_response:
            # Show the raw response structure
            import json
            response_str = json.dumps(users_response, indent=2)[:1500]  # Limit length
            await interaction.followup.send(f"**Users API Response Structure:**\n```json\n{response_str}\n```")
        else:
            await interaction.followup.send("❌ Failed to get users response")
            
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

@bot.tree.command(name="test-outline-features", description="Test Outline features (validation + dry run)")
@discord.app_commands.default_permissions(manage_roles=True)
async def test_outline_features_slash(interaction: discord.Interaction):
    """Test Outline features with validation and dry run."""
    # Check if Outline API is configured
    if not outline_api:
        await interaction.response.send_message("❌ Outline API not configured. Please set OUTLINE_API_URL and OUTLINE_API_TOKEN in .env file")
        return
    
    if not role_mappings:
        await interaction.response.send_message("❌ Role mappings are not configured.", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    try:
        # Perform dry run
        dry_run_result = await auto_sync_outline_command(interaction, outline_api, role_mappings, dry_run=True)
        
        # Send combined results
        await interaction.followup.send("🧪 **Outline Feature Test Complete**\n🔍 Dry run completed\nCheck the results above for details.")
        
    except Exception as e:
        await interaction.followup.send(f"❌ Test failed: {str(e)}")

@bot.tree.command(name="sync-outline-auto", description="Sync Discord roles to Outline groups")
@discord.app_commands.default_permissions(manage_roles=True)
@discord.app_commands.describe(dry_run="Whether to perform a dry run (no actual operations)")
async def sync_outline_auto_slash(interaction: discord.Interaction, dry_run: bool = False):
    """Sync Discord roles to corresponding Outline groups."""
    await auto_sync_outline_command(interaction, outline_api, role_mappings, dry_run)



@bot.tree.command(name="show-role-mappings", description="Show current Discord role to Outline group mappings")
@discord.app_commands.default_permissions(manage_roles=True)
async def show_role_mappings_slash(interaction: discord.Interaction):
    """Show the current role mappings configuration."""
    if not role_mappings:
        await interaction.response.send_message("❌ No role mappings configured.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🔗 Discord Role → Outline Group Mappings",
        color=discord.Color.blue(),
        description="Current role mapping configuration"
    )
    
    for category_name, category_data in role_mappings.items():
        mappings = category_data.get('mappings', {})
        description = category_data.get('description', 'No description')
        
        if mappings:
            mapping_text = "\n".join([f"• `{discord_role}` → `{outline_group}`" 
                                    for discord_role, outline_group in mappings.items()])
            embed.add_field(
                name=f"📋 {category_name.replace('_', ' ').title()}",
                value=f"*{description}*\n{mapping_text}",
                inline=False
            )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="reload-mappings", description="Reload role mappings from configuration file")
@discord.app_commands.default_permissions(manage_roles=True)
async def reload_mappings_slash(interaction: discord.Interaction):
    """Reload role mappings from the JSON configuration file."""
    success = load_role_mappings()
    
    if success:
        mapping_count = sum(len(category.get('mappings', {})) for category in role_mappings.values())
        await interaction.response.send_message(
            f"✅ Successfully reloaded role mappings! Found {mapping_count} role mappings across {len(role_mappings)} categories.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "❌ Failed to reload role mappings. Check the console for error details.",
            ephemeral=True
        )

# ================================================================================================
# BOT STARTUP
# ================================================================================================

# Start the bot
bot.run(TOKEN)