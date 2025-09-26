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
            create_message = ""
            if outline_group_name not in outline_groups:
                if dry_run:
                    create_message = f"🔍 [DRY RUN] Would create Outline group '{outline_group_name}'\n"
                    # Create a mock group for dry run to continue processing
                    outline_groups[outline_group_name] = {'id': 'mock-id-for-dry-run', 'name': outline_group_name}
                else:
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
                        create_message = f"✅ Created Outline group '{outline_group_name}'\n"
                    else:
                        results.append(f"❌ Failed to create Outline group '{outline_group_name}'")
                        continue
            
            # Sync members
            sync_result = await sync_role_to_outline_group(
                guild, discord_role, outline_group_name, outline_groups[outline_group_name]['id'], outline_api, dry_run
            )
            
            # Combine create message with sync result
            combined_result = create_message + sync_result
            results.append(combined_result)
        
        # Send each role's result as a separate complete message
        if results:
            for result in results:
                await interaction.followup.send(f"```\n{result}\n```")
        else:
            await interaction.followup.send("No role mappings found to sync.")
    
    except Exception as e:
        await interaction.followup.send(f"❌ Error during auto-sync: {str(e)}")

async def sync_role_to_outline_group(guild, discord_role, outline_group_name, outline_group_id, outline_api, dry_run=False):
    """
    Sync a specific Discord role to an Outline group.
    
    Args:
        guild: Discord guild object
        discord_role: Discord role object
        outline_group_name: Name of the Outline group
        outline_group_id: ID of the Outline group
        outline_api: OutlineAPI client instance
        
    Returns:
        str: Result message with detailed sync information
    """
    try:
        # Get Outline users
        outline_users_response = await outline_api.get_users()
        if not outline_users_response or 'data' not in outline_users_response:
            return f"❌ Failed to fetch Outline users for '{outline_group_name}'"
        
        # Handle nested data structure: {"data": {"users": [...]}}
        users_data = outline_users_response['data']
        if isinstance(users_data, dict) and 'users' in users_data:
            users_list = users_data['users']
        elif isinstance(users_data, list):
            users_list = users_data  # Fallback for direct array format
        else:
            return f"❌ Invalid users response structure for '{outline_group_name}'"
        
        # Get Discord members with the role
        discord_members = discord_role.members
        
        # Track detailed results
        synced_members = []
        failed_members = []
        
        print(f"🔍 Processing Discord role '{discord_role.name}' with {len(discord_members)} members")
        
        # Enhanced user matching logic - prioritize Discord display name matching
        def find_matching_outline_user(discord_username, discord_display_name, outline_users):
            """
            Find matching Outline user - prioritize Discord display name matching since users changed Outline names to match Discord display names
            """
            # Strategy 1: Direct Discord display name match (PRIORITY - users changed Outline names to match Discord display names)
            if discord_display_name:
                for user in outline_users:
                    if user.get('name'):
                        outline_name = user['name'].lower()
                        display_clean = discord_display_name.lower()
                        
                        # Direct display name match
                        if outline_name == display_clean:
                            return user, f"Direct display name match: '{discord_display_name}' = '{user['name']}'"
            
            # Strategy 2: Partial Discord display name match (more flexible)
            if discord_display_name:
                for user in outline_users:
                    if user.get('name'):
                        outline_name = user['name'].lower()
                        display_clean = discord_display_name.lower()
                        
                        # Split names and check individual parts
                        display_parts = display_clean.split()
                        outline_parts = outline_name.split()
                        
                        # Check if any part of display name matches any part of outline name
                        for display_part in display_parts:
                            for outline_part in outline_parts:
                                if len(display_part) > 2 and len(outline_part) > 2:  # Avoid matching single letters
                                    if display_part in outline_part or outline_part in display_part:
                                        return user, f"Partial display name match: '{discord_display_name}' ≈ '{user['name']}'"
            
            # Strategy 3: Email-based matching using display name
            if discord_display_name:
                display_clean = discord_display_name.lower().replace(' ', '')
                for user in outline_users:
                    if user.get('email'):
                        email_prefix = user['email'].split('@')[0].lower()
                        if display_clean in email_prefix or email_prefix in display_clean:
                            return user, f"Email-display match: '{discord_display_name}' ≈ '{user['email']}'"
            
            # Strategy 4: Direct Discord username match (fallback)
            for user in outline_users:
                if user.get('name'):
                    outline_name = user['name'].lower()
                    if outline_name == discord_username.lower():
                        return user, f"Direct username match: '{discord_username}' = '{user['name']}'"
            
            # Strategy 5: Partial Discord username match
            for user in outline_users:
                if user.get('name'):
                    outline_name = user['name'].lower()
                    username_clean = discord_username.lower()
                    
                    # Check if username contains outline name or vice versa (with length check)
                    if len(username_clean) > 2 and len(outline_name) > 2:
                        if username_clean in outline_name or outline_name in username_clean:
                            return user, f"Partial username match: '{discord_username}' ≈ '{user['name']}'"
            
            # Strategy 6: Email prefix matching (last resort)
            for user in outline_users:
                if user.get('email'):
                    email_prefix = user['email'].split('@')[0].lower()
                    if email_prefix == discord_username.lower():
                        return user, f"Email prefix match: '{discord_username}' = '{email_prefix}@...'"
            
            return None, f"No match found for Discord user: '{discord_username}' (display: '{discord_display_name}')"
        
        # Track different types of results
        synced_members = []
        existing_members = []
        failed_members = []
        
        for member in discord_members:
            # Use the enhanced matching function
            matched_user, match_reason = find_matching_outline_user(member.name, member.display_name, users_list)
            
            if matched_user:
                outline_user_id = matched_user['id']
                if dry_run:
                    # In dry run mode, check if user is already in the group
                    user_already_in_group = False
                    if 'memberships' in matched_user:
                        for membership in matched_user['memberships']:
                            if membership.get('groupId') == outline_group_id:
                                user_already_in_group = True
                                break
                    
                    if user_already_in_group:
                        existing_members.append(f"🔄 {member.display_name} ({member.name}) → {matched_user['name']} [Already in group]")
                    else:
                        synced_members.append(f"✅ {member.display_name} ({member.name}) → {matched_user['name']} [{match_reason}]")
                else:
                    # Add user to group
                    add_response = await outline_api.add_user_to_group(outline_user_id, outline_group_id)
                    if add_response:
                        # Debug: Print the actual response to understand the format
                        print(f"🔍 DEBUG: API response for {member.display_name}: {add_response}")
                        
                        # Check if the response indicates user already exists
                        response_text = str(add_response).lower()
                        print(f"🔍 DEBUG: Response text: {response_text}")
                        
                        # Check for various indicators of existing membership
                        existing_keywords = ['already', 'exist', 'duplicate', 'member', 'conflict', 'present']
                        is_existing = any(keyword in response_text for keyword in existing_keywords)
                        
                        # Also check if response has success=false or error field
                        if isinstance(add_response, dict):
                            if add_response.get('success') == False or 'error' in add_response:
                                error_msg = add_response.get('error', {}).get('message', '').lower()
                                print(f"🔍 DEBUG: Error message: {error_msg}")
                                if any(keyword in error_msg for keyword in existing_keywords):
                                    is_existing = True
                        
                        if is_existing:
                            existing_members.append(f"🔄 {member.display_name} ({member.name}) → {matched_user['name']} [Already in group]")
                        else:
                            synced_members.append(f"✅ {member.display_name} ({member.name}) → {matched_user['name']} [{match_reason}]")
                    else:
                        failed_members.append(f"❌ {member.display_name} ({member.name}) → {matched_user['name']} [API call failed]")
            else:
                failed_members.append(f"❌ {member.display_name} ({member.name}) [{match_reason}]")
        
        # Build result message with exist count
        synced_count = len(synced_members)
        existing_count = len(existing_members)
        failed_count = len(failed_members)
        
        dry_run_prefix = "🔍 [DRY RUN] " if dry_run else ""
        
        # Build status summary
        status_parts = []
        if synced_count > 0:
            status_parts.append(f"{synced_count} synced")
        if existing_count > 0:
            status_parts.append(f"{existing_count} exist")
        if failed_count > 0:
            status_parts.append(f"{failed_count} failed")
        
        status_summary = ", ".join(status_parts) if status_parts else "0 processed"
        summary = f"{dry_run_prefix}'{discord_role.name}' → '{outline_group_name}': {status_summary}"
        
        # Add existing members to summary if any
        if existing_members:
            summary += f"\nAlready in group:"
            existing_names = []
            for member_info in existing_members:
                if "🔄 " in member_info:
                    member_part = member_info.split(" →")[0].replace("🔄 ", "")
                    if " (" in member_part:
                        display_name = member_part.split(" (")[0]
                    else:
                        display_name = member_part
                    existing_names.append(display_name)
            summary += f"\n{', '.join(existing_names)}"
        
        # Group failed members by failure reason
        if failed_members:
            failure_groups = {}
            for member_info in failed_members:
                # Extract member name and reason from the formatted string
                if "❌ " in member_info:
                    parts = member_info.split(" [")
                    if len(parts) >= 2:
                        member_part = parts[0].replace("❌ ", "")
                        reason = parts[-1].rstrip("]")
                        
                        # Extract display name (before the parentheses)
                        if " (" in member_part:
                            display_name = member_part.split(" (")[0]
                        else:
                            display_name = member_part
                        
                        # Simplify reason categories
                        simplified_reason = ""
                        if "No match found" in reason:
                            simplified_reason = "No match found"
                        elif "API call failed" in reason:
                            simplified_reason = "API error"
                        else:
                            simplified_reason = "Other error"
                        
                        # Group by simplified reason
                        if simplified_reason not in failure_groups:
                            failure_groups[simplified_reason] = []
                        failure_groups[simplified_reason].append(display_name)
            
            # Format grouped failures
            for reason, members in failure_groups.items():
                summary += f"\n{reason}:"
                summary += f"\n{', '.join(members)}"
        
        return summary
    
    except Exception as e:
        return f"❌ Error syncing '{discord_role.name}': {str(e)}"