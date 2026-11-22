// Shared edit commands for a JSON-backed A2UI surface. Pass paths as arrays of
// property names / array indices. Give each design its own DraftHistory.
const missing = Symbol('missing');
const plain = value => value !== null && typeof value === 'object' &&
  [Object.prototype, null].includes(Object.getPrototypeOf(value));
const copy = value => JSON.parse(JSON.stringify(value));

// An immutable JSON tree keeps caller-owned input, history and transport apart.
function copyJson(value, freeze = true, seen = new Set()) {
  if (value === null || typeof value === 'string' || typeof value === 'boolean' || Number.isFinite(value)) return value;
  if (!(Array.isArray(value) || plain(value)) || seen.has(value)) return missing;
  seen.add(value);
  const result = Array.isArray(value)
    ? Array.from(value, item => copyJson(item, freeze, seen))
    : Object.fromEntries(Object.entries(value).map(([key, item]) => [key, copyJson(item, freeze, seen)]));
  seen.delete(value);
  if (Object.values(result).includes(missing)) return missing;
  return freeze ? Object.freeze(result) : result;
}

function equal(left, right) {
  if (left === right) return true;
  if (!left || !right || typeof left !== 'object' || typeof right !== 'object' ||
      Array.isArray(left) !== Array.isArray(right)) return false;
  const keys = Object.keys(left);
  return keys.length === Object.keys(right).length &&
    keys.every(key => Object.hasOwn(right, key) && equal(left[key], right[key]));
}

// Object fields follow the baseline. Lists may change contents and a null
// baseline leaves the type open for an optional value.
function fits(original, value) {
  if (original === null) return true;
  if (Array.isArray(original)) return Array.isArray(value);
  if (!plain(original)) return typeof original === typeof value;
  return plain(value) && Object.keys(original).length === Object.keys(value).length &&
    Object.keys(original).every(key => Object.hasOwn(value, key) && fits(original[key], value[key]));
}

function read(root, path) {
  if (!Array.isArray(path)) return missing;
  let node = root;
  for (const key of path) {
    if (Array.isArray(node)) {
      if (!Number.isInteger(key) || key < 0 || key >= node.length) return missing;
    } else if (!plain(node) || typeof key !== 'string' || !Object.hasOwn(node, key)) {
      return missing;
    }
    node = node[key];
  }
  return node;
}

function put(node, [key, ...rest], value) {
  if (key === undefined) return value;
  const child = put(node[key], rest, value);
  if (!Array.isArray(node)) return Object.freeze({ ...node, [key]: child });
  const list = node.slice();
  list[key] = child;
  return Object.freeze(list);
}

function difference(original, current, root = false) {
  if (!plain(original) || !plain(current)) return equal(original, current) ? missing : current;
  const fields = [];
  for (const key of Object.keys(current)) {
    const change = difference(original[key], current[key]);
    if (change !== missing) fields.push([key, change]);
    else if (root && plain(original[key])) fields.push([key, {}]);
  }
  return fields.length || root ? Object.fromEntries(fields) : missing;
}

