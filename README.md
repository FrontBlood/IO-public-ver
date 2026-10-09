# Relic Bot

A Python Discord bot for community progression, check-ins, virtual currency, shops, drops, achievements, onboarding, private voice rooms, Avalon, OMG screenshot analysis, and optional image scam moderation.

This repository is a public source release for review and further development. It does not include server data, real credentials, or the original deployment environment. You must configure it for your own Discord server before running it.

## Features

- **Community progression**: text, voice, and streaming activity XP; levels; role synchronization; and XP decay.
- **Check-ins and rewards**: daily check-ins, streaks, leaderboards, events, and achievements.
- **Virtual economy**: balances, XP exchange, transfers, drops, and a local SQLite shop.
- **Community tools**: newcomer management, onboarding, private voice-room maintenance, message management, and text-to-speech.
- **Games**: Avalon lobby creation, test mode, player statistics, and leaderboards.
- **Content processing**: OMG skill-screen analysis and optional OpenAI image scam moderation.

Use `&帮助` or `&菜单` in Discord to view the commands available to the current account. The default command prefix is `&`.

## Requirements

- Python 3.10 or later
- A Discord Bot application and token
- Windows, Linux, or macOS
- An OpenAI API key only if you enable image scam moderation

## Quick start

```powershell
git clone https://github.com/FrontBlood/IO-public-ver.git
cd IO-public-ver

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

Copy-Item .env.example .env
# Edit .env and set at least DISCORD_TOKEN
python bot.py
```

