# MCP 目录

## 定位
- `/Users/anfeng/AI/mcp` 是本机 MCP 服务统一源目录。
- 活跃服务放在 `active/`；历史实现、替代实现和停用服务放在 `legacy/`。
- Claude、Codex、VS Code、Kimi、Gemini 等工具只引用 `active/` 中的服务入口。
- MCP 服务配置不写密钥、账号、临时 token、客户地址或生产库密码。

## 活跃服务
| 名称 | 入口 | 用途 | 运行方式 |
|---|---|---|---|
| `kingdee-knowledge` | `active/kingdee-knowledge/mcp-server.js` | 检索金蝶云苍穹知识库 | `node active/kingdee-knowledge/mcp-server.js` |
| `search-web` | `active/search-web/search_mcp_server.py` | 联网搜索、页面抓取、证据包生成 | `python3 active/search-web/search_mcp_server.py stdio` |
| `doc-reader` | `active/doc-reader/app/main.py` | 读取 docx、xlsx 文档内容 | `python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000` |

## 配置入口
- Claude Code: `/Users/anfeng/.claude/settings.json`
- Claude 本地权限: `/Users/anfeng/.claude/settings.local.json`
- 项目 VS Code MCP: `/Users/anfeng/Code/Work/ztjg/.vscode/mcp.json`
- MCP 清单: `inventory/mcp-inventory.md`

## 规则
- 新增 MCP 先进入 `active/<name>` 或 `legacy/<name>`，不得散落在项目根、工具根或客户端配置目录。
- 客户端配置只写服务启动入口，不复制服务源码。
- 需要停用的 MCP 移入 `legacy/`，并删除客户端配置引用。
- 服务日志、依赖和运行产物留在对应 MCP 目录内，不进入知识库正文。
