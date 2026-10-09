# Relic Bot

这是一个 Discord 机器人项目的公开源码快照，包含经验、签到、经济系统、阿瓦隆和若干社区工具模块。

## 公开快照边界

本目录是从当前源码树重新初始化的单提交快照，不包含原私有仓库历史、环境变量、数据库、备份、运行日志或用户活跃报告。公开前仍应在目标平台完成一次 secret scanning 和人工审阅。

运行时配置应放在本地 `.env`；请从 `.env.example` 复制并填写。SQLite 数据库会在本地运行时创建，不要把真实数据库提交到仓库。

源码中的 Discord 服务器、频道、角色和用户 ID 已在此公开快照中替换为占位值；部署时请在私有配置层恢复为你自己的服务器配置。

公开版不包含外部 MySQL 经济系统、跨机器人发奖协议、数据库导入工具或头像审查分割 Worker。原私有仓库中的这些功能不会随本快照发布；本目录仅作为源码阅读和基础模块展示版本。

含有样例用户昵称的 MVP 结果图片也未纳入公开版。

## 基本运行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python bot.py
```

## 安全提醒

不要提交 Discord token、OpenAI key、MySQL properties、SQLite 数据库、报告导出物或包含真实用户标识的日志。发现历史泄露时，应先轮换凭据，再清理托管平台上的对象和缓存。
