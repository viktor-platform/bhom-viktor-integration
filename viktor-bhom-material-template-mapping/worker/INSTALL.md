# Windows Generic Worker setup

1. Install BHoM v9.2 beta with the LifeCycleAssessment datasets.
2. Run `scripts\build-gateway.ps1`.
3. Run `worker\install-gateway.ps1` as Administrator.
4. Merge `worker\config.example.yaml` into the VIKTOR Generic Worker configuration.
5. Restart the Generic Worker.
6. Run `worker\diagnose.ps1`, then `worker\run-local.ps1`.

The executable key used by the VIKTOR app is `bhom_material_lookup`. The gateway reads typed EPDs through BHoM `Library_Engine` from `C:\ProgramData\BHoM\Datasets\LifeCycleAssessment`; no external API token is required.
