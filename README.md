# Relic Bot

一个面向 Discord 社区的 Python 机器人，提供等级与活跃度、签到、晶核经济、商店、掉落、成就、迎新、私房管理、阿瓦隆和 OMG 截图分析等功能。

本仓库是可公开查看和二次开发的源码版本。它不包含任何服务器数据、真实凭据或原部署环境；首次部署前需要完成自己的 Discord 服务器配置。

## 功能概览

- **社区成长**：文字、语音和直播活跃经验，等级计算，等级身份组同步，经验衰减。
- **签到与奖励**：每日签到、连续签到、签到排行、签到活动和成就奖励。
- **晶核经济**：余额、兑换、转账、掉落和本地 SQLite 商店。
- **社区工具**：新人管理、迎新/萌萌模块、私房语音频道维护、消息管理和文字转语音。
- **游戏功能**：阿瓦隆创建、测试、战绩和排行。
- **内容处理**：OMG 选技截图分析；可选的 OpenAI 图片反诈审查。

使用 `&帮助` 或 `&菜单` 可以在 Discord 内查看当前账号可用的指令。默认指令前缀是 `&`。

## 运行环境

- Python 3.10 或更高版本
- 一个 Discord Bot 应用及其 Token
- Windows、Linux 或 macOS 均可运行；下面的命令以 Windows PowerShell 为例
- 如果启用图片反诈审查，需要 OpenAI API Key

## 快速开始

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

Linux/macOS 可使用：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
python bot.py
```

## Discord 应用配置

1. 在 [Discord Developer Portal](https://discord.com/developers/applications) 创建 Application，并添加 Bot。
2. 复制 Bot Token 到本地 `.env` 的 `DISCORD_TOKEN`。
3. 在 Bot 设置中开启 **Message Content Intent** 和 **Server Members Intent**。代码还会使用语音状态事件，因此机器人需要加入能够访问目标语音频道的服务器。
4. 通过 OAuth2 URL 将机器人邀请到服务器，至少使用 `bot` scope。若后续启用应用命令或扩展命令，再添加 `applications.commands` scope。
5. 根据实际启用的模块授予机器人权限：
   - 基础功能：查看频道、发送消息、嵌入链接、上传文件、读取历史消息。
   - 图片审查与消息清理：管理消息、管理成员（用于临时禁言）。
   - 等级身份组、签到活动和新人标签：管理身份组，并将机器人最高身份组置于目标身份组之上。
   - 私房频道管理：管理频道。
   - 语音经验和 TTS：连接、说话，并允许读取相关语音状态。

## 首次配置

公开版已经把服务器相关 ID 清空为 `0` 占位值。运行前请根据自己的服务器修改配置文件；不使用的模块可以保持默认值或关闭。

### 必须检查的配置

| 文件 | 需要配置的内容 |
| --- | --- |
| `config/constants.py` | 公告频道、管理身份组、签到活动频道、商店管理员、掉落频道与管理员、私房分类等 ID |
| `config/level_roles.py` | 等级名称对应的 Discord Role ID |
| `config/mengmeng_config.py` | 萌萌身份组、迎新身份组和迎新管理身份组 ID |
| `config/mention_guard_config.py` | 提及保护的例外身份组和频道规则 |
| `config/moderation_config.py` | 图片反诈开关、监控/排除频道、告警频道与告警身份组 |

Discord ID 的获取方式：在 Discord 用户设置中开启开发者模式，然后右键频道、身份组或成员选择“复制 ID”。

### 环境变量

`.env.example` 只包含不应提交到 Git 的运行时密钥：

```dotenv
DISCORD_TOKEN=
OPENAI_API_KEY=
```

`DISCORD_TOKEN` 是启动所必需的。`OPENAI_API_KEY` 为可选项；未填写时机器人仍可启动，但图片反诈审查不会调用云端模型。

语音和数据库备份还支持以下可选环境变量：

- `TTS_VOICE`、`TTS_READ1_VOICE`、`TTS_READ2_VOICE`：调整 TTS 音色。
- `TTS_MAX_TEXT_LENGTH`、`TTS_IDLE_DISCONNECT_SECONDS`：调整 TTS 文本长度和空闲断开时间。
- `DB_BACKUP_ROOT`、`DB_BACKUP_RETENTION_DAYS`、`DB_BACKUP_MAX_COPIES`：调整数据库备份位置和保留策略。

## 数据与隐私

机器人默认使用本地 SQLite 文件保存等级、签到、晶核、商店、阿瓦隆和私房状态等数据。数据库会在项目根目录运行时自动创建，文件名包括 `levels.db`、`currency.db`、`checkin.db`、`shop.db`、`avalon.db` 等，并已被 `.gitignore` 忽略。

不要把这些文件、日志、备份或用户活动报告提交到公开仓库。生产环境请自行设置备份目录，并在发布前确认备份目录不在 Git 工作区内。

### 图片反诈审查说明

启用图片反诈审查后，带图片的消息会被下载、压缩并发送到 OpenAI API 进行分类；命中规则的消息可能被删除，发送者可能被临时禁言，近期消息可能被清理。请在启用前确认符合你的服务器隐私政策和数据处理要求，并为机器人授予相应权限。

本公开版本不提供外部 MySQL 经济系统、跨机器人经济协议、数据库导入工具和头像分割审查 Worker。它们不会随本仓库启动；如需类似能力，请自行设计适配，并将相关凭据和服务配置留在私有部署环境中。

## 常用指令

普通成员可使用：

| 指令 | 作用 |
| --- | --- |
| `&帮助` | 查看当前可用指令 |
| `&rank` | 查看自己的等级 |
| `&签到` | 每日签到 |
| `&签到天数` | 查看连续签到信息 |
| `&签到排行` | 查看签到排行 |
| `&成就` | 查看成就进度 |
| `&晶核余额` | 查看晶核余额 |
| `&兑换晶核 类型 数量` | 用经验兑换晶核 |
| `&转账晶核 @成员 数量` | 转账晶核 |
| `&商店` | 打开商店 |
| `&购买 商品名` | 购买商品 |
| `&阿瓦隆` | 创建阿瓦隆游戏 |
| `&阿瓦隆规则` | 查看阿瓦隆规则 |
| `&OMG` + 图片 | 分析 OMG 选技截图 |

管理指令会根据管理员权限或配置的管理身份组显示在 `&帮助` 中，包括掉落控制、等级组巡检、私房巡检、经验/晶核调整、成就管理和活动管理等。

## 测试

安装运行依赖后，再安装测试工具即可运行：

```bash
python -m pip install pytest
python -m pytest
```

建议先在测试服务器验证权限、身份组顺序、频道 ID、数据库备份和自动清理行为，再邀请到正式服务器。

## 公开版边界

这是一个可运行的基础源码版本，不承诺开箱即用。由于每个 Discord 服务器的频道、身份组和权限结构不同，部署者必须完成本地配置、权限审查和隐私评估。

提交 Issue 或 Pull Request 时，请不要上传 Token、API Key、数据库、备份、日志、用户报告或真实服务器配置。安全问题请参考 [SECURITY.md](SECURITY.md) 通过私下渠道报告。

## 许可证

当前仓库未附带 `LICENSE` 文件。仓库公开访问不代表自动授予复制、修改或再分发权限；如计划向外部用户开放复用，请先补充合适的开源许可证，或联系维护者确认授权范围。
