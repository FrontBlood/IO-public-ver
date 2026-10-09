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

Use `&帮助` or `&菜单` in Discord for the built-in command menu. It is not a complete list of every command. The default command prefix is `&`.

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

`DISCORD_TOKEN` is required to start the bot. `OPENAI_API_KEY` is optional. Without it, the image guard still examines image attachments locally and writes diagnostic logs, but it does not send images to OpenAI. To turn the guard off, set `SCAM_IMAGE_GUARD_ENABLED = False` in `config/moderation_config.py`.

Optional environment variables include:

- `TTS_VOICE`, `TTS_READ1_VOICE`, and `TTS_READ2_VOICE` for TTS voices.
- `TTS_MAX_TEXT_LENGTH` and `TTS_IDLE_DISCONNECT_SECONDS` for TTS limits.
- `DB_BACKUP_ROOT`, `DB_BACKUP_RETENTION_DAYS`, and `DB_BACKUP_MAX_COPIES` for database backup location and retention.

## Data and privacy

The bot stores levels, check-ins, currency, shop records, Avalon state, private-room state, and related data in local SQLite files. Database paths are relative to the process's working directory. If you run `python bot.py` from the repository root, files such as `levels.db`, `currency.db`, `checkin.db`, `shop.db`, and `avalon.db` are created there. Some are initialized at startup; others are created when their features are first used. The repository's `.gitignore` excludes `*.db` files.

The bot attempts a database backup before its daily 05:00 restart, using the host's local time. By default, backups are saved under `db_backups/` in the repository and excluded by `.gitignore`. Set `DB_BACKUP_ROOT` to a directory outside the repository for production. If backup fails, that day's restart is canceled. Keep database files, backup copies, logs, and exported activity reports out of public commits; `.gitignore` does not remove files already tracked by Git.

### Image scam moderation

`SCAM_IMAGE_GUARD_ENABLED` is `True` by default. For non-bot messages with image attachments, the guard checks the configured channel scope, downloads eligible images, and converts them to JPEG. With an API key it sends the converted image to OpenAI for classification; visible content is not anonymized. Without an API key it does not send the image to OpenAI, but local downloading and diagnostic logging still occur. A positive result can delete the triggering message, time out its author, and remove recent messages where the bot has permission. The default empty `MOD_WATCH_CHANNEL_IDS` list covers all channels except those in `MOD_EXCLUDE_CHANNEL_IDS`. Set `SCAM_IMAGE_GUARD_ENABLED = False` to disable this image path, or configure a limited watch list before deployment. The logs include message, user, and channel IDs and attachment metadata.


## Common commands

Examples of member commands (some have additional conditions):

| Command | Description |
| --- | --- |
| `&帮助` | Show the built-in command menu |
| `&rank` | Show your level |
| `&签到` | Check in for the day when no check-in event has locked this command |
| `&签到天数` | Show check-in streak information |
| `&签到排行` | Show the check-in leaderboard |
| `&成就` | Show achievement progress |
| `&晶核余额` | Show your currency balance |
| `&兑换晶核 类型 数量` | Exchange XP for currency |
| `&转账晶核 @成员 数量` | Transfer currency to a member after reaching total level 5 |
| `&商店` | Open the shop |
| `&购买 商品名` | Purchase an item |
| `&阿瓦隆` | Create an Avalon game |
| `&阿瓦隆规则` | Show the Avalon rules |
| `&OMG` + image | Analyze an OMG skill screenshot |

The `&帮助` menu shows different command groups according to Discord administrator permissions or the configured management role. It is not an exhaustive list; additional game and event commands are implemented outside that menu.

## Testing

Install the runtime dependencies, then install the test runner:

```bash
python -m pip install pytest
python -m pytest
```

Before using the bot in production, test it in a separate Discord server and verify permissions, role ordering, channel IDs, database backups, and automated cleanup behavior.

## Project scope

This is source code for a self-hosted Discord bot. Configure its channels, roles, permissions, and privacy settings for your server before use.

The economy uses local SQLite storage. This repository does not include remote database synchronization, cross-bot economy features, or avatar screening.

For vulnerability reports and guidance on sharing diagnostic information, see [SECURITY.md](SECURITY.md).

## License

This project is licensed under the [MIT License](LICENSE). You may use, modify, and redistribute it, including commercially, provided you retain the copyright and license notice. The software is provided without warranty.

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

默认指令前缀为 `&`。可在 Discord 中使用 `&帮助` 或 `&菜单` 查看内置指令菜单；菜单并未列出全部指令。

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

