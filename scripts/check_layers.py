"""
계층 참조 방향을 검사한다 — 아래 계층이 위 계층을 import 하면 위반이다.

    python -m scripts.check_layers

`app/model`·`enums`·`constants`·`exception` 은 층이 아니라 모든 층이 쓰는 어휘라 제외한다
(docs/abstraction-layers.md 3절). 검사한 파일 수와 규칙 수를 함께 찍어
"통과"와 "아무것도 안 봄"을 구분한다.
"""
from __future__ import annotations

import ast
import pathlib
import sys

SHARED: tuple[str, ...] = ("app.model", "app.enums", "app.constants", "app.exception", "app.source")
"""층이 아닌 공용 어휘. 어느 층에서 import 해도 위반이 아니다.
app.source 는 서비스와 구현이 함께 보는 약속(Protocol)이라 여기 둔다"""

LEVEL: dict[str, int] = {
    "web": 1,
    "app/service": 2,
    "infra": 3,
    "app/dto": 3,
    "app/dao": 5,
    "app/external": 6,
}
"""낮은 수가 높은 층. infra 는 app/source 약속의 구현이라 service 보다 아래다"""

SKIP_DIRS: tuple[str, ...] = ("venv", ".venv", "test", "scripts", "__pycache__", "bootstrap")
"""bootstrap 은 조립 도면이라 모든 층을 알아도 된다"""


def layer_of(path: str) -> str | None:
    normalized: str = path.replace(".", "/")
    for name in sorted(LEVEL, key=len, reverse=True):
        if normalized.startswith(name):
            return name
    return None


def main() -> int:
    violations: list[str] = []
    checked: int = 0

    for file in pathlib.Path(".").rglob("*.py"):
        if any(part in SKIP_DIRS for part in file.parts):
            continue
        source_layer: str | None = layer_of(str(file))
        if source_layer is None:
            continue

        checked += 1
        tree: ast.Module = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            if node.module.startswith(SHARED):
                continue
            target_layer: str | None = layer_of(node.module)
            if target_layer is None or target_layer == source_layer:
                continue
            if LEVEL[target_layer] < LEVEL[source_layer]:
                violations.append(f"{file}: {source_layer} -> {node.module}")

    print(f"검사 파일 {checked}개, 규칙 {len(LEVEL)}개 -> 역방향 위반 {len(violations)}건")
    for violation in violations:
        print("  ", violation)
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
