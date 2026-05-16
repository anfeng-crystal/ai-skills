#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cosmic-post-check.py — 苍穹代码生成后统一检查入口

逻辑：
1. 从目标文件/目录向上查找 Gradle 项目根目录（同时存在 build.gradle + settings.gradle）
2. 若找到 → 执行 Gradle 编译 (./gradlew :module:compileJava)，利用真实编译器检查代码正确性
3. 若未找到 → 回退到 cosmic-post-lint.py 静态校验

用法:
    python3 cosmic-post-check.py <file_or_directory> [--fix-hint] [--json] [--strict]

示例:
    python3 cosmic-post-check.py /path/to/project/code/module-bos/src/main/java/Foo.java
    python3 cosmic-post-check.py ./src/main/java/ --fix-hint
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

SCRIPT_DIR = Path(__file__).resolve().parent

# 全局 verbose 标志，通过 --verbose 开启
VERBOSE = False


def _verbose(msg: str):
    """在 --verbose 模式下输出诊断信息到 stderr。"""
    if VERBOSE:
        print(f"  [verbose] {msg}", file=sys.stderr)


# ══════════════════════════════════════════════
#  Gradle 项目检测
# ══════════════════════════════════════════════

def find_gradle_root(target: str) -> Optional[Path]:
    """从目标路径向上查找 Gradle 项目根目录。

    判定条件：目录中同时存在 build.gradle(.kts) 和 settings.gradle(.kts)。
    """
    p = Path(target).resolve()
    if p.is_file():
        p = p.parent
    while p != p.parent:
        has_build = (p / "build.gradle").exists() or (p / "build.gradle.kts").exists()
        has_settings = (p / "settings.gradle").exists() or (p / "settings.gradle.kts").exists()
        if has_build and has_settings:
            return p
        p = p.parent
    return None


def parse_modules(gradle_root: Path) -> Dict[str, Path]:
    """解析 settings.gradle 获取 模块名 → 目录 映射。

    支持标准格式：
        include 'moduleName'
        project(':moduleName').projectDir = new File('relative/path')
    """
    modules: Dict[str, Path] = {}
    for name in ("settings.gradle", "settings.gradle.kts"):
        settings = gradle_root / name
        if settings.exists():
            break
    else:
        return modules

    text = settings.read_text(encoding="utf-8")

    # 收集所有 include 声明
    includes = re.findall(r"include\s+'([^']+)'", text)

    # 收集 projectDir 映射
    project_dirs: Dict[str, str] = dict(re.findall(
        r"project\(':([^']+)'\)\.projectDir\s*=\s*new\s+File\('([^']+)'\)",
        text,
    ))

    for mod_name in includes:
        if mod_name in project_dirs:
            modules[mod_name] = (gradle_root / project_dirs[mod_name]).resolve()
        else:
            modules[mod_name] = (gradle_root / mod_name).resolve()

    return modules


def find_module(gradle_root: Path, target: str,
                modules: Dict[str, Path]) -> Optional[str]:
    """确定目标文件/目录属于哪个 Gradle 子模块。"""
    target_path = Path(target).resolve()
    # 优先匹配最长路径（最具体的模块）
    best_match: Optional[str] = None
    best_len = 0
    for name, mod_dir in modules.items():
        try:
            target_path.relative_to(mod_dir)
            if len(str(mod_dir)) > best_len:
                best_len = len(str(mod_dir))
                best_match = name
        except ValueError:
            continue
    return best_match


# ══════════════════════════════════════════════
#  JDK 版本检测（仅读取 JAVA_HOME）
# ══════════════════════════════════════════════

def _read_properties(filepath: Path) -> Dict[str, str]:
    """读取 .properties 文件为 key→value 字典（支持 systemProp. 前缀）。"""
    props: Dict[str, str] = {}
    if not filepath.exists():
        return props
    for line in filepath.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        props[k.strip()] = v.strip()
    return props


def _detect_gradle_major(gradle_root: Path) -> Optional[int]:
    """从 gradle-wrapper.properties 提取 Gradle 主版本号。"""
    wrapper = gradle_root / "gradle" / "wrapper" / "gradle-wrapper.properties"
    if not wrapper.exists():
        return None
    text = wrapper.read_text(encoding="utf-8")
    m = re.search(r"gradle-(\d+)\.", text)
    return int(m.group(1)) if m else None


def _parse_jdk_major(version_str: str) -> Optional[int]:
    """将 JDK 版本字符串解析为主版本号。

    支持格式: "1.8" → 8, "17" → 17, "11.0.2" → 11, "21" → 21
    """
    if not version_str:
        return None
    version_str = version_str.strip()
    if version_str.startswith("1."):
        try:
            return int(version_str.split(".")[1])
        except (IndexError, ValueError):
            return None
    try:
        return int(version_str.split(".")[0])
    except ValueError:
        return None


