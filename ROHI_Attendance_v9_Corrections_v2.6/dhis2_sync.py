"""
ROHI - DHIS2 Integration
-------------------------
Pushes ROHI attendance data into a DHIS2 instance (tested against the
public DHIS2 demo server, e.g. https://play.dhis2.org/<version>).

Two independent payload types are supported, matching how DHIS2 itself
separates individual-level data from aggregate data:

1. Tracker event  -> POST {server}/api/tracker
   One event per staff check-in/out day, attached to a Tracked Entity
   Instance (the staff member) inside a Tracker Program.

2. Aggregate data values -> POST {server}/api/dataValueSets
   Present/Absent totals for a period, attached to a Data Set + Org Unit.

Both calls use HTTP Basic Auth (username/password) since that is what
the DHIS2 demo instance supports out of the box. A Personal Access
Token can be substituted by passing it as the password with username
left as the literal string "ACCESS_TOKEN" is NOT how DHIS2 PATs work -
PATs are sent as an "ApiToken" Authorization header - so a
`token` argument is accepted separately below and takes priority over
basic auth when provided.

All functions return (ok: bool, message: str) so the caller can show a
one-line status the same way the existing Excel/Google sync does.
"""
import json
import base64
import ssl
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


def _rohi_ssl_context():
    """Same certifi-backed context as main.py - Pydroid 3 doesn't wire the
    OS certificate store into Python's ssl module, so a plain urlopen() to
    an https:// DHIS2 server fails with CERTIFICATE_VERIFY_FAILED without
    this, even when the server's certificate is perfectly valid."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        try:
            return ssl.create_default_context()
        except Exception:
            return None


_SSL_CONTEXT = _rohi_ssl_context()


def _auth_headers(username, password, token=None):
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"ApiToken {token}"
    else:
        raw = f"{username}:{password}".encode("utf-8")
        headers["Authorization"] = "Basic " + base64.b64encode(raw).decode("ascii")
    return headers


def _post_json(url, payload, username, password, token=None, timeout=30):
    try:
        data = json.dumps(payload).encode("utf-8")
        req = Request(url, data=data, headers=_auth_headers(username, password, token), method="POST")
        with urlopen(req, timeout=timeout, context=_SSL_CONTEXT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = str(e)
        return False, f"DHIS2 rejected the request (HTTP {e.code}): {body[:300]}"
    except URLError as e:
        return False, f"Could not reach DHIS2 server: {e.reason}"
    except Exception as e:
        return False, f"DHIS2 sync error: {e}"

    try:
        parsed = json.loads(body) if body else {}
    except Exception:
        parsed = {}

    if status not in (200, 201, 200):
        return False, f"DHIS2 returned HTTP {status}: {body[:300]}"

    # DHIS2 /api/tracker returns status: OK/ERROR/WARNING in the JSON body
    # even on HTTP 200, so check that explicitly.
    dhis_status = str(parsed.get("status") or "").upper()
    if dhis_status == "ERROR":
        return False, f"DHIS2 import errors: {json.dumps(parsed.get('validationReport', parsed))[:300]}"

    return True, "Synced to DHIS2."


def push_attendance_event(
    server_url, username, password,
    program, program_stage, org_unit, tracked_entity, tracked_entity_type,
    event_date, data_values, token=None, event_status="COMPLETED",
):
    """Push one individual attendance record as a DHIS2 Tracker event.

    ``tracked_entity`` is the DHIS2 Tracked Entity Instance UID for this
    staff member (create once at registration time, then reuse for every
    attendance day). ``data_values`` is a dict of {dataElement UID: value}
    for whatever fields the ROHI attendance program stage defines
    (e.g. check-in time, check-out time, late flag, GPS status).
    """
    server_url = server_url.rstrip("/")
    payload = {
        "events": [{
            "program": program,
            "programStage": program_stage,
            "orgUnit": org_unit,
            "trackedEntity": tracked_entity,
            "occurredAt": event_date,
            "status": event_status,
            "dataValues": [
                {"dataElement": de, "value": str(val)}
                for de, val in (data_values or {}).items() if val not in (None, "")
            ],
        }]
    }
    return _post_json(f"{server_url}/api/tracker?async=false", payload, username, password, token)


def ensure_tracked_entity(
    server_url, username, password,
    org_unit, tracked_entity_type, attributes, token=None,
):
    """Create a Tracked Entity Instance for a staff member if one doesn't
    already exist, returning (ok, tei_uid_or_message).

    ``attributes`` is a dict of {trackedEntityAttribute UID: value}
    (e.g. staff ID, full name). DHIS2 will assign a new TEI UID on
    success; the caller should store it against the staff record so
    future attendance events reuse the same TEI instead of duplicating
    people in DHIS2.
    """
    server_url = server_url.rstrip("/")
    payload = {
        "trackedEntities": [{
            "orgUnit": org_unit,
            "trackedEntityType": tracked_entity_type,
            "attributes": [
                {"attribute": attr, "value": str(val)}
                for attr, val in (attributes or {}).items() if val not in (None, "")
            ],
        }]
    }
    ok, message = _post_json(f"{server_url}/api/tracker?async=false", payload, username, password, token)
    if not ok:
        return False, message
    return True, message


def push_aggregate_summary(
    server_url, username, password,
    org_unit, period, data_set,
    present_data_element, absent_data_element,
    present_count, absent_count,
    late_data_element=None, late_count=None,
    token=None, category_option_combo="default",
):
    """Push present/absent (and optionally late) totals as DHIS2 aggregate
    data values for one reporting period.

    ``period`` must be in DHIS2 period format for the data set's period
    type, e.g. "202608" for a monthly data set, "20260821" for daily.
    """
    server_url = server_url.rstrip("/")
    data_values = [
        {
            "dataElement": present_data_element,
            "period": period,
            "orgUnit": org_unit,
            "categoryOptionCombo": category_option_combo,
            "value": str(present_count),
        },
        {
            "dataElement": absent_data_element,
            "period": period,
            "orgUnit": org_unit,
            "categoryOptionCombo": category_option_combo,
            "value": str(absent_count),
        },
    ]
    if late_data_element and late_count is not None:
        data_values.append({
            "dataElement": late_data_element,
            "period": period,
            "orgUnit": org_unit,
            "categoryOptionCombo": category_option_combo,
            "value": str(late_count),
        })

    payload = {"dataSet": data_set, "completeDate": None, "period": period,
               "orgUnit": org_unit, "dataValues": data_values}
    return _post_json(f"{server_url}/api/dataValueSets", payload, username, password, token)


def test_connection(server_url, username, password, token=None):
    """Quick reachability/auth check against /api/me."""
    server_url = server_url.rstrip("/")
    try:
        req = Request(f"{server_url}/api/me", headers=_auth_headers(username, password, token))
        with urlopen(req, timeout=15, context=_SSL_CONTEXT) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
            name = body.get("displayName") or body.get("username") or "connected"
            return True, f"Connected to DHIS2 as {name}."
    except HTTPError as e:
        if e.code == 401:
            return False, "DHIS2 login failed - check username/password or token."
        return False, f"DHIS2 returned HTTP {e.code}."
    except URLError as e:
        return False, f"Could not reach DHIS2 server: {e.reason}"
    except Exception as e:
        return False, f"DHIS2 connection error: {e}"
