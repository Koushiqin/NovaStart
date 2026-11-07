"""架构边界棘轮检查：冻结 backend/app 的分层依赖方向与时间入口。

规则（对应 docs/architecture.md）：
1. models/  不得 import services / routers
2. services/ 不得 import routers
3. routers/ 之间不得互相 import
4. datetime.now( 只允许出现在 clock.py（后端时间唯一真相源）

纯源码 AST 扫描，不导入 app、不连数据库，任何环境可跑。
清理历史问题后只能收紧，不得通过删断言 / 加白名单掩盖违规。
"""

import ast
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def _py_files(layer: str) -> list[Path]:
    return sorted((APP_DIR / layer).rglob("*.py"))


def _imported_app_modules(path: Path) -> set[str]:
    """返回文件中 import 的 app.* 顶层子模块名集合，如 {'services', 'routers'}。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        for name in names:
            parts = name.split(".")
            if len(parts) >= 2 and parts[0] == "app":
                modules.add(parts[1])
    return modules


def _datetime_now_calls(path: Path) -> list[int]:
    """返回调用 datetime.now(...) 的行号列表。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    lines: list[int] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "now"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "datetime"
        ):
            lines.append(node.lineno)
    return lines


@pytest.mark.parametrize("path", _py_files("models"), ids=lambda p: p.name)
def test_models_do_not_import_upper_layers(path: Path) -> None:
    imported = _imported_app_modules(path)
    assert not (imported & {"services", "routers"}), (
        f"{path.name} 违规引用上层模块: {imported & {'services', 'routers'}}"
    )


@pytest.mark.parametrize("path", _py_files("services"), ids=lambda p: p.name)
def test_services_do_not_import_routers(path: Path) -> None:
    imported = _imported_app_modules(path)
    assert "routers" not in imported, f"{path.name} 违规引用 routers"


@pytest.mark.parametrize("path", _py_files("routers"), ids=lambda p: p.name)
def test_routers_do_not_import_each_other(path: Path) -> None:
    imported = _imported_app_modules(path)
    assert "routers" not in imported, f"{path.name} 违规引用其他 router"


@pytest.mark.parametrize(
    "path",
    [p for p in APP_DIR.rglob("*.py") if p.name != "clock.py"],
    ids=lambda p: str(p.relative_to(APP_DIR)),
)
def test_datetime_now_only_in_clock(path: Path) -> None:
    lines = _datetime_now_calls(path)
    assert not lines, (
        f"{path.relative_to(APP_DIR)} 第 {lines} 行直接调用 datetime.now()，"
        "时间判定必须走 app/clock.py 的 Clock"
    )
