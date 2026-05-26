"""Web 服务器 - 提供 HTML 页面供用户在浏览器中操作生成脚本"""

import html as html_module
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs
import sys
from pathlib import Path

# 获取当前脚本所在目录（如 skills/your_skill/scripts/）
SCRIPT_DIR = Path(__file__).parent
# 将根目录加入搜索路径
sys.path.append(str(SCRIPT_DIR))
sys.path.append(str(SCRIPT_DIR.parent)) # 通常需3级返回：scripts → skill_dir → skills → root

from models import DBConfig
from config_manager import ConfigManager
from script_generator import ScriptGenerator
from type_handler import TypeHandler, SUPPORTED_TYPES

logger = logging.getLogger(__name__)


class SqlScriptRequestHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器"""

    default_config: dict = {}
    config_manager: ConfigManager = None

    def do_GET(self):
        if self.path == "/" or self.path == "":
            self._handle_index()
        elif self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        else:
            # 其他未知路径重定向到首页
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()

    def do_POST(self):
        if self.path == "/generate":
            self._handle_generate()
        else:
            self.send_error(404, "接口不存在")

    def _handle_index(self):
        self._send_html(self._render_index_page())

    def _handle_generate(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            params = parse_qs(body)

            type_name = params.get("type", [""])[0]
            entity = params.get("entity", [""])[0]
            number = params.get("number", [""])[0]
            filter_cond = params.get("filter", [""])[0]

            # 收集用户输入，用于回填表单
            form_values = {
                "type": type_name,
                "entity": entity,
                "number": number,
                "filter": filter_cond,
                "db_type": params.get("db_type", ["postgresql"])[0],
                "host": params.get("db_host", ["localhost"])[0],
                "port": params.get("db_port", ["5432"])[0],
                "username": params.get("db_username", [""])[0],
                "password": params.get("db_password", [""])[0],
                "meta_database": params.get("meta_database", [""])[0],
                "sys_database": params.get("sys_database", [""])[0],
                "workflow_database": params.get("workflow_database", [""])[0],
                "biz_database": params.get("biz_database", [""])[0],
            }

            if not type_name:
                self._send_html(self._render_index_page(
                    error="请选择脚本类型", form_values=form_values))
                return

            db_configs = self._build_db_configs_from_form(params)
            generator = ScriptGenerator()
            handler = TypeHandler(generator, db_configs)
            script = handler.dispatch(type_name, {
                "entity": entity, "number": number, "filter": filter_cond,
            })
            self._send_html(self._render_index_page(
                form_values=form_values, script=script, script_type=type_name))

        except Exception as e:
            logger.error("生成脚本失败: %s", e)
            self._send_html(self._render_index_page(
                error=str(e), form_values=form_values if 'form_values' in dir() else {}))

    def _send_html(self, html: str):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _build_db_configs_from_form(self, params: dict) -> dict:
        """从表单参数构建数据库配置（公共参数 + 各自数据库名）"""
        common = {
            "host": params.get("db_host", ["localhost"])[0],
            "port": int(params.get("db_port", ["5432"])[0] or "5432"),
            "username": params.get("db_username", [""])[0],
            "password": params.get("db_password", [""])[0],
            "db_type": params.get("db_type", ["postgresql"])[0],
        }
        configs = {}
        for key in ("meta", "sys", "workflow", "biz"):
            configs[key] = DBConfig(
                host=common["host"],
                port=common["port"],
                database=params.get(f"{key}_database", [""])[0],
                username=common["username"],
                password=common["password"],
                db_type=common["db_type"],
            )
        return configs

    def log_message(self, format, *args):
        logger.info(format, *args)

    def _render_index_page(self, error: str = "", form_values: dict = None,
                           script: str = "", script_type: str = "") -> str:
        defaults = self.default_config or {}
        fv = form_values or {}
        # 表单值：优先用用户提交的值，其次用配置默认值
        v_type = fv.get("type", "")
        v_entity = html_module.escape(fv.get("entity", ""))
        v_number = html_module.escape(fv.get("number", ""))
        v_filter = html_module.escape(fv.get("filter", ""))
        v_db_type = fv.get("db_type", "") or defaults.get("db_type", "postgresql")
        v_host = fv.get("host", "") or defaults.get("host", "localhost")
        v_port = fv.get("port", "") or defaults.get("port", "5432")
        v_username = fv.get("username", "") or defaults.get("username", "")
        v_password = fv.get("password", "") or defaults.get("password", "")
        v_meta_db = fv.get("meta_database", "") or defaults.get("meta_database", "")
        v_sys_db = fv.get("sys_database", "") or defaults.get("sys_database", "")
        v_wf_db = fv.get("workflow_database", "") or defaults.get("workflow_database", "")
        v_biz_db = fv.get("biz_database", "") or defaults.get("biz_database", "")

        error_html = f'<div class="error">{html_module.escape(error)}</div>' if error else ""

        # 类型中文显示名
        type_labels = {
            "coderule": "编码规则",
            "import": "导入导出模板",
            "event": "订阅事件",
            "perm": "权限项",
            "schdule": "调度计划",
            "basedata": "预置基础资料数据",
            "openapi": "开放API服务",
        }

        type_options = ""
        for t in SUPPORTED_TYPES:
            selected = "selected" if t == v_type else ""
            label = type_labels.get(t, t)
            type_options += f'<option value="{t}" {selected}>{label}</option>'

        # 脚本结果区域
        script_html = ""
        if script:
            escaped_script = html_module.escape(script)
            script_html = f"""
            <div class="section-title">生成结果（{html_module.escape(script_type)}）
                <button class="btn btn-copy" onclick="copyScript()" style="margin-left:12px;font-size:13px;padding:4px 12px;">复制脚本</button>
            </div>
            <pre class="script-area" id="scriptContent">{escaped_script}</pre>
            <script>
                function copyScript() {{
                    const text = document.getElementById('scriptContent').innerText;
                    navigator.clipboard.writeText(text).then(() => {{
                        const btn = document.querySelector('.btn-copy');
                        btn.innerText = '已复制!';
                        setTimeout(() => {{ btn.innerText = '复制脚本'; }}, 2000);
                    }}).catch(err => {{
                        const ta = document.createElement('textarea');
                        ta.value = text;
                        document.body.appendChild(ta);
                        ta.select();
                        document.execCommand('copy');
                        document.body.removeChild(ta);
                        const btn = document.querySelector('.btn-copy');
                        btn.innerText = '已复制!';
                        setTimeout(() => {{ btn.innerText = '复制脚本'; }}, 2000);
                    }});
                }}
            </script>"""

        def _sel(val, target):
            return "selected" if val == target else ""

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>SQL脚本生成器</title>
    <style>
        body {{ font-family: "Microsoft YaHei", sans-serif; max-width: 960px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        h1 {{ color: #333; text-align: center; }}
        .container {{ background: #fff; padding: 24px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .form-row {{ margin: 8px 0; display: flex; align-items: center; }}
        .form-row label {{ width: 120px; font-weight: bold; }}
        .form-row input, .form-row select {{ flex: 1; padding: 6px 10px; border: 1px solid #ddd; border-radius: 4px; }}
        fieldset {{ margin: 12px 0; padding: 12px; border: 1px solid #ddd; border-radius: 4px; }}
        legend {{ font-weight: bold; color: #555; }}
        .btn {{ background: #1890ff; color: #fff; border: none; padding: 10px 24px; border-radius: 4px; cursor: pointer; font-size: 15px; }}
        .btn:hover {{ background: #40a9ff; }}
        .btn-copy {{ background: #52c41a; color: #fff; border: none; border-radius: 4px; cursor: pointer; }}
        .btn-copy:hover {{ background: #73d13d; }}
        .error {{ background: #fff2f0; border: 1px solid #ffccc7; color: #ff4d4f; padding: 10px; border-radius: 4px; margin: 12px 0; }}
        .section-title {{ font-size: 16px; font-weight: bold; margin: 16px 0 8px; color: #333; }}
        .script-area {{ background: #282c34; color: #abb2bf; padding: 16px; border-radius: 4px; overflow-x: auto; white-space: pre-wrap; word-break: break-all; font-family: Consolas, monospace; font-size: 13px; max-height: 600px; overflow-y: auto; }}
    </style>
</head>
<body>
    <h1>SQL脚本生成器</h1>
    <div class="container">
        {error_html}
        <form method="POST" action="/generate">
            <div class="section-title">脚本类型与参数</div>
            <div class="form-row">
                <label>脚本类型:</label>
                <select name="type">{type_options}</select>
            </div>
            <div class="form-row">
                <label>实体编码:</label>
                <input type="text" name="entity" value="{v_entity}" placeholder="如 bd_currency（coderule/import/event/basedata 类型使用）">
            </div>
            <div class="form-row">
                <label>编码列表:</label>
                <input type="text" name="number" value="{v_number}" placeholder="如 QXX0114,QXX0115（perm/schdule 类型使用）">
            </div>
            <div class="form-row">
                <label>过滤条件:</label>
                <input type="text" name="filter" value="{v_filter}" placeholder="如 fnumber in ('CNY','USD')（basedata 类型使用）">
            </div>

            <details>
            <summary class="section-title" style="cursor:pointer;">数据库连接配置 ▸</summary>
            <fieldset>
                <legend>公共连接参数</legend>
                <div class="form-row">
                    <label>数据库类型:</label>
                    <select name="db_type">
                        <option value="postgresql" {_sel(v_db_type, "postgresql")}>PostgreSQL</option>
                        <option value="mysql" {_sel(v_db_type, "mysql")}>MySQL</option>
                        <option value="oracle" {_sel(v_db_type, "oracle")}>Oracle</option>
                        <option value="sqlserver" {_sel(v_db_type, "sqlserver")}>SQL Server</option>
                    </select>
                </div>
                <div class="form-row">
                    <label>主机:</label>
                    <input type="text" name="db_host" value="{v_host}">
                </div>
                <div class="form-row">
                    <label>端口:</label>
                    <input type="text" name="db_port" value="{v_port}">
                </div>
                <div class="form-row">
                    <label>用户名:</label>
                    <input type="text" name="db_username" value="{v_username}">
                </div>
                <div class="form-row">
                    <label>密码:</label>
                    <input type="password" name="db_password" value="{v_password}">
                </div>
            </fieldset>
            <fieldset>
                <legend>数据库名称</legend>
                <div class="form-row">
                    <label>元数据库:</label>
                    <input type="text" name="meta_database" value="{v_meta_db}">
                </div>
                <div class="form-row">
                    <label>系统库:</label>
                    <input type="text" name="sys_database" value="{v_sys_db}">
                </div>
                <div class="form-row">
                    <label>工作流库:</label>
                    <input type="text" name="workflow_database" value="{v_wf_db}">
                </div>
                <div class="form-row">
                    <label>业务库:</label>
                    <input type="text" name="biz_database" value="{v_biz_db}">
                </div>
            </fieldset>
            </details>

            <div style="text-align: center; margin-top: 16px;">
                <button type="submit" class="btn">生成脚本</button>
            </div>
        </form>
        {script_html}
    </div>
</body>
</html>"""


class SqlScriptWebServer:
    """Web 服务器封装"""

    def __init__(self, host: str = "localhost", port: int = 8089):
        self.host = host
        self.port = port

    def start(self):
        server = HTTPServer((self.host, self.port), SqlScriptRequestHandler)
        print(f"SQL脚本生成器 Web 服务已启动: http://{self.host}:{self.port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n服务已停止")
            server.server_close()
