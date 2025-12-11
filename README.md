# Discord Bot - Setup and Configuration

A Discord bot for PlanetNaturists server with role management and rules acceptance features.

## Prerequisites

- Python 3.11 or higher
- Discord Bot Token from [Discord Developer Portal](https://discord.com/developers/applications)

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd discord
   ```

2. **Create a virtual environment (recommended)**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and set your Discord bot token:
   ```
   DISCORD_TOKEN=your_actual_bot_token_here
   ```

   **⚠️ IMPORTANT**: Never commit your `.env` file to git! It contains sensitive credentials.

## Configuration

### Getting Your Discord Bot Token

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application or select an existing one
3. Go to the "Bot" section
4. Click "Reset Token" or "Copy" to get your token
5. Paste it in your `.env` file

### Required Bot Permissions

Your bot needs the following permissions:
- Manage Roles
- Read Messages/View Channels
- Send Messages
- Add Reactions
- Use Slash Commands

### Required Privileged Intents

Enable these in the Discord Developer Portal under Bot settings:
- ✅ Server Members Intent
- ✅ Message Content Intent

### Server Configuration

Update `config.py` with your Discord server IDs:

1. Enable Developer Mode in Discord:
   - User Settings > App Settings > Advanced > Developer Mode

2. Right-click on roles/channels and select "Copy ID"

3. Update the IDs in `config.py`:
   ```python
   ROLE_MEMBER = your_member_role_id
   CHANNEL_RULES = your_rules_channel_id
   ```

## Running the Bot

```bash
python bot.py
```

If everything is configured correctly, you should see:
```
🔍 Validating configuration...
✅ Environment variables validated successfully
Logged in as YourBot#1234 (ID: 123456789)
Loaded cog: rules.py
Slash commands synced.
------
```

## Security Best Practices

### ✅ DO:
- Keep your `.env` file private and never commit it to git
- Use `.env.example` as a template for others
- Regenerate your bot token if it's ever exposed
- Use environment variables for all sensitive data
- Validate configuration before bot startup
- Enable only the intents your bot needs

### ❌ DON'T:
- Hard-code tokens or secrets in your code
- Share your `.env` file or bot token publicly
- Commit sensitive data to version control
- Use overly permissive bot permissions
- Skip validation checks

## Troubleshooting

### "DISCORD_TOKEN environment variable is not set"
- Ensure you've created a `.env` file
- Ensure the `.env` file contains `DISCORD_TOKEN=your_token`
- Ensure you're running the bot from the correct directory

### "LOGIN FAILED"
- Verify your token is correct in `.env`
- Check if the token was regenerated in Discord Developer Portal
- Ensure the bot application still exists

### "PRIVILEGED INTENTS REQUIRED"
- Go to Discord Developer Portal
- Enable required intents in Bot settings
- Save and restart the bot

### Configuration ID Warnings
- Verify the role/channel IDs are correct
- Ensure IDs are from the correct Discord server
- Check that Developer Mode is enabled in Discord

## Project Structure

```
project/
├── bot.py              # Main bot entry point
├── config.py           # Server configuration (roles, channels)
├── validators.py       # Token and config validation
├── database.py         # Database operations
├── requirements.txt    # Python dependencies
├── .env                # Environment variables (not in git)
├── .env.example        # Environment variables template
├── .gitignore         # Git ignore rules
└── cogs/
    └── rules.py       # Rules acceptance cog
```

## Support

For issues or questions, please open an issue on GitHub.
