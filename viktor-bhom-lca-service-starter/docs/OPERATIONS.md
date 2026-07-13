# Worker operations

## Installed components

```text
C:\Services\BHoMLcaGateway\
├── BHoMLcaGateway.exe
├── BHoMLcaGateway.dll
├── BHoMLcaGateway.runtimeconfig.json
├── BHoM and toolkit assemblies
├── DataSets\
└── external-revisions.json
```

The VIKTOR Generic Worker runs `BHoMLcaGateway.exe` through the `bhom_lca` executable key. Job files are placed in a temporary working directory. Do not configure one shared fixed working directory when parallel execution is enabled.

## Installation

1. Build the gateway on a Windows development machine.
2. Copy the publish output to the worker machine.
3. Run `worker\install-gateway.ps1` as Administrator.
4. Merge `worker\config.example.yaml` into the Generic Worker configuration.
5. Restart the Generic Worker service.
6. Run `worker\diagnose.ps1`.
7. Run a VIKTOR sample job.

## Upgrade

1. Record the previous publish directory and runtime manifest.
2. Stop the Generic Worker service.
3. Install the new signed or approved package.
4. Update the worker configuration only when the path or arguments changed.
5. Start the worker service.
6. Run diagnostics and the fixed sample.
7. Change `CACHE_VERSION` in `lca_service/worker_client.py` when calculation code, BHoM assemblies or service contracts change.

## Rollback

`install-gateway.ps1` moves the existing target to a timestamped backup directory. Stop the worker, replace the target directory with the selected backup, and start the worker again. Run the fixed sample before reopening the service to users.

## Concurrency

Start with `maxParallelProcesses: 2` only after confirming memory and CPU use on the worker. Every job must use its VIKTOR-created temporary directory. Reduce the value to one if any BHoM library or dataset access proves unsafe under concurrent execution.

## Logs and artifacts

For every successful calculation, retain:

- normalized result;
- raw BHoM results;
- gateway events;
- runtime manifest;
- service request;
- source takeoff and material-template hashes.

The starter returns the first four artifacts to VIKTOR. Add long-term persistence according to the deployment retention policy.

## Exit codes

| Code | Meaning |
|---:|---|
| 0 | Success |
| 2 | Invalid command-line arguments |
| 3 | Invalid request or input data |
| 4 | Calculation or runtime failure |

## Security

- The worker configuration permits only the fixed `bhom_lca` executable.
- The gateway accepts file names only within the current job directory.
- VIKTOR jobs cannot choose a DLL or arbitrary executable.
- Do not copy secrets into job files.
- Verify package origin and hashes before deployment.
- Keep the worker host patched and restrict interactive logon.

## Data quality

The supplied EPD factors are synthetic test data. A production deployment must use approved material templates and retain their source, declared unit, publication date, validity date and verification information.
