# BHoM LCA Gateway installation

This package is for the administrator of the Windows VIKTOR Generic Worker.
Users of the VIKTOR web application do not install it.

## Requirements

- Windows x64
- .NET 8 Desktop Runtime
- VIKTOR Generic Worker
- Administrator access for installation

## Install

1. Extract the complete ZIP. Do not copy only the executable.
2. Open PowerShell as Administrator in the extracted directory.
3. Run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install.ps1
   ```

4. Merge `config.example.yaml` into the Generic Worker configuration.
5. Restart the Generic Worker service.
6. Verify the installed gateway:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\diagnose.ps1
   ```

The installer copies the gateway bundle to `C:\Services\BHoMLcaGateway`.
