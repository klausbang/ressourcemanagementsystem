// RMS Sandbox — shared parsing/export helpers for the three editable-table-view
// prototypes (Phase 22). Self-contained, no external dependencies, matching the rest
// of this app's JS.
(function () {
  "use strict";

  var FIELDS = ["code", "name", "category", "quantity", "notes"];

  // Splits a block of pasted/uploaded text into a 2D array of cell strings.
  // Excel/Google Sheets copy produces tab-separated text; a .csv file or a CSV-style
  // paste uses commas. Detected per-call by checking for a tab in the first line.
  function parseDelimited(text) {
    text = String(text || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    while (text.endsWith("\n")) text = text.slice(0, -1);
    if (!text) return [];
    var firstLine = text.split("\n")[0];
    if (firstLine.indexOf("\t") !== -1) {
      return text.split("\n").map(function (line) { return line.split("\t"); });
    }
    return parseCsv(text);
  }

  // A small CSV parser: handles quoted fields, escaped "" quotes, and commas/newlines
  // inside quotes - enough for a real Excel/Sheets "Save as CSV" export or a hand-typed
  // sample file, without pulling in a library for it.
  function parseCsv(text) {
    var rows = [];
    var row = [];
    var field = "";
    var inQuotes = false;
    for (var i = 0; i < text.length; i++) {
      var ch = text[i];
      if (inQuotes) {
        if (ch === '"') {
          if (text[i + 1] === '"') { field += '"'; i++; } else { inQuotes = false; }
        } else {
          field += ch;
        }
      } else if (ch === '"') {
        inQuotes = true;
      } else if (ch === ",") {
        row.push(field); field = "";
      } else if (ch === "\n") {
        row.push(field); field = ""; rows.push(row); row = [];
      } else {
        field += ch;
      }
    }
    row.push(field);
    rows.push(row);
    return rows;
  }

  // Turns a 2D array into row objects keyed by FIELDS. If the first row looks like a
  // header (its cells case-insensitively match known field names), it's used to map
  // columns and then dropped; otherwise columns are mapped positionally in FIELDS order.
  function rowsToObjects(grid) {
    if (!grid.length) return [];
    var header = grid[0].map(function (c) { return String(c).trim().toLowerCase(); });
    var looksLikeHeader = header.some(function (h) { return FIELDS.indexOf(h) !== -1; });
    var cols = looksLikeHeader ? header : FIELDS.slice(0, grid[0].length);
    var dataRows = looksLikeHeader ? grid.slice(1) : grid;
    return dataRows
      .filter(function (r) { return r.some(function (c) { return String(c).trim() !== ""; }); })
      .map(function (r) {
        var obj = {};
        cols.forEach(function (field, i) {
          if (FIELDS.indexOf(field) !== -1) obj[field] = r[i] !== undefined ? String(r[i]).trim() : "";
        });
        return obj;
      });
  }

  function parseJsonRows(text) {
    var data = JSON.parse(text);
    if (!Array.isArray(data)) throw new Error("Expected a JSON array of row objects");
    return data.map(function (obj) {
      var row = {};
      FIELDS.forEach(function (f) { row[f] = obj[f] !== undefined && obj[f] !== null ? String(obj[f]) : ""; });
      return row;
    });
  }

  function objectsToTsv(objs) {
    var lines = [FIELDS.join("\t")];
    objs.forEach(function (o) {
      lines.push(FIELDS.map(function (f) { return o[f] !== undefined && o[f] !== null ? o[f] : ""; }).join("\t"));
    });
    return lines.join("\n");
  }

  function downloadFile(filename, content, mime) {
    var blob = new Blob([content], { type: mime });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
    return Promise.resolve();
  }

  window.RmsSandbox = {
    FIELDS: FIELDS,
    parseDelimited: parseDelimited,
    rowsToObjects: rowsToObjects,
    parseJsonRows: parseJsonRows,
    objectsToTsv: objectsToTsv,
    downloadFile: downloadFile,
    copyText: copyText,
  };
})();