`DISCORD_TOKEN` 是启动所必需的。`OPENAI_API_KEY` 是可选项。未填写时，图片审查模块仍会在本地读取图片附件并写入诊断日志，但不会将图片发送到 OpenAI。要关闭该模块，请在 `config/moderation_config.py` 中将 `SCAM_IMAGE_GUARD_ENABLED` 设为 `False`。

其他可选环境变量：

- `TTS_VOICE`、`TTS_READ1_VOICE`、`TTS_READ2_VOICE`：设置 TTS 音色。
- `TTS_MAX_TEXT_LENGTH`、`TTS_IDLE_DISCONNECT_SECONDS`：设置 TTS 文本长度和空闲断开时间。
- `DB_BACKUP_ROOT`、`DB_BACKUP_RETENTION_DAYS`、`DB_BACKUP_MAX_COPIES`：设置数据库备份位置和保留策略。

## 数据与隐私

机器人使用本地 SQLite 保存等级、签到、晶核、商店、阿瓦隆、私房状态等数据。数据库路径相对于启动进程时的工作目录；如果在仓库根目录执行 `python bot.py`，`levels.db`、`currency.db`、`checkin.db`、`shop.db` 和 `avalon.db` 等文件会在那里生成。一部分在启动时初始化，其余在首次使用对应功能时创建。仓库的 `.gitignore` 会忽略 `*.db` 文件。

机器人会在每天按主机本地时间 05:00 重启前尝试备份数据库。默认备份到仓库内被 `.gitignore` 忽略的 `db_backups/`；生产部署可通过 `DB_BACKUP_ROOT` 指向仓库外的目录。备份失败会取消当次重启。不要公开提交数据库、备份、日志或导出的活跃报告；`.gitignore` 不会自动移除已经被 Git 跟踪的文件。

### 图片反诈审查

`SCAM_IMAGE_GUARD_ENABLED` 默认是 `True`。对于非机器人发送的带图消息，模块会检查频道范围、下载符合条件的图片并转换为 JPEG。配置 API Key 后，转换后的图片会发送到 OpenAI 分类，图片中的可见内容不会匿名化。没有 API Key 时不会发送图片，但仍会发生本地下载和诊断日志记录。判为命中后，机器人可能删除该消息、临时禁言发送者，并在权限允许的频道清理近期消息。默认空的 `MOD_WATCH_CHANNEL_IDS` 列表表示监控所有未列入 `MOD_EXCLUDE_CHANNEL_IDS` 的频道。部署前可将 `SCAM_IMAGE_GUARD_ENABLED` 设为 `False`，或配置仅监控指定频道。日志会包含消息、用户、频道 ID 和附件元数据。


## 常用指令

以下是成员指令示例，部分指令还有额外使用条件：

| 指令 | 作用 |
| --- | --- |
| `&帮助` | 查看内置指令菜单 |
| `&rank` | 查看自己的等级 |
| `&签到` | 未被签到活动锁定时进行每日签到 |
| `&签到天数` | 查看连续签到信息 |
| `&签到排行` | 查看签到排行 |
| `&成就` | 查看成就进度 |
| `&晶核余额` | 查看晶核余额 |
| `&兑换晶核 类型 数量` | 用经验兑换晶核 |
| `&转账晶核 @成员 数量` | 总等级达到 5 级后向成员转账晶核 |
| `&商店` | 打开商店 |
| `&购买 商品名` | 购买商品 |
| `&阿瓦隆` | 创建阿瓦隆游戏 |
| `&阿瓦隆规则` | 查看阿瓦隆规则 |
| `&OMG` + 图片 | 分析 OMG 选技截图 |

`&帮助` 会根据 Discord 管理员权限或配置的管理身份组显示不同指令组，但不是完整指令清单；游戏和活动等模块还有未列入该菜单的指令。

## 测试

安装运行依赖后，再安装测试工具：

```bash
python -m pip install pytest
python -m pytest
```

正式使用前，建议在单独的测试服务器验证权限、身份组顺序、频道 ID、数据库备份和自动清理行为。

## 项目范围

这是一个可自行托管的 Discord 机器人源码项目。使用前请按照自己服务器的频道、身份组、权限和隐私要求完成配置。

经济系统使用本地 SQLite；仓库不包含远程数据库同步、跨机器人经济功能或头像审查。

漏洞报告方式及分享诊断信息时的注意事项，请参阅 [SECURITY.md](SECURITY.md)。

## 许可证

本项目采用 [MIT 许可证](LICENSE)。你可以使用、修改和再分发项目，包括商业用途，但须保留版权和许可证声明。软件按“原样”提供，不附带担保。

</details>
