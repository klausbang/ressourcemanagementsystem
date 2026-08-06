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

  // Builds a full keyboard-navigable, copy/paste/undo-capable editable grid (the
  // prototype known as "Option C") into an empty container element, parameterized by
  // an arbitrary column list instead of the fixed sandbox FIELDS above. Used by both
  // the sandbox_c.html prototype and the Admin Proposals "Table view".
  //
  // config:
  //   grid            - empty container element the grid is built into (required)
  //   fields           - [{key, label, editable}], in column order (required).
  //                       editable defaults to true.
  //   idField          - optional key naming the row-identity field. If it isn't
  //                       already in `fields`, a read-only leading column is added for it.
  //   rows             - initial array of plain row objects (required)
  //   filterable       - whether to build the filter row / wire the search toggle (default true)
  //   allowAddRow      - whether "+ Row" and paste-growing-past-the-end may add rows (default true)
  //   allowDeleteRow   - whether Delete/Backspace/Ctrl+X on a row-selection removes rows,
  //                       as opposed to just clearing editable cell contents (default true)
  //   toolbar          - { undo, addRow, delRow, copy, searchToggle, editMulti, exportJson,
  //                        importFile, save } - element refs; any may be omitted/null.
  //   filterRow        - element for the filter-input row (required if filterable)
  //   statusBar        - element for the row-count status line (optional)
  //   multiEditStatus  - element for the multi-edit status line (optional)
  //   exportFilename   - filename for the Export JSON button (default "export.json")
  //   onSave           - function(rows) called with the current grid data when Save is
  //                       clicked (required if a save button is given)
  function createEditableGrid(config) {
    var grid = config.grid;
    var fields = config.fields.slice();
    var idField = config.idField || null;
    if (idField && !fields.some(function (f) { return f.key === idField; })) {
      fields.unshift({ key: idField, label: idField, editable: false });
    }
    var filterable = config.filterable !== false;
    var allowAddRow = config.allowAddRow !== false;
    var allowDeleteRow = config.allowDeleteRow !== false;
    var toolbar = config.toolbar || {};
    var filterRow = config.filterRow || null;
    var statusBarEl = config.statusBar || null;
    var multiEditStatus = config.multiEditStatus || null;
    var MAX_UNDO = 50;
    var undoStack = [];

    function isEditable(c) { return fields[c] && fields[c].editable !== false; }

    function dataRows() {
      return Array.prototype.filter.call(grid.children, function (r) {
        return !r.classList.contains("header") && !r.classList.contains("sbx-filter-row");
      });
    }
    function cellAt(r, c) {
      var rows = dataRows();
      if (!rows[r]) return null;
      return rows[r].querySelector('.sbx-cell[data-col="' + c + '"]');
    }
    function rowHandleAt(r) {
      var rows = dataRows();
      return rows[r] ? rows[r].querySelector(".sbx-row-handle") : null;
    }

    var active = { row: 0, col: 0 };
    var selection = null; // {r1,c1,r2,c2} or null (meaning just the active cell)
    var selectionMode = "cell"; // "cell" | "row" | "column" | "all"

    function clearHighlight() {
      grid.querySelectorAll(".sbx-cell.active,.sbx-cell.selected,.sbx-row-handle.selected").forEach(function (el) {
        el.classList.remove("active", "selected");
      });
    }

    function bounds() {
      var sel = selection || { r1: active.row, c1: active.col, r2: active.row, c2: active.col };
      return {
        r1: Math.min(sel.r1, sel.r2), r2: Math.max(sel.r1, sel.r2),
        c1: Math.min(sel.c1, sel.c2), c2: Math.max(sel.c1, sel.c2),
      };
    }

    function render() {
      dataRows().forEach(function (row, i) { row.setAttribute("data-row", i); });
      clearHighlight();
      var b = bounds();
      for (var r = b.r1; r <= b.r2; r++) {
        for (var c = b.c1; c <= b.c2; c++) {
          var cell = cellAt(r, c);
          if (cell) cell.classList.add("selected");
        }
        if (selectionMode === "row" || selectionMode === "all") {
          var handle = rowHandleAt(r);
          if (handle) handle.classList.add("selected");
        }
      }
      var activeCell = cellAt(active.row, active.col);
      if (activeCell) {
        activeCell.classList.add("active");
        activeCell.focus();
        var range = document.createRange();
        range.selectNodeContents(activeCell);
        range.collapse(false);
        var sel2 = window.getSelection();
        sel2.removeAllRanges();
        sel2.addRange(range);
      }
      updateStatusBar();
    }

    function updateStatusBar() {
      if (!statusBarEl) return;
      var rows = dataRows();
      var total = rows.length;
      var visible = rows.filter(function (r) { return r.style.display !== "none"; }).length;
      var b = bounds();
      var selectedRows = b.r2 - b.r1 + 1;
      var parts = [total + " row" + (total === 1 ? "" : "s") + " total"];
      if (visible !== total) parts.push(visible + " shown (filtered)");
      parts.push(selectedRows + " row" + (selectedRows === 1 ? "" : "s") + " selected");
      statusBarEl.textContent = parts.join(" · ");
    }

    // --- Search / filter ---
    function wildcardToRegex(pattern) {
      var escaped = pattern.replace(/[.+^${}()[\]\\]/g, "\\$&").replace(/\*/g, ".*").replace(/\?/g, ".");
      return new RegExp("^" + escaped + "$", "i");
    }

    function matchesFilter(value, filterText) {
      var branches = filterText.split("|").map(function (s) { return s.trim(); }).filter(function (s) { return s.length; });
      if (!branches.length) return true;
      return branches.some(function (branch) { return wildcardToRegex(branch).test(value); });
    }

    function applyFilters() {
      if (!filterRow) return;
      var inputs = filterRow.querySelectorAll("input[data-filter-col]");
      var activeFilters = [];
      inputs.forEach(function (input) {
        var text = input.value.trim();
        if (text) activeFilters.push({ col: Number(input.getAttribute("data-filter-col")), text: text });
      });
      dataRows().forEach(function (row) {
        var visible = activeFilters.every(function (f) {
          var cell = row.querySelector('.sbx-cell[data-col="' + f.col + '"]');
          return matchesFilter(cell ? cell.textContent.trim() : "", f.text);
        });
        row.style.display = visible ? "" : "none";
      });
      updateStatusBar();
    }

    if (filterable && filterRow && toolbar.searchToggle) {
      toolbar.searchToggle.addEventListener("click", function () {
        var isOpen = filterRow.classList.toggle("open");
        this.classList.toggle("active", isOpen);
        if (isOpen) {
          filterRow.querySelector("input").focus();
        } else {
          filterRow.querySelectorAll("input").forEach(function (i) { i.value = ""; });
          applyFilters();
        }
      });
      filterRow.addEventListener("input", applyFilters);
    }

    function setActive(r, c, extend) {
      var rows = dataRows();
      if (!rows.length) return;
      r = Math.max(0, Math.min(r, rows.length - 1));
      c = Math.max(0, Math.min(c, fields.length - 1));
      if (extend) {
        if (!selection) selection = { r1: active.row, c1: active.col, r2: active.row, c2: active.col };
        selection.r2 = r; selection.c2 = c;
      } else {
        selection = null;
      }
      selectionMode = "cell";
      active = { row: r, col: c };
      render();
    }

    function selectRow(r, extend) {
      var rows = dataRows();
      if (!rows.length) return;
      r = Math.max(0, Math.min(r, rows.length - 1));
      var anchorRow = extend && selectionMode === "row" && selection ? selection.r1 : r;
      selection = { r1: anchorRow, c1: 0, r2: r, c2: fields.length - 1 };
      selectionMode = "row";
      active = { row: r, col: 0 };
      render();
    }

    function selectColumn(c, extend) {
      var rows = dataRows();
      if (!rows.length) return;
      var anchorCol = extend && selectionMode === "column" && selection ? selection.c1 : c;
      selection = { r1: 0, c1: anchorCol, r2: rows.length - 1, c2: c };
      selectionMode = "column";
      active = { row: 0, col: c };
      render();
    }

    function selectAll() {
      var rows = dataRows();
      if (!rows.length) return;
      selection = { r1: 0, c1: 0, r2: rows.length - 1, c2: fields.length - 1 };
      selectionMode = "all";
      active = { row: 0, col: 0 };
      render();
    }

    // --- Undo ---
    function snapshotJson() { return JSON.stringify(gridToObjects()); }
    function pushUndo() {
      undoStack.push(snapshotJson());
      if (undoStack.length > MAX_UNDO) undoStack.shift();
    }
    function restoreJson(json) {
      var objs = JSON.parse(json);
      if (multiEditRows) exitMultiEdit();
      dataRows().forEach(function (r) { r.remove(); });
      objs.forEach(function (o) { grid.appendChild(makeRow(o)); });
      selection = null;
      selectionMode = "cell";
      active = { row: 0, col: 0 };
      render();
    }
    function undo() {
      if (!undoStack.length) return;
      restoreJson(undoStack.pop());
    }

    var focusSnapshot = null;
    var focusValueBefore = null;
    grid.addEventListener("focusin", function (e) {
      var cell = e.target.closest(".sbx-cell");
      if (!cell || cell.closest(".header")) return;
      focusSnapshot = snapshotJson();
      focusValueBefore = cell.textContent;
    });
    grid.addEventListener("focusout", function (e) {
      var cell = e.target.closest(".sbx-cell");
      if (!cell || cell.closest(".header")) return;
      if (focusSnapshot !== null && cell.textContent !== focusValueBefore) {
        undoStack.push(focusSnapshot);
        if (undoStack.length > MAX_UNDO) undoStack.shift();
      }
      focusSnapshot = null;
    });

    // --- Click handling: cells, row handles, column headers, corner ---
    grid.addEventListener("click", function (e) {
      if (e.target.closest(".sbx-corner-select-all")) {
        selectAll();
        return;
      }
      var handle = e.target.closest(".sbx-row-handle");
      if (handle) {
        var r = Array.prototype.indexOf.call(dataRows(), handle.parentElement);
        selectRow(r, e.shiftKey);
        return;
      }
      var headerCell = e.target.closest(".header .sbx-cell");
      if (headerCell) {
        selectColumn(Number(headerCell.getAttribute("data-col")), e.shiftKey);
        return;
      }
      var cell = e.target.closest(".sbx-cell");
      if (!cell || cell.closest(".header")) return;
      var row = Array.prototype.indexOf.call(dataRows(), cell.parentElement);
      var col = Number(cell.getAttribute("data-col"));
      setActive(row, col, e.shiftKey);
    });

    function copySelection() {
      var b = bounds();
      var lines = [];
      for (var r = b.r1; r <= b.r2; r++) {
        var line = [];
        for (var c = b.c1; c <= b.c2; c++) {
          var cell = cellAt(r, c);
          line.push(cell ? cell.textContent.trim() : "");
        }
        lines.push(line.join("\t"));
      }
      copyText(lines.join("\n"));
    }

    function clearSelectionContents() {
      var b = bounds();
      pushUndo();
      for (var r = b.r1; r <= b.r2; r++) {
        for (var c = b.c1; c <= b.c2; c++) {
          if (!isEditable(c)) continue;
          var cell = cellAt(r, c);
          if (cell) cell.textContent = "";
        }
      }
      render();
    }

    // --- Edit multiple rows at once ---
    var multiEditRows = null;

    function updateMultiEditHighlight() {
      grid.querySelectorAll(".sbx-multiedit-anchor,.sbx-multiedit-target").forEach(function (el) {
        el.classList.remove("sbx-multiedit-anchor", "sbx-multiedit-target");
      });
      if (!multiEditRows) {
        if (multiEditStatus) multiEditStatus.textContent = "";
        return;
      }
      var rows = dataRows();
      multiEditRows.forEach(function (r, i) {
        var row = rows[r];
        if (row) row.classList.add(i === 0 ? "sbx-multiedit-anchor" : "sbx-multiedit-target");
      });
      if (multiEditStatus) {
        multiEditStatus.textContent = "Editing the highlighted row - press Ctrl+R to repeat your changes on the other "
          + (multiEditRows.length - 1) + " selected row(s), or Esc to cancel.";
      }
    }

    function exitMultiEdit() {
      multiEditRows = null;
      updateMultiEditHighlight();
    }

    function startMultiEdit() {
      if (selectionMode !== "row") {
        window.alert("Select 2 or more rows first, using the row handles on the left.");
        return;
      }
      var b = bounds();
      var rows = [];
      for (var r = b.r1; r <= b.r2; r++) rows.push(r);
      if (rows.length < 2) {
        window.alert("Select 2 or more rows first, using the row handles on the left.");
        return;
      }
      multiEditRows = rows;
      setActive(rows[0], 0, false);
      updateMultiEditHighlight();
    }

    function repeatMultiEdit() {
      if (!multiEditRows || multiEditRows.length < 2) return;
      pushUndo();
      var rows = dataRows();
      var anchorRow = rows[multiEditRows[0]];
      if (!anchorRow) { exitMultiEdit(); return; }
      var anchorValues = fields.map(function (f, i) {
        var cell = anchorRow.querySelector('.sbx-cell[data-col="' + i + '"]');
        return cell ? cell.textContent : "";
      });
      for (var k = 1; k < multiEditRows.length; k++) {
        var targetRow = rows[multiEditRows[k]];
        if (!targetRow) continue;
        fields.forEach(function (f, i) {
          if (!isEditable(i)) return;
          var cell = targetRow.querySelector('.sbx-cell[data-col="' + i + '"]');
          if (cell) cell.textContent = anchorValues[i];
        });
      }
      exitMultiEdit();
      render();
    }

    if (toolbar.editMulti) toolbar.editMulti.addEventListener("click", startMultiEdit);

    function deleteSelectedRows() {
      if (!allowDeleteRow) {
        clearSelectionContents();
        return;
      }
      var b = bounds();
      pushUndo();
      exitMultiEdit();
      var rows = dataRows();
      for (var r = b.r2; r >= b.r1; r--) {
        if (rows[r]) rows[r].remove();
      }
      selection = null;
      selectionMode = "cell";
      active = { row: Math.max(0, Math.min(b.r1, dataRows().length - 1)), col: 0 };
      render();
    }

    grid.addEventListener("keydown", function (e) {
      // Filter-row inputs are children of `grid` (so search-box focus/typing stays
      // inside the grid's DOM), but they're plain text inputs, not grid cells - a
      // Delete/Backspace clearing filter text must never fall through to the
      // data-row shortcuts below and delete whatever rows happen to be selected.
      if (e.target.closest(".sbx-filter-row")) return;
      var ctrl = e.ctrlKey || e.metaKey;
      var key = e.key;

      if (ctrl && key.toLowerCase() === "z") {
        e.preventDefault();
        undo();
        return;
      }
      if (ctrl && key.toLowerCase() === "c") {
        e.preventDefault();
        copySelection();
        return;
      }
      if (ctrl && key.toLowerCase() === "x") {
        e.preventDefault();
        copySelection();
        if (selectionMode === "row") {
          deleteSelectedRows();
        } else {
          clearSelectionContents();
        }
        return;
      }
      if (ctrl && key.toLowerCase() === "r" && multiEditRows) {
        e.preventDefault();
        repeatMultiEdit();
        return;
      }
      if (key === "Escape" && multiEditRows) {
        e.preventDefault();
        exitMultiEdit();
        return;
      }
      if ((key === "Delete" || key === "Backspace") && selection) {
        e.preventDefault();
        if (selectionMode === "row") {
          deleteSelectedRows();
        } else {
          clearSelectionContents();
        }
        return;
      }

      var moves = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] };
      if (moves[key]) {
        e.preventDefault();
        setActive(active.row + moves[key][0], active.col + moves[key][1], e.shiftKey);
      } else if (key === "Tab") {
        e.preventDefault();
        setActive(active.row, active.col + (e.shiftKey ? -1 : 1), false);
      } else if (key === "Enter") {
        e.preventDefault();
        setActive(active.row + 1, active.col, false);
      }
    });

    grid.addEventListener("paste", function (e) {
      e.preventDefault();
      var text = (e.clipboardData || window.clipboardData).getData("text");
      var pasted = parseDelimited(text);
      if (!pasted.length) return;
      pushUndo();
      var startRow = active.row, startCol = active.col;
      pasted.forEach(function (rowValues, rOffset) {
        var r = startRow + rOffset;
        if (!allowAddRow && dataRows().length <= r) return;
        while (dataRows().length <= r) grid.appendChild(makeRow({}));
        rowValues.forEach(function (val, cOffset) {
          var c = startCol + cOffset;
          if (c >= fields.length || !isEditable(c)) return;
          var cell = cellAt(r, c);
          if (cell) cell.textContent = val;
        });
      });
      selection = { r1: startRow, c1: startCol, r2: startRow + pasted.length - 1, c2: startCol + (pasted[0].length - 1) };
      selectionMode = "cell";
      active = { row: selection.r1, col: selection.c1 };
      render();
    });

    if (toolbar.copy) toolbar.copy.addEventListener("click", copySelection);
    if (toolbar.undo) toolbar.undo.addEventListener("click", undo);

    function makeRow(values) {
      values = values || {};
      var row = document.createElement("div");
      row.className = "sbx-grid-row";
      var handle = document.createElement("div");
      handle.className = "sbx-row-handle";
      handle.title = "Select row";
      row.appendChild(handle);
      fields.forEach(function (f, i) {
        var cell = document.createElement("div");
        cell.className = "sbx-cell" + (f.editable === false ? " sbx-cell-readonly" : "");
        cell.contentEditable = f.editable === false ? "false" : "true";
        if (f.editable === false) {
          // A non-contenteditable div with no tabindex silently ignores .focus() -
          // without this, becoming the active cell here (e.g. the default column a
          // row-handle selection lands on) leaves focus stuck outside the grid
          // entirely, and every keyboard shortcut (Ctrl+C/X/Z, Delete, arrows) stops
          // working until the user clicks into an actual editable cell.
          cell.tabIndex = -1;
        }
        cell.setAttribute("data-col", i);
        cell.textContent = values[f.key] !== undefined && values[f.key] !== null ? values[f.key] : "";
        row.appendChild(cell);
      });
      return row;
    }

    if (toolbar.addRow) {
      toolbar.addRow.addEventListener("click", function () {
        if (!allowAddRow) return;
        pushUndo();
        grid.appendChild(makeRow({}));
      });
    }

    if (toolbar.delRow) {
      toolbar.delRow.addEventListener("click", function () {
        if (!dataRows().length) return;
        deleteSelectedRows();
      });
    }

    function gridToObjects() {
      return dataRows().map(function (row) {
        var obj = {};
        fields.forEach(function (f, i) {
          var cell = row.querySelector('.sbx-cell[data-col="' + i + '"]');
          obj[f.key] = cell ? cell.textContent.trim() : "";
        });
        return obj;
      });
    }

    if (toolbar.exportJson) {
      toolbar.exportJson.addEventListener("click", function () {
        downloadFile(config.exportFilename || "export.json", JSON.stringify(gridToObjects(), null, 2), "application/json");
      });
    }

    if (toolbar.save) {
      toolbar.save.addEventListener("click", function () {
        if (config.onSave) config.onSave(gridToObjects());
      });
    }

    if (toolbar.importFile) {
      toolbar.importFile.addEventListener("change", function (e) {
        var file = e.target.files[0];
        if (!file) return;
        var reader = new FileReader();
        reader.onload = function () {
          var objs;
          try {
            var raw = file.name.toLowerCase().endsWith(".json")
              ? JSON.parse(reader.result)
              : rowsToObjects(parseDelimited(reader.result));
            if (Array.isArray(raw) && file.name.toLowerCase().endsWith(".json")) {
              objs = raw.map(function (o) {
                var row = {};
                fields.forEach(function (f) { row[f.key] = o[f.key] !== undefined && o[f.key] !== null ? String(o[f.key]) : ""; });
                return row;
              });
            } else {
              objs = raw;
            }
          } catch (err) {
            window.alert("Could not read that file: " + err.message);
            return;
          }
          pushUndo();
          objs.forEach(function (o) { grid.appendChild(makeRow(o)); });
          render();
        };
        reader.readAsText(file);
        e.target.value = "";
      });
    }

    // --- Build the grid DOM ---
    var headerRow = document.createElement("div");
    headerRow.className = "sbx-grid-row header";
    var corner = document.createElement("div");
    corner.className = "sbx-corner sbx-corner-select-all";
    corner.title = "Select all";
    headerRow.appendChild(corner);
    fields.forEach(function (f, i) {
      var cell = document.createElement("div");
      cell.className = "sbx-cell";
      cell.setAttribute("data-col", i);
      cell.textContent = f.label;
      headerRow.appendChild(cell);
    });
    grid.appendChild(headerRow);

    if (filterable && filterRow) {
      var filterCorner = document.createElement("div");
      filterCorner.className = "sbx-corner";
      filterCorner.style.cursor = "default";
      filterCorner.title = "Filter";
      filterRow.appendChild(filterCorner);
      fields.forEach(function (f, i) {
        var input = document.createElement("input");
        input.type = "text";
        input.setAttribute("data-filter-col", i);
        input.placeholder = "e.g. INV-* | EQP-*";
        filterRow.appendChild(input);
      });
      grid.appendChild(filterRow);
    }

    (config.rows || []).forEach(function (r) { grid.appendChild(makeRow(r)); });

    render();

    return { getRows: gridToObjects, undo: undo, render: render };
  }

  window.RmsSandbox = {
    FIELDS: FIELDS,
    parseDelimited: parseDelimited,
    rowsToObjects: rowsToObjects,
    parseJsonRows: parseJsonRows,
    objectsToTsv: objectsToTsv,
    downloadFile: downloadFile,
    copyText: copyText,
    createEditableGrid: createEditableGrid,
  };
})();
