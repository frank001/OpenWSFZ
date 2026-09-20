/**
 * Read-only decoder-parameter page logic (decoder-param-readout, shim 20260054).
 *
 * Fetches GET /api/v1/decoder/params once on page load and lists EVERY entry it returns, grouped
 * into "Runtime-settable" and "Compile-time", each row `name · value · default`, plus the native
 * shim version. The endpoint reads the native library on every request, so what is shown is what
 * the decoder is running with NOW, not what app.json says.
 *
 * This page can change nothing: it builds table rows and text only. It never creates a form
 * control, never sends any request but the one GET, and holds no state.
 *
 * The data-shaping functions below are pure and exported so `node --test` can exercise them
 * without a DOM (see decoderParams.test.js); only `init()` touches `document`, and it only runs
 * in a browser.
 *
 * @module decoderParams
 */

/** `kind` value of a value that can be changed at run time. */
export const KIND_RUNTIME = 'runtime';

/** `kind` value of a constant that only a native rebuild can change. */
export const KIND_COMPILE_TIME = 'compile-time';

/**
 * Split the API's entries into the two groups the page shows, PRESERVING the native table's
 * order within each group.
 *
 * Throws rather than dropping anything: an empty table, or a row of a kind this page does not
 * know, must surface as an error on the page, never as a row that quietly does not appear
 * (design D12: nothing is omitted silently).
 *
 * @param {Array<{name: string, kind: string, value: number, default: number}>} entries
 * @returns {{runtime: object[], compileTime: object[]}}
 */
export function groupEntries(entries) {
  if (!Array.isArray(entries) || entries.length === 0) {
    throw new Error('The native decoder reported no parameters.');
  }
  const runtime = [];
  const compileTime = [];
  for (const entry of entries) {
    if (entry.kind === KIND_RUNTIME) {
      runtime.push(entry);
    } else if (entry.kind === KIND_COMPILE_TIME) {
      compileTime.push(entry);
    } else {
      throw new Error(`Unknown parameter kind '${entry.kind}' for '${entry.name}'.`);
    }
  }
  return { runtime, compileTime };
}

/**
 * The text shown for a value: the API's own number, verbatim. Deliberately NO rounding or
 * re-formatting, so the page shows exactly the value the API returned.
 * @param {number} value
 * @returns {string}
 */
export function formatValue(value) {
  return String(value);
}

/**
 * True when a parameter is running with something other than its compiled-in default.
 * @param {{value: number, default: number}} entry
 * @returns {boolean}
 */
export function differsFromDefault(entry) {
  return entry.value !== entry.default;
}

/**
 * Everything one table row shows, as plain data.
 * @param {{name: string, value: number, default: number}} entry
 * @returns {{name: string, value: string, default: string, differs: boolean}}
 */
export function rowModel(entry) {
  return {
    name: entry.name,
    value: formatValue(entry.value),
    default: formatValue(entry.default),
    differs: differsFromDefault(entry),
  };
}

/**
 * Append one row per entry to a <tbody>. Text only (`textContent`), never HTML, so nothing an
 * entry contains can be interpreted as markup.
 * @param {HTMLElement} tbody
 * @param {object[]} entries
 * @param {Document} doc
 */
function appendRows(tbody, entries, doc) {
  for (const entry of entries) {
    const model = rowModel(entry);
    const tr = doc.createElement('tr');
    tr.dataset.name = model.name;
    if (model.differs) tr.classList.add('param-differs');

    const nameTd = doc.createElement('td');
    nameTd.className = 'param-name';
    nameTd.textContent = model.name;

    const valueTd = doc.createElement('td');
    valueTd.className = 'param-value';
    valueTd.textContent = model.value;
    if (model.differs) {
      // A text marker, not colour alone: the state must not depend on seeing a colour.
      const mark = doc.createElement('span');
      mark.className = 'param-differs-mark';
      mark.textContent = 'differs';
      valueTd.append(' ', mark);
    }

    const defaultTd = doc.createElement('td');
    defaultTd.className = 'param-default';
    defaultTd.textContent = model.default;

    tr.append(nameTd, valueTd, defaultTd);
    tbody.append(tr);
  }
}

/** Load the table and render it. Browser only. */
async function init() {
  const statusEl = document.getElementById('dp-status');
  try {
    // Imported here, not at the top: api.js touches `window`/`sessionStorage` when it loads,
    // which would stop the pure functions above from being imported under `node --test`.
    const { getDecoderParams } = await import('./api.js');
    const response = await getDecoderParams();
    const { runtime, compileTime } = groupEntries(response.entries);

    document.getElementById('dp-shim-version').textContent = String(response.shimVersion);
    appendRows(document.getElementById('dp-runtime-body'), runtime, document);
    appendRows(document.getElementById('dp-compile-body'), compileTime, document);
    document.getElementById('dp-runtime').hidden = false;
    document.getElementById('dp-compile').hidden = false;
    statusEl.textContent =
      `${response.entries.length} parameters: ${runtime.length} runtime-settable, ` +
      `${compileTime.length} compile-time.`;
  } catch (err) {
    // Never show an empty table as if it were the answer: say plainly that the readout failed.
    statusEl.textContent = `Could not read the decoder parameters: ${err.message}`;
    statusEl.classList.add('param-error');
  }
}

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', init);
}
