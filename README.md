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
