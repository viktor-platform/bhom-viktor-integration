import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Self

import pytest

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))


if "viktor" not in sys.modules:

    class _SdkFile:
        _data: bytes

        @classmethod
        def from_data(cls, data: bytes) -> Self:
            instance = cls()
            instance._data = data
            return instance

        def getvalue_binary(self) -> bytes:
            return self._data

    class _ViktorModule(ModuleType):
        File: type[_SdkFile]
        Storage: Any

    viktor = _ViktorModule("viktor")
    viktor.File = _SdkFile
    viktor.Storage = lambda: (_ for _ in ()).throw(
        AssertionError("VIKTOR Storage must be faked or patched in unit tests.")
    )
    sys.modules["viktor"] = viktor


class FakeStoredFile:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def getvalue_binary(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


class FakeStorage:
    def __init__(self, values: dict[str, Any] | None = None) -> None:
        self.values = dict(values or {})
        self.calls: list[tuple[str, str]] = []

    def get(self, key: str, *, scope: str) -> FakeStoredFile:
        self.calls.append(("get", key))
        assert scope == "entity"
        if key not in self.values:
            raise FileNotFoundError(key)
        return FakeStoredFile(self.values[key])

    def set(self, key: str, *, data: Any, scope: str) -> None:
        self.calls.append(("set", key))
        assert scope == "entity"
        self.values[key] = json.loads(data.getvalue_binary().decode("utf-8"))


@pytest.fixture
def sample_takeoff() -> dict[str, Any]:
    return {
        "_t": "BH.oM.Physical.Materials.GeneralMaterialTakeoff",
        "MaterialTakeoffItems": [
            {
                "Material": {
                    "_t": "BH.oM.Physical.Materials.Material",
                    "Name": "Concrete C30/37",
                    "Density": 2400.0,
                },
                "Volume": 12.5,
                "Mass": 30000.0,
            }
        ],
    }


@pytest.fixture
def sample_templates() -> list[dict[str, Any]]:
    return [
        {
            "_t": "BH.oM.Physical.Materials.Material",
            "Name": "Concrete C30/37",
            "Density": 2400.0,
            "Properties": [
                {"_t": "BH.oM.LifeCycleAssessment.EnvironmentalProductDeclaration"}
            ],
        }
    ]
