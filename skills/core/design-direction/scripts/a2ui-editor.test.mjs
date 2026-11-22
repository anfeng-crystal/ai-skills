import assert from 'node:assert/strict';
import test from 'node:test';
import { createDataModelPublisher, DraftHistory } from './a2ui-editor.mjs';

const title = ['items', 'intro', 'title'];
const accent = ['theme', 'accent'];
const item = ['items', 'intro'];
const base = () => ({
  theme: { accent: '#112233', paper: '#ffffff' },
  items: { intro: { title: 'Hello', x: 0, y: 0 }, end: { title: 'Bye' } },
  order: ['intro', 'end'],
});

test('text, color, position and bound order update the same A2UI 1.0 model', () => {
  const messages = [];
  const publish = createDataModelPublisher({ surfaceId: 'preview', path: '/page', processMessages: batch => messages.push(...batch) });
  const editor = new DraftHistory(base(), { publish, moveBounds: [-3, 3] });
  assert.ok(editor.setText(title, '新的标题'));
  assert.ok(editor.setColor(accent, '#AbC'));
  assert.ok(editor.move(item, 2, -1));
  assert.ok(editor.reorder(['order'], 0, 1));
  assert.equal(messages.length, 4);
  assert.deepEqual(messages.at(-1), {
    version: '1.0', updateDataModel: { surfaceId: 'preview', path: '/page', value: editor.snapshot() },
  });
  assert.deepEqual(editor.value.items.intro, { title: '新的标题', x: 2, y: -1 });
  assert.deepEqual(editor.value.items.end, base().items.end);
  assert.deepEqual(editor.value.theme, { accent: '#aabbcc', paper: '#ffffff' });
  assert.deepEqual(editor.value.order, ['end', 'intro']);
  messages.at(-1).updateDataModel.value.items.intro.title = 'transport copy';
  assert.equal(editor.value.items.intro.title, '新的标题');
});

test('typing groups, reset, redo and new branches preserve the expected undo point', () => {
  const editor = new DraftHistory(base(), { historyLimit: 2 });
  editor.setText(title, 'H', 'typing');
  editor.setText(title, 'Hi', 'typing');
  assert.equal(editor.history.length, 1);
  assert.ok(editor.undo());
  assert.equal(editor.value.items.intro.title, 'Hello');
  assert.ok(editor.redo());
  assert.equal(editor.value.items.intro.title, 'Hi');
  assert.ok(editor.reset());
  assert.equal(editor.changed, false);
  assert.ok(editor.undo());
  assert.equal(editor.value.items.intro.title, 'Hi');
  assert.ok(editor.setText(title, ''));
  assert.equal(editor.canRedo, false);
  assert.ok(editor.setText(title, 'Last'));
  assert.equal(editor.history.length, 2);
  assert.ok(editor.undo());
  assert.equal(editor.value.items.intro.title, '');
  assert.ok(editor.undo());
  assert.equal(editor.value.items.intro.title, 'Hi');
  assert.equal(editor.undo(), false);
});

test('reverting a complete edit group leaves earlier undo steps reachable', () => {
  const editor = new DraftHistory(base());
  editor.setText(title, 'First');
  editor.setColor(accent, '#abcd00', 'picker');
  editor.setColor(accent, '#112233', 'picker');
  assert.equal(editor.history.length, 1);
  assert.ok(editor.undo());
  assert.deepEqual(editor.value, base());
});

test('rejected input and no-ops do not publish or consume a redo step', () => {
  let writes = 0;
  const editor = new DraftHistory(base(), { publish: () => { writes++; }, moveBounds: [-3, 3] });
  editor.move(item, 1, 0);
  editor.undo();
  const cycle = {}; cycle.self = cycle;
  for (const run of [
    () => editor.setText(title, 5), () => editor.setText(title, 'Hello'),
    () => editor.setColor(accent, '#123'), () => editor.setColor(accent, 'unknown'),
    () => editor.move(item, 4, 1), () => editor.move(item, NaN, 1),
    () => editor.reorder(['order'], 0, 3), () => editor.reorder(['order'], 0, 0),
    () => editor.edit(['items', 'missing'], 'x'), () => editor.edit(['__proto__', 'x'], 1),
    () => editor.edit(['order', 'length'], 0), () => editor.edit(['order'], cycle),
    () => editor.edit(title, undefined), () => editor.restore({ other: 1 }),
    () => editor.restore(editor.snapshot()), () => editor.reset(),
  ]) assert.equal(run(), false);
  assert.equal(writes, 2);
  assert.equal(editor.history.length, 0);
  assert.ok(editor.canRedo);
  assert.deepEqual(editor.value, base());
  assert.ok(editor.redo());
  assert.equal(editor.value.items.intro.x, 1);
});

test('a transport refusal or exception cannot partially advance an edit, undo or restore', () => {
  let mode = 'ok';
  const editor = new DraftHistory(base(), { publish() {
    if (mode === 'throw') throw new Error('unavailable');
    return mode === 'ok';
  } });
  editor.setText(title, 'Saved');
  mode = 'refuse';
  assert.equal(editor.move(item, 1, 2), false);
  assert.equal(editor.undo(), false);
  assert.equal(editor.restore(base()), false);
  mode = 'throw';
  assert.throws(() => editor.reset(), /unavailable/);
  assert.equal(editor.value.items.intro.title, 'Saved');
  assert.deepEqual([editor.value.items.intro.x, editor.value.items.intro.y], [0, 0]);
  assert.equal(editor.history.length, 1);
  mode = 'ok';
  assert.ok(editor.undo());
  assert.deepEqual(editor.value, base());
});

test('independent versions exchange complete snapshots and export only changed fields', () => {
  const original = base();
  const a = new DraftHistory(original);
  const b = new DraftHistory(original);
  original.items.intro.title = 'user-owned input';
  a.setText(title, 'A');
  assert.equal(b.value.items.intro.title, 'Hello');
  assert.deepEqual(a.edits, { theme: {}, items: { intro: { title: 'A' } } });
  const snapshot = a.snapshot();
  assert.ok(b.restore(snapshot));
  snapshot.items.intro.title = 'changed after load';
  assert.equal(b.value.items.intro.title, 'A');
  assert.equal(b.history.length, 0);
  assert.throws(() => { b.value.items.intro.title = 'mutate history'; }, TypeError);
  b.setText(title, 'B');
  assert.equal(a.value.items.intro.title, 'A');
  assert.ok(b.undo());
  assert.equal(b.value.items.intro.title, 'A');
});
