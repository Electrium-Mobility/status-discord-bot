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

async def auto_sync_outline_command(interaction: discord.Interaction, outline_api, dry_run: bool = False):
    """
    Auto-sync all mapped Discord roles to corresponding Outline groups.
    
    Args:
        interaction: Discord interaction object
        bot: Discord bot instance
        outline_api: OutlineAPI client instance
        role_mappings: Role mapping configuration
    """
    if not outline_api:
        await interaction.response.send_message("❌ Outline API is not configured.", ephemeral=True)
        return
    
    if not role_mappings:
        await interaction.response.send_message("❌ Role mappings are not configured.", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    guild = interaction.guild
    results = []
    
    try:
        # Get existing Outline groups
        outline_groups_response = await outline_api.get_groups()
        if not outline_groups_response or 'data' not in outline_groups_response:
            await interaction.followup.send("❌ Failed to fetch Outline groups.")
            return
        
        outline_groups = {group['name']: group for group in outline_groups_response['data']}
        
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
                    outline_groups[outline_group_name] = create_response['data']
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
        
        # Create email to user ID mapping
        outline_user_map = {}
        for user in outline_users_response['data']:
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