def _get_java_home_version(java_home: str) -> Optional[int]:
    """读取 JAVA_HOME 指向的 JDK 主版本号。

    优先读取 $JAVA_HOME/release 文件中的 JAVA_VERSION，
    回退到执行 java -version 解析输出。
    """
    # 方式 1: release 文件（无需启动进程，最快）
    release_file = Path(java_home) / "release"
    if release_file.exists():
        try:
            text = release_file.read_text(encoding="utf-8")
            m = re.search(r'JAVA_VERSION="([^"]+)"', text)
            if m:
                return _parse_jdk_major(m.group(1))
        except Exception as e:
            _verbose(f"读取 release 文件失败: {e}")

    # 方式 2: java -version
    java_bin = os.path.join(java_home, "bin", "java.exe" if sys.platform == "win32" else "java")
    if os.path.isfile(java_bin):
        try:
            r = subprocess.run(
                [java_bin, "-version"],
                capture_output=True, text=True, timeout=10,
            )
            # java -version 输出到 stderr
            output = r.stderr or r.stdout or ""
            m = re.search(r'version "([^"]+)"', output)
            if m:
                return _parse_jdk_major(m.group(1))
        except Exception as e:
            _verbose(f"执行 java -version 失败: {e}")

    return None


def _get_required_jdk(gradle_root: Path) -> tuple:
    """计算 Gradle 项目所需的 JDK 版本范围。

    取 max(项目声明版本, Gradle 运行时最低要求) 作为下限。
    Returns: (min_jdk, max_jdk)
    """
    props = _read_properties(gradle_root / "gradle.properties")

    # Gradle 运行时 JDK 范围
    gradle_major = _detect_gradle_major(gradle_root)
    if gradle_major is not None and gradle_major >= 8:
        gradle_min, gradle_max = 17, 23   # Gradle 8.x: JDK 17–23
    elif gradle_major is not None and gradle_major >= 7:
        gradle_min, gradle_max = 11, 19   # Gradle 7.x: JDK 11–19
    else:
        gradle_min, gradle_max = 8, 16    # Gradle 6.x 及更早

    # 项目声明 JDK 版本
    project_jdk_str = (
        props.get("systemProp.jdk.version")
        or props.get("systemProp.jdk_version")
        or props.get("sourceCompatibility")
        or ""
    ).strip()
    project_jdk = _parse_jdk_major(project_jdk_str)

    min_jdk = max(project_jdk, gradle_min) if project_jdk else gradle_min
    return min_jdk, gradle_max


def check_java_home(gradle_root: Path) -> tuple:
    """检查 JAVA_HOME 是否满足项目要求。

    Returns:
        (ok, java_home, current_ver, required_ver)
        - ok: True=可以编译, False=需要回退
        - java_home: JAVA_HOME 路径（可能为 None）
        - current_ver: 当前 JAVA_HOME 的 JDK 主版本（可能为 None）
        - required_ver: 项目所需的 JDK 版本描述（如 "17–23"）
    """
    # 1. 项目 gradle.properties 中 org.gradle.java.home 优先
    props = _read_properties(gradle_root / "gradle.properties")
    explicit = props.get("org.gradle.java.home", "").strip()
    if explicit and os.path.isdir(explicit):
        java_home = explicit
    else:
        java_home = os.environ.get("JAVA_HOME", "").strip() or None

    min_jdk, max_jdk = _get_required_jdk(gradle_root)
    required_desc = f"{min_jdk}–{max_jdk}"
    _verbose(f"项目 JDK 要求: {required_desc}")

    if not java_home or not os.path.isdir(java_home):
        _verbose("JAVA_HOME 未设置或路径不存在")
        return False, None, None, required_desc

    current = _get_java_home_version(java_home)
    _verbose(f"JAVA_HOME={java_home}, 检测版本={current}")
    if current is None:
        _verbose("无法识别 JAVA_HOME 指向的 JDK 版本")
        return False, java_home, None, required_desc

    ok = min_jdk <= current <= max_jdk
    return ok, java_home, current, required_desc


# ══════════════════════════════════════════════
#  Gradle 编译
# ══════════════════════════════════════════════