function hex(value) {
  if (typeof value !== 'string' || !/^#(?:[\da-f]{3,4}|[\da-f]{6}|[\da-f]{8})$/i.test(value)) return null;
  const digits = value.slice(1).toLowerCase();
  return '#' + (digits.length <= 4 ? Array.from(digits, char => char + char).join('') : digits);
}

/** Bind an existing A2UI 1.0 surface to a synchronous MessageProcessor. */
export function createDataModelPublisher({ surfaceId, path = '/draft', processMessages }) {
  if (typeof surfaceId !== 'string' || !surfaceId.trim() || typeof path !== 'string' ||
      !path.startsWith('/') || typeof processMessages !== 'function') throw new TypeError('Invalid A2UI publisher configuration');
  return value => {
    const model = copyJson(value, false);
    if (model === missing) throw new TypeError('Expected JSON data for the A2UI model');
    return processMessages([{ version: '1.0', updateDataModel: { surfaceId, path, value: model } }]);
  };
}

export class DraftHistory {
  #baseline;
  #value;
  #past = [];
  #future = [];
  #publish;
  #publishing = false;
  #limit;
  #bounds;
  group = null;

  constructor(baseline, { publish, historyLimit = 60, moveBounds } = {}) {
    this.#baseline = copyJson(baseline);
    if (!plain(this.#baseline)) throw new TypeError('Expected a JSON object baseline');
    if (publish !== undefined && typeof publish !== 'function') throw new TypeError('Expected a synchronous publisher');
    if (!Number.isSafeInteger(historyLimit) || historyLimit < 1) throw new RangeError('Invalid historyLimit');
    if (moveBounds !== undefined && !(Array.isArray(moveBounds) && moveBounds.length === 2 &&
        moveBounds.every(Number.isFinite) && moveBounds[0] <= moveBounds[1])) throw new RangeError('Invalid moveBounds');
    this.#value = this.#baseline;
    this.#publish = publish;
    this.#limit = historyLimit;
    this.#bounds = moveBounds?.slice();
  }

  get baseline() { return this.#baseline; }
  get value() { return this.#value; }
  get history() { return this.#past.slice(); }
  get canRedo() { return this.#future.length > 0; }
  get changed() { return !equal(this.#value, this.#baseline); }
  get edits() { return copy(difference(this.#baseline, this.#value, true)); }
  snapshot() { return copy(this.#value); }

  // A rejected update leaves the current value and both history stacks intact.
  #accept(next) {
    if (this.#publishing || equal(this.#value, next)) return false;
    this.#publishing = true;
    try {
      const result = this.#publish?.(next);
      if (result && typeof result.then === 'function') {
        // Surface the contract error synchronously and consume a late rejection.
        Promise.resolve(result).catch(() => {});
        throw new TypeError('The publisher must be synchronous');
      }
      return result !== false;
    } finally {
      this.#publishing = false;
    }
  }

  #record(next, group) {
    if (!this.#accept(next)) return false;
    if (group === null || group !== this.group || this.#past.length === 0) {
      this.#past.push(this.#value);
      if (this.#past.length > this.#limit) this.#past.shift();
    } else if (equal(next, this.#past.at(-1))) {
      // Reverting a color picker or text field before blur cancels its undo step.
      this.#past.pop();
      group = null;
    }
    this.#future = [];
    this.group = group;
    this.#value = next;
    return true;
  }

  replace(value, group = null) {
    const next = copyJson(value);
    return next !== missing && fits(this.#baseline, next) && this.#record(next, group);
  }

  edit(path, value, group = null) {
    const before = read(this.#value, path);
    if (before === missing) return false;
    const next = copyJson(value);
    if (next === missing || equal(before, next)) return false;
    const revised = put(this.#value, path, next);
    return fits(this.#baseline, revised) && this.#record(revised, group);
  }

  setText(path, text, group = null) {
    const previous = read(this.#value, path);
    return typeof text === 'string' && (previous === null || typeof previous === 'string') && this.edit(path, text, group);
  }

  setColor(path, color, group = null) {
    const next = hex(color);
    const previous = read(this.#value, path);
    return next !== null && (previous === null || typeof previous === 'string') &&
      hex(previous) !== next && this.edit(path, next, group);
  }

  // Supply absolute coordinates in the units used by the bound component.
  move(path, x, y, group = null) {
    const block = read(this.#value, path);
    if (!plain(block) || ![block.x, block.y, x, y].every(Number.isFinite)) return false;
    if (this.#bounds && [x, y].some(n => n < this.#bounds[0] || n > this.#bounds[1])) return false;
    return this.edit(path, { ...block, x, y }, group);
  }

  // For a catalog whose order is bound to an array in the data model.
  reorder(path, from, to, group = null) {
    const list = read(this.#value, path);
    if (!Array.isArray(list) || from === to ||
        ![from, to].every(n => Number.isInteger(n) && n >= 0 && n < list.length)) return false;
    const next = list.slice();
    next.splice(to, 0, next.splice(from, 1)[0]);
    return this.edit(path, next, group);
  }

  #step(source, destination) {
    const next = source.at(-1);
    if (!next || !this.#accept(next)) return false;
    destination.push(this.#value);
    this.#value = source.pop();
    this.group = null;
    return true;
  }

  undo() { return this.#step(this.#past, this.#future); }
  redo() { return this.#step(this.#future, this.#past); }
  reset() { return this.#record(this.#baseline, null); }

  // Load a complete compatible snapshot as the start of a new history.
  restore(snapshot) {
    const next = copyJson(snapshot);
    if (next === missing || !fits(this.#baseline, next) || !this.#accept(next)) return false;
    this.#past = [];
    this.#future = [];
    this.group = null;
    this.#value = next;
    return true;
  }
}
