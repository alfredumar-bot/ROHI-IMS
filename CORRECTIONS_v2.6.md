# ROHI corrections v2.6

- Login is scheduled immediately after the first frame. Background service startup, server checks, and report-link checks wait until the login interface is visible.
- Dashboard DHIS2 and Power BI use the supplied logos and match the Gmail icon size.
- Daily Weekly Performance Tracker and Monthly Report use the supplied Microsoft Word templates. Their uploads preserve the `.docx` format in Google Drive.
- CFM navigation checks that its layout is available before entering the screen and presents a clear error instead of an unexplained white screen if a packaging/layout issue occurs.
- Timesheets now show only the exact selected calendar month. For example, September contains 1-30 September, with no August dates. Template rows beyond the selected month are cleared before export.
- Timesheet has its own section and officer routing controls. These controls do not change Staff Registration. The sender must choose an officer before the timesheet is queued for approval.
- `TIMESHEET_APPROVAL_PROTOCOL.md` defines the API/queue contract for the planned Windows approval application.
