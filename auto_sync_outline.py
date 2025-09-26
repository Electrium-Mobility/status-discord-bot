"""
Auto Sync Outline Groups Command
===============================

This module provides commands for automatically syncing Discord roles to Outline groups
based on the role mapping configuration.
"""

import discord
from discord.ext import commands
import json
import logging

# Load role mappings
def load_role_mappings():
    try:
        with open('role_mapping.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error("role_mapping.json file not found")
        return {}
    except json.JSONDecodeError:
        logging.error("Invalid JSON in role_mapping.json")
        return {}

async def auto_sync_outline_command(interaction: discord.Interaction, outline_api, role_mappings, dry_run: bool = False):
    """
    Auto-sync all mapped Discord roles to corresponding Outline groups.
    
    Args:
        interaction: Discord interaction object
        bot: Discord bot instance
        outline_api: OutlineAPI client instance
        role_mappings: Role mapping configuration
    """
    # Note: interaction response should already be handled by the calling command
    
    guild = interaction.guild
    results = []
    
    try:
        # Get existing Outline groups
        outline_groups_response = await outline_api.get_groups()
        if not outline_groups_response or 'data' not in outline_groups_response:
            await interaction.followup.send("❌ Failed to fetch Outline groups.")
            return
        
        # Handle nested response structure for groups
        groups_data = outline_groups_response['data']
        if isinstance(groups_data, dict) and 'groups' in groups_data:
            groups_list = groups_data['groups']
        elif isinstance(groups_data, list):
            groups_list = groups_data  # Fallback for direct array format
        else:
            await interaction.followup.send(f"❌ Invalid groups response structure: {type(groups_data)}")
            return
        
        outline_groups = {group['name']: group for group in groups_list}
        
        # Get all mapped roles
        all_mappings = {}
        for category_name, category_data in role_mappings.items():
            mappings = category_data.get('mappings', {})
            all_mappings.update(mappings)
        
        # Process each mapped role
        for discord_role_name, outline_group_name in all_mappings.items():
            # Find Discord role
            discord_role = discord.utils.get(guild.roles, name=discord_role_name)
            if not discord_role:
                results.append(f"⚠️  Discord role '{discord_role_name}' not found")
                continue
            
            # Check if Outline group exists, create if not
            if outline_group_name not in outline_groups:
                description = f"Auto-synced from Discord role: {discord_role_name}"
                create_response = await outline_api.create_group(outline_group_name, description)
                if create_response and 'data' in create_response:
                    # Handle nested response structure for group creation
                    group_data = create_response['data']
                    if isinstance(group_data, dict):
                        outline_groups[outline_group_name] = group_data
                    else:
                        results.append(f"❌ Invalid group creation response structure for '{outline_group_name}'")
                        continue
                    results.append(f"✅ Created Outline group '{outline_group_name}'")
                else:
                    results.append(f"❌ Failed to create Outline group '{outline_group_name}'")
                    continue
            
            # Sync members
            sync_result = await sync_role_to_outline_group(
                guild, discord_role, outline_group_name, outline_groups[outline_group_name]['id'], outline_api
            )
            results.append(sync_result)
        
        # Send results
        if results:
            result_text = "\n".join(results[:20])  # Limit to first 20 results
            if len(results) > 20:
                result_text += f"\n... and {len(results) - 20} more results"
            
            await interaction.followup.send(f"**Auto-sync Results:**\n```\n{result_text}\n```")
        else:
            await interaction.followup.send("No role mappings found to sync.")
    
    except Exception as e:
        await interaction.followup.send(f"❌ Error during auto-sync: {str(e)}")

async def sync_role_to_outline_group(guild, discord_role, outline_group_name, outline_group_id, outline_api):
    """
    Sync a specific Discord role to an Outline group.
    
    Args:
        guild: Discord guild object
        discord_role: Discord role object
        outline_group_name: Name of the Outline group
        outline_group_id: ID of the Outline group
        outline_api: OutlineAPI client instance
        
    Returns:
        str: Result message
    """
    try:
        # Get Outline users
        outline_users_response = await outline_api.get_users()
        if not outline_users_response or 'data' not in outline_users_response:
            return f"❌ Failed to fetch Outline users for '{outline_group_name}'"
        
        # DEBUG: Print the complete users response structure
        import json
        print(f"🔍 DEBUG - Complete users.list API response:")
        print(f"🔍 Response type: {type(outline_users_response)}")
        print(f"🔍 Response keys: {list(outline_users_response.keys()) if isinstance(outline_users_response, dict) else 'Not a dict'}")
        print(f"🔍 Full response: {json.dumps(outline_users_response, indent=2)[:1000]}...")
        
        # Handle nested data structure: {"data": {"users": [...]}}
        users_data = outline_users_response['data']
        if isinstance(users_data, dict) and 'users' in users_data:
            users_list = users_data['users']
            print(f"🔍 Using nested structure: data.users (length: {len(users_list)})")
        elif isinstance(users_data, list):
            users_list = users_data  # Fallback for direct array format
            print(f"🔍 Using direct structure: data (length: {len(users_list)})")
        else:
            print(f"❌ Unexpected users data type: {type(users_data)}")
            print(f"❌ Users data content: {users_data}")
            return f"❌ Invalid users response structure for '{outline_group_name}'"
        
        # Create email to user ID mapping
        outline_user_map = {}
        for user in users_list:
            if user.get('email'):
                outline_user_map[user['email'].lower()] = user['id']
        
        # Get Discord members with the role
        discord_members = discord_role.members
        synced_count = 0
        failed_count = 0
        
        for member in discord_members:
            member_email = member.name.lower() + "@electriummobility.com"  # Assuming email pattern
            
            if member_email in outline_user_map:
                outline_user_id = outline_user_map[member_email]
                
                # Add user to group
                add_response = await outline_api.add_user_to_group(outline_user_id, outline_group_id)
                if add_response:
                    synced_count += 1
                else:
                    failed_count += 1
            else:
                failed_count += 1
        
        return f"✅ '{discord_role.name}' → '{outline_group_name}': {synced_count} synced, {failed_count} failed"
    
    except Exception as e:
        return f"❌ Error syncing '{discord_role.name}': {str(e)}"