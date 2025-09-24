# Discord Bot Code Structure

## Overview
This document outlines the structure of the Discord bot for Electrium Mobility, which manages Discord roles, Google Sheets integration, and Outline synchronization.

## File Structure
```
status-discord-bot/
├── bot.py              # Main bot file (1006 lines)
├── requirements.txt    # Python dependencies
├── .env.example       # Environment variables template
├── .gitignore         # Git ignore rules
└── README.md          # Project documentation
```

## Code Organization in bot.py

### 1. File Header & Imports (Lines 1-26)
- File documentation
- Import statements organized by category
- External libraries and Discord-specific imports

### 2. Environment Configuration (Lines 27-53)
- Environment variable loading
- Discord, Google Sheets, and Outline API configuration
- Validation of required environment variables

### 3. Google Sheets Setup (Lines 54-61)
- OAuth2 credentials setup
- Google Sheets client initialization

### 4. Discord Bot Setup (Lines 62-70)
- Bot intents configuration
- Bot instance creation

### 5. Outline API Integration (Lines 71-172)
- `OutlineAPI` class definition
- API methods: get_users, get_groups, add_user_to_group, remove_user_from_group
- API client initialization

### 6. Bot Events (Lines 173-203)
- `on_ready` event handler
- Bot startup logging and command synchronization

### 7. Outline Integration Commands (Lines 204-425)
- `/list-roles` - List Discord server roles
- `/list-outline-groups` - List Outline groups
- `/sync-outline` - Sync Discord roles with Outline groups
- Helper function: `_sync_role_to_group`

### 8. Basic Bot Commands (Lines 426-442)
- `/ping` - Test bot responsiveness

### 9. Google Sheets Integration Commands (Lines 443-583)
- `/checkapps` - Check application count in Google Sheet
- `/sync_roles` - Sync Discord roles with Google Sheet data
- `/promote` - Promote members between role tiers

### 10. Member Management Commands (Lines 584-659)
- `/setstatus` - Set member status and update both Discord and Google Sheet

### 11. Utility Functions & Automation (Lines 660-725)
- `_sync_roles_internal` - Internal role synchronization logic
- `auto_sync_roles` - Automated daily role synchronization task

### 12. Role Intersection Commands (Lines 726-793)
- `/who-intersection` - Find members with both specified roles
- `/ping-intersection` - Mention members with both specified roles

### 13. Google Sheets Validation Commands (Lines 794-999)
- `/check-sheet-members` - Verify Google Sheet members exist in Discord

### 14. Bot Startup (Lines 1000-1006)
- Bot initialization and startup

## Command Summary

### Outline Integration (3 commands)
1. `list-roles` - List all Discord server roles
2. `list-outline-groups` - List all Outline groups
3. `sync-outline` - Sync Discord roles with Outline groups

### Basic Commands (1 command)
1. `ping` - Test bot responsiveness

### Google Sheets Integration (3 commands)
1. `checkapps` - Check application count
2. `sync_roles` - Sync roles with Google Sheet
3. `promote` - Promote members between tiers

### Member Management (1 command)
1. `setstatus` - Set member status

### Role Intersection (2 commands)
1. `who-intersection` - Find members with both roles
2. `ping-intersection` - Mention members with both roles

### Validation (1 command)
1. `check-sheet-members` - Verify sheet members in Discord

## Key Features
- **Modular Design**: Clear separation of concerns with grouped commands
- **Error Handling**: Comprehensive error handling throughout
- **Permission Control**: All commands require appropriate Discord permissions
- **Automated Tasks**: Daily role synchronization
- **Multi-Platform Integration**: Discord, Google Sheets, and Outline API
- **Flexible Mapping**: Dynamic role-to-group mapping with username matching

## Maintenance Notes
- Code is well-documented with docstrings for all functions
- Clear section separators for easy navigation
- No duplicate code or redundant definitions
- Syntax validated and error-free
- Total: 1006 lines (reduced from previous ~1400+ lines after cleanup)