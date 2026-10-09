# Relic Bot

Choose a language / 选择语言：

<details>
<summary><strong>English (EN)</strong></summary>

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

</details>

<details>
<summary><strong>中文 (CN)</strong></summary>

## 项目简介

这是一个面向 Discord 社区的 Python 机器人，提供社区成长、签到、晶核经济、商店、掉落、成就、迎新、私房语音频道、阿瓦隆和 OMG 截图分析等功能。

本仓库是面向公开查看和二次开发的源码版本，不包含服务器数据、真实凭据或原部署环境。首次运行前必须完成自己的 Discord 服务器配置。

## 功能概览

- **社区成长**：文字、语音和直播活跃经验、等级计算、等级身份组同步和经验衰减。
- **签到与奖励**：每日签到、连续签到、签到排行、签到活动和成就。
- **晶核经济**：余额、经验兑换、转账、掉落和本地 SQLite 商店。
- **社区工具**：新人管理、迎新/萌萌、私房语音频道维护、消息管理和文字转语音。
- **游戏功能**：阿瓦隆创建、测试、战绩和排行。
- **内容处理**：OMG 选技截图分析和可选的 OpenAI 图片反诈审查。

默认指令前缀为 `&`，可在 Discord 中使用 `&帮助` 或 `&菜单` 查看当前账号可用的指令。

## 运行环境

- Python 3.10 或更高版本
- Discord Bot 应用及 Token
- Windows、Linux 或 macOS
- 只有启用图片反诈审查时才需要 OpenAI API Key

## 快速开始

Windows PowerShell：

```powershell
git clone https://github.com/FrontBlood/IO-public-ver.git
cd IO-public-ver

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

Copy-Item .env.example .env
# 编辑 .env，至少填写 DISCORD_TOKEN
python bot.py
```

Linux/macOS：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，至少填写 DISCORD_TOKEN
python bot.py
```

## Discord 应用配置

1. 在 [Discord Developer Portal](https://discord.com/developers/applications) 创建 Application 并添加 Bot。
2. 将 Bot Token 填入本地 `.env` 的 `DISCORD_TOKEN`。
3. 在 Bot 设置中开启 **Message Content Intent** 和 **Server Members Intent**。机器人还会监听语音状态事件，因此需要能够访问目标语音频道。
4. 使用 OAuth2 的 `bot` scope 邀请机器人；只有在扩展应用命令时才需要添加 `applications.commands` scope。
5. 根据启用的模块授予所需权限：
   - **基础功能**：查看频道、发送消息、嵌入链接、上传文件、读取历史消息。
   - **图片审查与清理**：管理消息、管理成员。
   - **身份组同步、签到活动和新人标签**：管理身份组，并确保机器人最高身份组位于需要管理的身份组之上。
   - **私房语音频道管理**：管理频道。
   - **语音经验和 TTS**：连接、说话，并允许访问相关语音状态事件。

## 首次配置

公开版已将服务器相关 ID 替换为 `0` 占位值。启动前请替换为自己服务器的 ID，或关闭不使用的模块。

### 需要检查的配置文件

| 文件 | 需要配置的内容 |
| --- | --- |
| `config/constants.py` | 公告频道、管理身份组、签到活动频道、商店管理员、掉落频道与管理员、私房分类等 ID |
| `config/level_roles.py` | 各等级对应的 Discord Role ID |
| `config/mengmeng_config.py` | 萌萌、迎新和迎新管理身份组 ID |
| `config/mention_guard_config.py` | 提及保护的例外身份组和频道规则 |
| `config/moderation_config.py` | 图片审查开关、监控/排除频道、告警频道和告警身份组 |

获取 Discord ID：在 Discord 用户设置中开启开发者模式，然后右键频道、身份组或成员，选择“复制 ID”。

### 环境变量

`.env.example` 只包含运行时密钥，并且保持为空：

```dotenv
DISCORD_TOKEN=
OPENAI_API_KEY=
```

`DISCORD_TOKEN` 是启动所必需的。`OPENAI_API_KEY` 是可选项；未填写时机器人仍可启动，但不会把图片发送到 OpenAI API 做诈骗分类。

其他可选环境变量：

- `TTS_VOICE`、`TTS_READ1_VOICE`、`TTS_READ2_VOICE`：设置 TTS 音色。
- `TTS_MAX_TEXT_LENGTH`、`TTS_IDLE_DISCONNECT_SECONDS`：设置 TTS 文本长度和空闲断开时间。
- `DB_BACKUP_ROOT`、`DB_BACKUP_RETENTION_DAYS`、`DB_BACKUP_MAX_COPIES`：设置数据库备份位置和保留策略。

## 数据与隐私

机器人默认使用本地 SQLite 保存等级、签到、晶核、商店、阿瓦隆、私房状态等数据。数据库会在项目根目录运行时自动创建，文件名包括 `levels.db`、`currency.db`、`checkin.db`、`shop.db` 和 `avalon.db` 等，并已被 `.gitignore` 忽略。

不要将数据库、日志、备份或用户活跃报告提交到公开仓库。生产环境请将备份目录放在 Git 工作区之外，并确认没有被 Git 跟踪。

### 图片反诈审查

启用后，带图片的消息会被下载、缩放、转换为 JPEG，并发送到 OpenAI API 分类。命中规则的消息可能被删除，发送者可能被临时禁言，近期消息也可能被清理。启用前请确认符合服务器隐私政策，并授予机器人所需权限。

本公开版不包含外部 MySQL 经济系统、跨机器人经济协议、数据库导入工具和头像分割审查 Worker。这些组件不会由本仓库启动；如需类似能力，请单独实现，并将服务凭据保存在私有部署环境中。

## 常用指令

普通成员可使用：

| 指令 | 作用 |
| --- | --- |
| `&帮助` | 查看当前账号可用的指令 |
| `&rank` | 查看自己的等级 |
| `&签到` | 每日签到 |
| `&签到天数` | 查看连续签到信息 |
| `&签到排行` | 查看签到排行 |
| `&成就` | 查看成就进度 |
| `&晶核余额` | 查看晶核余额 |
| `&兑换晶核 类型 数量` | 用经验兑换晶核 |
| `&转账晶核 @成员 数量` | 向成员转账晶核 |
| `&商店` | 打开商店 |
| `&购买 商品名` | 购买商品 |
| `&阿瓦隆` | 创建阿瓦隆游戏 |
| `&阿瓦隆规则` | 查看阿瓦隆规则 |
| `&OMG` + 图片 | 分析 OMG 选技截图 |

管理员指令会根据 Discord 管理员权限或配置的管理身份组显示在 `&帮助` 中，包括掉落控制、等级组巡检、私房巡检、经验/晶核调整、成就管理和活动管理等。

## 测试

安装运行依赖后，再安装测试工具：

```bash
python -m pip install pytest
python -m pytest
```

正式使用前，建议在单独的测试服务器验证权限、身份组顺序、频道 ID、数据库备份和自动清理行为。

## 公开版边界

这是一个可运行、供查看和二次开发的基础源码版本，不是零配置的托管服务。每个 Discord 服务器的频道、身份组、权限和隐私要求都不同，部署者需要自行完成配置和审查。

不要在 Issue 或 Pull Request 中提交 Token、API Key、数据库、备份、日志、用户报告或真实服务器配置。安全问题请参考 [SECURITY.md](SECURITY.md)，通过私下渠道报告。

## 许可证

当前仓库未附带 `LICENSE` 文件。公开访问本身不代表自动授予复制、修改或再分发权限。如果希望外部用户复用项目，请补充合适的开源许可证，或联系维护者确认授权范围。

</details>