def run_gradle(gradle_root: Path, module: Optional[str], java_home: str) -> int:
    """执行 Gradle 编译，返回退出码。"""
    # 定位 gradlew
    wrapper_name = "gradlew.bat" if sys.platform == "win32" else "gradlew"
    gradlew = gradle_root / wrapper_name
    if not gradlew.exists():
        print("⚠️  gradlew 不存在，尝试使用系统 gradle", file=sys.stderr)
        cmd_prefix = ["gradle"]
    else:
        # 确保 gradlew 有可执行权限
        if not os.access(gradlew, os.X_OK):
            os.chmod(gradlew, 0o755)
        cmd_prefix = [str(gradlew)]

    task = f":{module}:compileJava" if module else "compileJava"
    cmd = cmd_prefix + [task, "--console=plain"]

    env = os.environ.copy()
    env["JAVA_HOME"] = java_home

    # 读取项目 JDK 版本用于显示
    props = _read_properties(gradle_root / "gradle.properties")
    project_jdk_str = (
        props.get("systemProp.jdk.version")
        or props.get("systemProp.jdk_version")
        or ""
    ).strip()

    print("══════════════════════════════════════════════")
    print("  🔨 Gradle 编译检查")
    print("══════════════════════════════════════════════")
    print(f"  📁 项目根目录: {gradle_root}")
    if module:
        print(f"  📦 目标模块:   {module}")
    if project_jdk_str:
        print(f"  📋 项目 JDK:   {project_jdk_str} (gradle.properties)")
    print(f"  ☕ JAVA_HOME:  {java_home}")
    print(f"  🛠️  编译命令:   {' '.join(cmd)}")
    print("──────────────────────────────────────────────")
    print(flush=True)

    result = subprocess.run(cmd, cwd=str(gradle_root), env=env)

    print()
    print("══════════════════════════════════════════════")
    if result.returncode == 0:
        print("  ✅ Gradle 编译成功，未发现编译错误。")
    else:
        print(f"  ❌ Gradle 编译失败 (exit code {result.returncode})")
        print("  请根据上述编译错误信息修复代码。")
    print("══════════════════════════════════════════════")

    return result.returncode


# ══════════════════════════════════════════════
#  Post-Lint 回退
# ══════════════════════════════════════════════

def run_post_lint(args: list, jdk_hint: Optional[str] = None) -> int:
    """回退到 cosmic-post-lint.py 静态校验。"""
    post_lint = SCRIPT_DIR / "cosmic-post-lint.py"
    if not post_lint.exists():
        print(f"❌ 未找到 {post_lint}", file=sys.stderr)
        return 1

    print("📝 使用 post-lint 静态 + 知识库校验")
    print(flush=True)

    cmd = [sys.executable, str(post_lint)] + args
    result = subprocess.run(cmd)

    # 在结果之后输出 JAVA_HOME 设置提示
    if jdk_hint:
        print()
        print(jdk_hint)

    return result.returncode


# ══════════════════════════════════════════════
#  主入口
# ══════════════════════════════════════════════

def main():
    global VERBOSE

    if len(sys.argv) < 2:
        print("用法: cosmic-post-check.py <file_or_directory> [--fix-hint] [--json] [--strict] [--verbose]")
        print()
        print("优先使用 Gradle 编译检查；若非 Gradle 项目或 JAVA_HOME 不兼容则回退到 post-lint 静态校验。")
        sys.exit(1)

    # 解析 --verbose 并从 argv 中移除（不传给 post-lint）
    if "--verbose" in sys.argv:
        VERBOSE = True
        sys.argv.remove("--verbose")

    target = sys.argv[1]
    remaining_args = sys.argv[1:]

    # 1. 检测 Gradle 项目
    gradle_root = find_gradle_root(target)
    _verbose(f"Gradle 项目检测: {gradle_root or '未找到'}")

    if not gradle_root:
        # 非 Gradle → 直接 post-lint
        sys.exit(run_post_lint(remaining_args))

    # 2. 检查 JAVA_HOME
    ok, java_home, current_ver, required_ver = check_java_home(gradle_root)

    if ok and java_home:
        # JAVA_HOME 兼容 → Gradle 编译
        modules = parse_modules(gradle_root)
        module = find_module(gradle_root, target, modules)
        sys.exit(run_gradle(gradle_root, module, java_home))

    # 3. JAVA_HOME 不兼容 → 回退 post-lint，并生成提示信息
    hint_lines = ["══════════════════════════════════════════════"]
    hint_lines.append("  💡 Gradle 编译检查已跳过（JAVA_HOME 版本不兼容）")
    hint_lines.append("──────────────────────────────────────────────")
    if java_home and current_ver:
        hint_lines.append(f"  当前 JAVA_HOME: {java_home}")
        hint_lines.append(f"  当前 JDK 版本:  {current_ver}")
    elif java_home:
        hint_lines.append(f"  当前 JAVA_HOME: {java_home} (无法识别版本)")
    else:
        hint_lines.append("  当前 JAVA_HOME: 未设置")
    hint_lines.append(f"  项目需要 JDK:   {required_ver}")
    hint_lines.append("")
    # 从范围描述中取下限用于示例路径
    min_ver = required_ver.split("–")[0] if "–" in required_ver else required_ver
    hint_lines.append(f"  请设置 JAVA_HOME 环境变量指向 JDK {min_ver} 以启用 Gradle 编译检查:")
    if sys.platform == "win32":
        hint_lines.append(f'    set JAVA_HOME=C:\\Program Files\\Java\\jdk-{min_ver}')
    else:
        hint_lines.append(f"    export JAVA_HOME=/path/to/jdk-{min_ver}")
    hint_lines.append("══════════════════════════════════════════════")

    jdk_hint = "\n".join(hint_lines)
    print(f"⚠️  检测到 Gradle 项目 ({gradle_root.name})，但 JAVA_HOME 不满足要求，回退到静态校验")
    print(flush=True)

    sys.exit(run_post_lint(remaining_args, jdk_hint=jdk_hint))


if __name__ == "__main__":
    main()
