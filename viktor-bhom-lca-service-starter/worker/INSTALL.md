# BHoM LCA Gateway installation

This package is for the administrator of the Windows VIKTOR Generic Worker.
Users of the VIKTOR web application do not install it.

## Requirements

- Windows x64
- .NET 8 Desktop Runtime
- BHoM v9.2.beta.0
- VIKTOR Generic Worker
- Administrator access for installation

## Install

1. Extract the complete ZIP. Do not copy only the executable.
2. Open PowerShell in the extracted directory.
3. Install the pinned BHoM distribution when it is not already installed:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install-bhom.ps1 -Install
   ```

4. Open PowerShell as Administrator and run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install.ps1
   ```

5. Merge `config.example.yaml` into the Generic Worker configuration.
6. Restart the Generic Worker service.
7. Verify the installed gateway:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\diagnose.ps1
   ```

The installer copies the gateway bundle to `C:\Services\BHoMLcaGateway`.
