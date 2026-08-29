# ROHI Google one-time setup

The editable Spreadsheet IDs have now been configured in `google_drive_upload.gs`.

## Configured Spreadsheet IDs

- ROHI Attendance Report: `1viiRhothIiDJpx_HmFTc9JIKUbOXgyUb`
- ROHI Staff Registration Details: `1w6wj-e_qTglWP8uE0LP6k1zLPrUAZLbP`

The Timesheet and Leave Drive folder IDs are already configured.

## Still required in your Google account

You must deploy `google_drive_upload.gs` as a Google Apps Script Web App:

1. Open Google Apps Script.
2. Create a project.
3. Paste the complete contents of `google_drive_upload.gs`.
4. Save.
5. Deploy -> New deployment.
6. Select **Web app**.
7. Execute as: **Me**.
8. Who has access: **Anyone with the link**.
9. Deploy and authorize the requested permissions.
10. Copy the URL ending in `/exec`.

Put that `/exec` URL into the APK's Google/Server Connection endpoint settings for:

- Attendance
- Staff Registration
- Timesheet
- Leave Management

The same Web App `/exec` URL can be used for all four.

## Important

The spreadsheet IDs above are the normal editable IDs obtained from your `/edit` links. Do not replace them with the `/pubhtml` publication IDs.

After deployment, the app can:

- submit Check-In and Check-Out records to the Attendance spreadsheet
- submit Staff Registration immediately after Submit
- upload Timesheet XLSX files to the configured Timesheet Drive folder
- upload Leave Management XLSX files to the configured Leave Drive folder
- use the Email actions for generated reports

## Deployment URL configured in this build

All four ROHI upload endpoints are preconfigured to the deployed Apps Script Web App URL. The app no longer requires manual entry of the endpoint on first launch.

Web App URL: https://script.google.com/macros/s/AKfycbwLdMEyiB7nuAT_BHPP5W-eo1VJMgOz_UrpgFjiz5Fo3HDRo8C1KRFrgCmRCkzJNJb6/exec


## Safe State Office folder setup

Before the first production upload, open `google_drive_upload.gs` in Apps Script and run `setupStateOfficeFolders()` once. Authorize Drive access when prompted. The function is **safe and non-destructive**: it creates only missing ROHI State Office folders for Borno, Adamawa, Yobe, Taraba and Benue. Running it again will NOT delete, trash, or clear any existing folder or report. Existing folders and their reports are preserved.

After it finishes, use the generated folder IDs in `CONFIG.stateOfficeRoots` if the script created new root folders.