On Linux or macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set at least DISCORD_TOKEN
python bot.py
```

## Discord setup

1. Create an Application and add a Bot in the [Discord Developer Portal](https://discord.com/developers/applications).
2. Copy the Bot Token into `DISCORD_TOKEN` in your local `.env` file.
3. Enable **Message Content Intent** and **Server Members Intent** in the Bot settings. The bot also listens for voice-state events, so it must be able to access the target voice channels.
4. Invite the bot with the OAuth2 `bot` scope. Add `applications.commands` only if you extend the project with application commands.
5. Grant only the permissions required by the modules you use:
   - **Core features**: View Channel, Send Messages, Embed Links, Attach Files, and Read Message History.
   - **Image moderation and cleanup**: Manage Messages and Moderate Members.
   - **Role synchronization, check-in events, and newcomer tags**: Manage Roles. Keep the bot's highest role above the roles it must assign.
   - **Private voice-room management**: Manage Channels.
   - **Voice XP and TTS**: Connect and Speak, plus access to the relevant voice-state events.

## Initial configuration

Server-specific IDs in this public release have been replaced with `0` placeholders. Before starting the bot, replace them with IDs from your own server or disable the modules you do not use.

### Configuration files to review

| File | What to configure |
| --- | --- |
| `config/constants.py` | Announcement channels, management roles, check-in event channels, shop admins, drop channels and roles, private-room categories, and related IDs |
| `config/level_roles.py` | Discord Role IDs for each level |
| `config/mengmeng_config.py` | Mengmeng, onboarding, and onboarding-admin role IDs |
| `config/mention_guard_config.py` | Mention-protection exemptions and channel rules |
| `config/moderation_config.py` | Image-moderation switch, watched/excluded channels, alert channel, and alert role |

To copy a Discord ID, enable Developer Mode in Discord, then right-click the relevant channel, role, or member and choose **Copy ID**.

### Environment variables

`.env.example` contains only runtime secrets and is intentionally blank:

```dotenv
DISCORD_TOKEN=
OPENAI_API_KEY=
```

`DISCORD_TOKEN` is required to start the bot. `OPENAI_API_KEY` is optional; without it, the bot can start but will not send images to the OpenAI API for scam classification.

Optional environment variables include:

- `TTS_VOICE`, `TTS_READ1_VOICE`, and `TTS_READ2_VOICE` for TTS voices.
- `TTS_MAX_TEXT_LENGTH` and `TTS_IDLE_DISCONNECT_SECONDS` for TTS limits.
- `DB_BACKUP_ROOT`, `DB_BACKUP_RETENTION_DAYS`, and `DB_BACKUP_MAX_COPIES` for database backup location and retention.

## Data and privacy

The bot stores levels, check-ins, currency, shop records, Avalon state, private-room state, and related data in local SQLite files. These files are created in the project root at runtime, including names such as `levels.db`, `currency.db`, `checkin.db`, `shop.db`, and `avalon.db`. They are ignored by `.gitignore`.

Do not commit databases, logs, backups, or user activity reports. In production, configure a backup directory outside the Git working tree and verify that it is not being tracked.

### Image scam moderation

When enabled, image attachments are downloaded, resized, converted to JPEG, and sent to the OpenAI API for classification. A matching message may be deleted, its author may be temporarily timed out, and recent messages may be cleaned up. Review your server's privacy policy and grant the bot the required permissions before enabling this feature.

This public release does not provide the external MySQL economy system, cross-bot economy protocol, database import tools, or avatar segmentation worker from the private deployment. Those components are not started by this repository. If you need similar functionality, implement and operate it separately with private service credentials.

## Common commands

The following commands are available to regular members:

| Command | Description |
| --- | --- |
| `&帮助` | Show commands available to the current account |
| `&rank` | Show your level |
| `&签到` | Check in for the day |
| `&签到天数` | Show check-in streak information |
| `&签到排行` | Show the check-in leaderboard |
| `&成就` | Show achievement progress |
| `&晶核余额` | Show your currency balance |
| `&兑换晶核 类型 数量` | Exchange XP for currency |
| `&转账晶核 @成员 数量` | Transfer currency to a member |
| `&商店` | Open the shop |
| `&购买 商品名` | Purchase an item |
| `&阿瓦隆` | Create an Avalon game |
| `&阿瓦隆规则` | Show the Avalon rules |
| `&OMG` + image | Analyze an OMG skill screenshot |

Administrative commands are shown by `&帮助` according to Discord administrator permissions or the configured management roles. They include drop controls, role checks, private-room checks, XP/currency adjustments, achievement management, and event management.

## Testing

Install the runtime dependencies, then install the test runner:

```bash
python -m pip install pytest
python -m pytest
```

Before using the bot in production, test it in a separate Discord server and verify permissions, role ordering, channel IDs, database backups, and automated cleanup behavior.

## Public-release scope

This is a runnable foundation for review and adaptation, not a zero-configuration hosted service. Every Discord server has different channels, roles, permissions, and privacy requirements, so deployment owners must complete their own configuration and review.

Do not submit tokens, API keys, databases, backups, logs, user reports, or real server configuration in Issues or Pull Requests. For security reports, see [SECURITY.md](SECURITY.md) and use a private reporting channel.

## License

This repository currently does not include a `LICENSE` file. Public visibility alone does not grant additional permission to copy, modify, or redistribute the code. If you want external users to reuse the project, add an appropriate open-source license or contact the maintainer about the intended permission scope.

<details>
<summary>中文附录（简要说明）</summary>

## 中文附录

这是一个面向 Discord 社区的 Python 机器人，包含等级经验、签到、晶核经济、商店、掉落、成就、迎新、私房语音频道、阿瓦隆和 OMG 截图分析等功能。

公开版不包含真实 Token、API Key、数据库、日志、用户报告或原部署环境。运行前请：

1. 安装 Python 3.10+ 和 `requirements.txt` 中的依赖；
2. 从 `.env.example` 创建 `.env` 并填写 `DISCORD_TOKEN`；
3. 在 Discord Developer Portal 开启 Message Content Intent 和 Server Members Intent；
4. 将 `config/constants.py`、`config/level_roles.py`、`config/mengmeng_config.py`、`config/mention_guard_config.py` 和 `config/moderation_config.py` 中的 `0` 占位 ID 替换为自己服务器的配置；
5. 根据启用的功能授予机器人消息、身份组、频道、语音和内容管理权限。

图片反诈审查使用 OpenAI API。启用并配置 `OPENAI_API_KEY` 后，图片会被下载、压缩并发送给 OpenAI 分类；这不是本地审查，也没有对图片中的用户名、头像或文字做完全脱敏。未配置 API Key 时，机器人仍可启动，但不会进行云端图片分类。

公开版不包含外部 MySQL 经济系统、跨机器人经济协议、数据库导入工具和头像分割 Worker。SQLite 数据库会在本地运行时创建，请勿提交到公开仓库。

</details>
