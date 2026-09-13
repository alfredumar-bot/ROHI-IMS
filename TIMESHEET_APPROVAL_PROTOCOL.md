# Timesheet approval protocol

The Android app creates a timesheet for the selected calendar month, attaches the employee signature, and records an approval-routing item with these fields:

- `schema_version`
- `status` (`awaiting_officer_signature`, `approved`, or `rejected`)
- `created_at`
- `employee_name` and `employee_email`
- `section`
- `assigned_officer`
- `timesheet_file`

The future Windows application should read the same record from the shared service/API, show it as an officer notification, and allow only the assigned officer to attach a signature. Once approved, the Windows application uploads the signed `.xlsx` document to the configured Google Drive folder and changes the status to `approved`.

For production, move the queue from the APK-local `timesheet_approval_queue.json` file to an authenticated API. The API should enforce assignment, keep an audit trail, store signature metadata, and return push-notification status to both applications.
