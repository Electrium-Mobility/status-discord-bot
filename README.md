# 🤖 Electrium Mobility Discord Bot

Welcome to our Discord bot that manages member roles and status progression! This bot automatically syncs with our Google Sheets to keep member information up-to-date.

## 🎯 What This Bot Does

- **Automatically assigns roles** based on your status in our organization
- **Promotes members** through our progression system (Incoming → Active → Previous)
- **Syncs with Google Sheets** to keep everything organized
- **Updates both Discord and our database** when status changes

## 📋 Available Commands

| Command                       | What it does                                         |
| ----------------------------- | ---------------------------------------------------- |
| `!ping`                       | Test if the bot is working                           |
| `!checkapps`                  | See how many applications we have                    |
| `!sync_roles`                 | Manually sync all roles from our sheet               |
| `!promote`                    | Promote everyone's status (Incoming→Active→Previous) |
| `!setstatus @username Active` | Set a specific person's status                       |

## 👥 Our Role System

We have three main status roles:

- **🟡 Incoming** - New members who just joined
- **🟢 Active** - Current active members
- **🔴 Previous** - Former members

## 🛠️ Setup Instructions

### Situation 1: Running the Bot (Most Common)

If you just need to run the bot:

#### 1. Install Python Dependencies

```bash
pip install discord.py gspread python-dotenv oauth2client
```

#### 2. Get Configuration Files

Ask an admin in Discord for:

- `.env` file (contains Discord token and Sheet ID)
- `credentials.json` file (Google Sheets API credentials)

Place both files in your project folder.

#### 3. Run the Bot

```bash
python bot.py
```

**That's it!** The bot should now be running and connected to our Discord server.

---

### Situation 2: Setting Up for a NEW spreadsheet

If you need to set up the bot for a completely new spreadsheet:

#### 1. Install Python Dependencies

```bash
pip install discord.py gspread python-dotenv oauth2client
```

#### 2. Create Environment File

Create a `.env` file in the project folder:

```env
DISCORD_TOKEN=your_discord_bot_token_here
SHEET_ID=your_google_sheet_id_here
```

#### 3. Google Sheets Setup

1. **Get the Google Sheet ID** from the URL:
   - Open your Google Sheet
   - Copy the ID from the URL: `https://docs.google.com/spreadsheets/d/SHEET_ID_HERE/edit`
2. **Set up Google Sheets API**:

   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project
   - Enable Google Sheets API
   - Create a Service Account
   - Download the credentials JSON file
   - Rename it to `credentials.json` and place in project folder

3. **Share your Google Sheet**:
   - Open your Google Sheet
   - Click "Share" (top right)
   - Add the service account email (from credentials.json) with **Editor** permissions

### Required Files

- ✅ `bot.py` - Main bot code
- ✅ `.env` - Environment variables (get from admin or create new)
- ✅ `credentials.json` - Google Sheets API credentials (get from admin or create new)

## 🚀 How to Use

#### Promoting Everyone's Status

When it's time to promote members (like at the end of a semester):

```
!promote
```

This will:

- Move Incoming → Active
- Move Active → Previous
- Remove Previous roles
- Update our Google Sheet automatically

#### Setting Individual Status

To change someone's status manually:

```
!setstatus @username Active
```

Replace `@username` with the person's Discord mention and `Active` with their new status.

#### Manual Sync

If roles get out of sync:

```
!sync_roles
```

This will sync all roles from our Google Sheet to Discord.

## 📊 Checking Applications

To see our latest applications:

```
!checkapps
```

This shows how many applications we have and the most recent one.

## 🎉 Quick Reference

- `!ping` - Test bot
- `!checkapps` - See applications
- `!promote` - Promote everyone
- `!setstatus @user Active` - Set individual status
- `!sync_roles` - Manual sync

---

**Made by Prabhgun Bhatia**
