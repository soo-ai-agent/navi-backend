from __future__ import annotations

import ast
from graphlib import TopologicalSorter
from pathlib import Path
from unittest import TestCase


class TestVoDependencies(TestCase):
    def test_VO는_상위계층을_참조하지_않는다(self) -> None:
        root: Path = Path(__file__).resolve().parents[2] / "app/model/vo"
        paths: tuple[Path, ...] = tuple(root.glob("*.py"))
        self.assertTrue(paths)
        for path in paths:
            tree: ast.Module = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    imports: tuple[str, ...] = (node.module,)
                elif isinstance(node, ast.Import):
                    imports = tuple(alias.name for alias in node.names)
                else:
                    continue
                for module in imports:
                    with self.subTest(file=path.name, dependency=module):
                        self.assertFalse(module.startswith(("app.service.", "app.dao.", "app.dto.", "web.", "bootstrap.")))

    def test_VO_모듈끼리_순환_참조하지_않는다(self) -> None:
        root: Path = Path(__file__).resolve().parents[2] / "app/model/vo"
        # 파일명은 동적인 그래프 정점이므로 표준 위상 정렬의 입력 형식인 dict로 구성한다.
        dependencies: dict[str, set[str]] = {}
        for path in root.glob("*.py"):
            module: str = f"app.model.vo.{path.stem}"
            dependencies[module] = set()
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.startswith("app.model.vo."):
                        dependencies[module].add(node.module)

        ordered: tuple[str, ...] = tuple(TopologicalSorter(dependencies).static_order())

        self.assertEqual(len(dependencies), len(ordered))

    def test_VO_파일_하나에_클래스_하나만_둔다(self) -> None:
        root: Path = Path(__file__).resolve().parents[2] / "app/model/vo"
        for path in root.glob("*.py"):
            classes: tuple[ast.ClassDef, ...] = tuple(
                node for node in ast.parse(path.read_text()).body if isinstance(node, ast.ClassDef)
            )
            with self.subTest(file=path.name):
                self.assertLessEqual(len(classes), 1)
