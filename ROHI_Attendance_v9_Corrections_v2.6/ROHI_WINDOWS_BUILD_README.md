# ROHI IMS — Windows PC Build

This package is the Windows PC build version of the ROHI IMS project.
It keeps the current Android codebase and includes the CFM fix, Timesheet Backstop/Line Manager routing, and Leave Management template/report work.

## Build on Windows

1. Install **Python 3.11** (recommended) or Python 3.12 from python.org.
2. During installation, enable **Add Python to PATH**.
3. Extract this ZIP to a normal folder, for example:
   `C:\ROHI_IMS`
4. Double-click `build_windows.bat`.
5. Wait for the build to finish.
6. The Windows application will be created at:
   `dist\ROHI_IMS\ROHI_IMS.exe`

**Important:** Keep the complete `dist\ROHI_IMS` folder together. Do not copy only the EXE.

## Test without building an EXE

Run `build_windows.bat` once to create the virtual environment and install dependencies, then use `run_windows.bat`.

## Notes

- Android-only code is guarded by the existing platform checks in `main.py`.
- GPS/camera features that require Android hardware are not expected to provide the same functionality on Windows.
- Local SQLite, Excel/PDF report generation, Leave Management, Timesheet, CFM, and PostgreSQL/pg8000 functionality are included for PC use.
- For PostgreSQL, configure the server connection inside the application as required by your ROHI server.
