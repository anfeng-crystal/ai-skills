# KSQL Config Management

## Discovery Order

`scripts/config_resolver.py` 按以下顺序发现配置：

1. 命令行 `--config`
2. 当前项目 `.kingdee/ksql/config.ini`
3. 当前项目 `config/kingdee/ksql/config.ini`
4. 本 skill 的 `templates/config.example.ini`

`--cwd` 用于指定当前项目目录；未指定时使用进程当前工作目录。

## Commands

```bash
python3 scripts/config_resolver.py --cwd /path/to/project --print
python3 scripts/config_resolver.py --cwd /path/to/project --json
python3 scripts/config_resolver.py --config /path/to/config.ini --print
```

## Git Safety

真实 `config.ini` 允许本地存在，但默认不应被 Git 跟踪。提交前运行：

```bash
python3 scripts/git_secret_guard.py --repo /path/to/project --json
```

该检查只读，不会修改文件、索引或工作区。

## Template Fields

`templates/config.example.ini` 只保留示例值：

- `[server] host/port`
- `[database] db_type/host/port/username/password`
- `meta_database/sys_database/workflow_database/biz_database`

真实配置建议放在项目内 `.kingdee/ksql/config.ini`，并在项目 `.gitignore` 中忽略 `.kingdee/` 或至少忽略该文件。
