# Windows Generic Worker setup

1. Install BHoM v9.2 beta with the LifeCycleAssessment datasets.
2. Run `scripts\build-gateway.ps1`.
3. Run `worker\install-gateway.ps1` as Administrator. Confirm that the gateway is installed at `C:\Services\BHoMMaterialLookupGateway\BHoMMaterialLookupGateway.exe`.
4. Open the installed Generic Worker `config.yaml`. Production configuration is normally beside the installed worker under `C:\Program Files\Viktor\...\config.yaml`; development configuration is under the user-local VIKTOR installation.
5. Merge `executables.bhom_material_lookup` from `worker\config.example.yaml` into the existing `executables` mapping in `config.yaml`. Preserve all other executable entries and verify that the gateway path matches the installed path above.
6. Save `config.yaml`.
7. Restart the Generic Worker because it loads configuration at startup.
8. Run `worker\diagnose.ps1`, then `worker\run-local.ps1`.

The executable key used by the VIKTOR app is `bhom_material_lookup`. The gateway reads typed EPDs through BHoM `Library_Engine` from `C:\ProgramData\BHoM\Datasets\LifeCycleAssessment`; no external API token is required.
