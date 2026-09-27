from pathlib import Path

from jarvis.code_intelligence import architecture_context, build_repository_map, select_relevant


def test_python_symbols_imports_and_tests_are_mapped(tmp_path: Path):
    (tmp_path/"service.py").write_text("import json\nclass Engine:\n    def run(self): pass\n",encoding="utf-8")
    (tmp_path/"test_service.py").write_text("from service import Engine\ndef test_run(): pass\n",encoding="utf-8")
    items=build_repository_map(tmp_path,["service.py","test_service.py"])
    service=next(x for x in items if x.path=="service.py")
    test=next(x for x in items if x.path=="test_service.py")
    assert {"Engine","run"} <= set(service.symbols)
    assert "json" in service.imports
    assert test.tests is True


def test_objective_selects_semantically_related_file(tmp_path: Path):
    (tmp_path/"billing.py").write_text("def calculate_invoice_total(): return 1\n",encoding="utf-8")
    (tmp_path/"weather.py").write_text("def forecast(): return 2\n",encoding="utf-8")
    items=build_repository_map(tmp_path,["billing.py","weather.py"])
    selected=select_relevant(tmp_path,items,"fix invoice total calculation")
    assert selected[0].path=="billing.py"


def test_architecture_context_contains_map_and_focused_source(tmp_path: Path):
    (tmp_path/"auth.py").write_text("class TokenVerifier:\n    pass\n",encoding="utf-8")
    context=architecture_context(tmp_path,["auth.py"],"change TokenVerifier")
    assert "AEGIS REPOSITORY INTELLIGENCE" in context
    assert "TokenVerifier" in context
    assert "--- auth.py ---" in context
