import ast
import tomllib
from pathlib import Path

APP_ROOT = Path(__file__).parents[1]


def takeoff_file_call() -> ast.Call:
    source = (APP_ROOT / "app" / "parametrization.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "takeoff_file"
                for target in node.targets
            )
            and isinstance(node.value, ast.Call)
        ):
            return node.value

    raise AssertionError("takeoff_file FileField assignment not found")


def download_button_assignments() -> list[tuple[str, ast.Call]]:
    source = (APP_ROOT / "app" / "parametrization.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assignments = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and node.value.func.attr == "DownloadButton"
        ):
            assignments.append((node.targets[0].id, node.value))
    return assignments


def test_app_is_configured_as_simple():
    with (APP_ROOT / "viktor.config.toml").open("rb") as config_file:
        config = tomllib.load(config_file)

    assert config["app_type"] == "simple"


def test_only_visible_download_control_is_excel_export():
    buttons = download_button_assignments()

    assert len(buttons) == 1
    name, call = buttons[0]
    keywords = {
        keyword.arg: ast.literal_eval(keyword.value)
        for keyword in call.keywords
        if keyword.arg is not None
    }
    assert name == "download_excel"
    assert ast.literal_eval(call.args[0]) == "Export Excel"
    assert keywords == {"method": "download_excel"}
    assert {
        "download_template",
        "download_takeoff",
        "download_handoff",
    }.isdisjoint(name for name, _ in buttons)


def test_takeoff_file_clearly_describes_optional_table_fallback():
    call = takeoff_file_call()
    keywords = {
        keyword.arg: ast.literal_eval(keyword.value)
        for keyword in call.keywords
        if keyword.arg is not None
    }

    assert ast.literal_eval(call.args[0]) == "BHoM takeoff (Optional)"
    description = keywords["description"]
    assert description.startswith("Optional:")
    assert "GeneralMaterialTakeoff exported by the Revit app" in description
    assert "leave it empty" in description
    assert "material table" in description
