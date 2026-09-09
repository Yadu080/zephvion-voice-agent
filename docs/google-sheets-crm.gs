/**
 * Google Sheets as a free CRM for the Zephvion AI voice agent.
 *
 * Receives every lead, appointment, support ticket and automation event the
 * agent produces, and appends it to a tab named after the record type.
 * Headers are created automatically from whatever fields arrive.
 *
 * SETUP
 *  1. Go to sheets.new to create a new Google Sheet. Name it e.g. "Zephvion CRM".
 *  2. Extensions -> Apps Script. Delete whatever is in the editor.
 *  3. Paste this entire file in, then click Save.
 *  4. Click Deploy -> New deployment.
 *       - Click the gear next to "Select type" and choose Web app
 *       - Description:      Zephvion CRM webhook
 *       - Execute as:       Me
 *       - Who has access:   Anyone            <-- required, the server calls it
 *  5. Click Deploy, then Authorize access and allow the permissions.
 *       (Google will warn the app is unverified because you just wrote it —
 *        choose Advanced, then "Go to ... (unsafe)" to continue.)
 *  6. Copy the Web app URL. It looks like:
 *       https://script.google.com/macros/s/AKfy..../exec
 *  7. Put it in .env AND in Render -> Environment:
 *       CRM_WEBHOOK_URL=<that url>
 *       AUTOMATION_WEBHOOK_URL=<the same url, if you don't use Zapier/Make>
 *
 * Re-deploy note: after editing this script, use Deploy -> Manage deployments
 * -> edit -> Version: New version, or the old code keeps running.
 */

function doPost(e) {
  try {
    var payload = JSON.parse(e.postData.contents);

    // The agent sends CRM records as {type: "lead", ...fields} and automation
    // events as {event: "lead.captured", data: {...}}. Normalise both.
    var sheetName, row;
    if (payload.event) {
      sheetName = 'events';
      row = flatten(payload.data || {});
      row.event = payload.event;
    } else {
      sheetName = payload.type || 'records';
      row = flatten(payload);
      delete row.type;
    }

    row.received_at = new Date();
    appendRow(sheetName, row);

    return json({ ok: true, sheet: sheetName });
  } catch (err) {
    return json({ ok: false, error: String(err) });
  }
}

function doGet() {
  // Lets you confirm the deployment works by opening the URL in a browser.
  return json({ ok: true, message: 'Zephvion CRM webhook is live.' });
}

/** Flattens one level of nesting so nested objects still land in columns. */
function flatten(obj) {
  var out = {};
  Object.keys(obj || {}).forEach(function (key) {
    var value = obj[key];
    if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
      Object.keys(value).forEach(function (inner) {
        out[key + '_' + inner] = value[inner];
      });
    } else if (Array.isArray(value)) {
      out[key] = value.join(', ');
    } else {
      out[key] = value;
    }
  });
  return out;
}

/** Appends to the named tab, creating it and widening headers as needed. */
function appendRow(sheetName, row) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(sheetName) || ss.insertSheet(sheetName);

  var headers = sheet.getLastRow() > 0
    ? sheet.getRange(1, 1, 1, Math.max(sheet.getLastColumn(), 1)).getValues()[0].filter(String)
    : [];

  // Add any columns this record introduces.
  var added = false;
  Object.keys(row).forEach(function (key) {
    if (headers.indexOf(key) === -1) {
      headers.push(key);
      added = true;
    }
  });

  if (added || sheet.getLastRow() === 0) {
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    sheet.getRange(1, 1, 1, headers.length).setFontWeight('bold');
    sheet.setFrozenRows(1);
  }

  var values = headers.map(function (key) {
    return row[key] !== undefined ? row[key] : '';
  });
  sheet.appendRow(values);
}

function json(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
