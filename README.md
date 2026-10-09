# Relic Bot

Choose a language / 选择语言：

<details>
<summary><strong>English (EN)</strong></summary>

A Python Discord bot for community progression, check-ins, virtual currency, shops, drops, achievements, onboarding, private voice rooms, Avalon, OMG screenshot analysis, and optional image scam moderation.

The repository contains source code and example configuration. To run the bot, provide your own Discord token and server IDs.

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

Server-specific IDs are set to `0` placeholders. Replace them with IDs from your server before using the related features.

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

If an `OPENAI_API_KEY` is configured, image attachments in monitored channels are downloaded, resized, converted to JPEG, and sent to the OpenAI API for classification. Image content is not anonymized before transmission. A matching message may be deleted, its author may be temporarily timed out, and recent messages may be cleaned up. Review your server's privacy policy and grant the bot the required permissions before enabling this feature. By default, the monitored-channel list is empty, which covers all channels except any explicitly excluded channels.

The included economy uses local SQLite databases. External MySQL integration, cross-bot transfers, database import tools, and avatar segmentation are not available in this repository.

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

## Project scope

This is source code for a self-hosted Discord bot. Configure its channels, roles, permissions, and privacy settings for your server before use.

For vulnerability reports and guidance on sharing diagnostic information, see [SECURITY.md](SECURITY.md).

## License

This repository does not currently include a `LICENSE` file. Public visibility does not grant permission to copy, modify, or redistribute the code beyond what applicable law permits. Contact the repository owner if you need permission.

</details>

<details>
<summary><strong>中文 (CN)</strong></summary>

## 项目简介

这是一个面向 Discord 社区的 Python 机器人，提供社区成长、签到、晶核经济、商店、掉落、成就、迎新、私房语音频道、阿瓦隆和 OMG 截图分析等功能。

仓库提供源代码和示例配置。运行机器人时，需要填写自己的 Discord Token 和服务器 ID。

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

服务器相关 ID 当前为 `0` 占位值。使用对应功能前，请替换为自己服务器的 ID。

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

配置 `OPENAI_API_KEY` 后，受监控频道中的图片附件会被下载、缩放、转换为 JPEG，并发送到 OpenAI API 分类。发送前不会对图片内容做匿名化处理。命中规则的消息可能被删除，发送者可能被临时禁言，近期消息也可能被清理。启用前请确认符合服务器隐私政策，并授予机器人所需权限。默认监控频道列表为空，表示覆盖所有未被明确排除的频道。

仓库内的经济系统使用本地 SQLite 数据库；不提供外部 MySQL 对接、跨机器人转账、数据库导入工具或头像分割功能。

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

## 项目范围

这是一个可自行托管的 Discord 机器人源码项目。使用前请按照自己服务器的频道、身份组、权限和隐私要求完成配置。

漏洞报告方式及分享诊断信息时的注意事项，请参阅 [SECURITY.md](SECURITY.md)。

## 许可证

当前仓库未附带 `LICENSE` 文件。公开可见不代表获得复制、修改或再分发许可；如需使用许可，请联系仓库所有者。

</details>
