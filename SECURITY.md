# Security Policy

Choose a language / 选择语言：

<details>
<summary><strong>English (EN)</strong></summary>

## Report a vulnerability

If the repository's **Security** tab offers **Report a vulnerability**, use it to send details privately. Otherwise, open an Issue requesting a private way to contact the repository owner. Do not include exploit steps, credentials, or user data in a public Issue.

Include the affected component, what you observed, and the minimum steps needed to reproduce the problem. Remove tokens, API keys, Discord IDs, database contents, and personal information from screenshots and logs before sharing them.

## Protect your deployment

Keep `DISCORD_TOKEN` and `OPENAI_API_KEY` in a local `.env` file or your deployment's secret store. Do not commit `.env`, SQLite databases, backups, generated reports, or logs. If a credential is exposed, revoke or rotate it with its provider.

</details>

<details>
<summary><strong>中文 (CN)</strong></summary>

## 报告安全问题

如果仓库的 **Security** 页面提供 **Report a vulnerability**，请通过该入口私下提交详情。若没有该入口，请创建一个 Issue 请求与仓库所有者私下联系；公开 Issue 中不要放入漏洞利用步骤、凭据或用户数据。

报告中请写明受影响的组件、观察到的现象和最少的复现步骤。分享截图或日志前，请移除 Token、API Key、Discord ID、数据库内容及个人信息。

## 保护自己的部署

将 `DISCORD_TOKEN` 和 `OPENAI_API_KEY` 保存在本地 `.env` 或部署平台的密钥存储中。不要提交 `.env`、SQLite 数据库、备份、生成的报告或日志。如果凭据泄露，请到对应服务提供方撤销或轮换。

</details>
