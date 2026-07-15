# Source revisions inspected

Research snapshot recorded on 2026-07-14:

| Repository | Branch | Commit |
|---|---|---|
| `BHoM/Revit_Toolkit` | `develop` | `9d54d199f6c1845d9ba1e599a02052521db1047c` |
| `BHoM/LifeCycleAssessment_Toolkit` | `develop` | `b22711976e22522e06cfae45c2824ec16cce78a0` |
| `BHoM/BHoM_JSONSchema` | `develop` | `9a3bde86d287cb9e07f40b5538a059cc546c59dc` |

These commits support the sample's contract research; they are not a Windows
runtime compatibility claim. Before building the live Revit gateway, select one
BHoM v9 installer/runtime set, check out toolkit commits compatible with that
runtime, and replace this research snapshot with the tested release lock.

The bundled `GeneralMaterialTakeoff` and two `Material` objects were validated
against the JSON Schema commit above. Some unrelated generated schemas in that
commit omit a `$schema` declaration, so validation used Draft 2020-12 as the
explicit default specification while registering local `$id` references.
