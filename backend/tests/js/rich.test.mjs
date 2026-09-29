import test from 'node:test';
import assert from 'node:assert/strict';
import { parseInline, parseRich } from '../../app/static/rich.js';

test('inline: bold, code, citations, and plain text in order', () => {
  assert.deepEqual(parseInline('Use **log_param** or `mlflow.log_params` [1][2] now'), [
    { t: 'text', v: 'Use ' }, { t: 'strong', v: 'log_param' }, { t: 'text', v: ' or ' },
    { t: 'code', v: 'mlflow.log_params' }, { t: 'text', v: ' ' }, { t: 'cite', n: 1 }, { t: 'cite', n: 2 },
    { t: 'text', v: ' now' }]);
});

test('inline: grouped citations become separate cite tokens', () => {
  assert.deepEqual(parseInline('true [1, 3]; also [2;4]').filter((t) => t.t === 'cite').map((t) => t.n), [1, 3, 2, 4]);
});

test('inline: brackets that are not citations stay text', () => {
  assert.deepEqual(parseInline('array[i] and [note]'), [{ t: 'text', v: 'array[i] and [note]' }]);
});

test('markup is data, never interpreted: HTML stays literal text', () => {
  const blocks = parseRich('<img src=x onerror=alert(1)> and <script>alert(2)</script>');
  assert.equal(blocks.length, 1);
  assert.deepEqual(blocks[0].inline, [{ t: 'text', v: '<img src=x onerror=alert(1)> and <script>alert(2)</script>' }]);
});

test('blocks: paragraphs, headings, bullet and numbered lists', () => {
  const blocks = parseRich('# Title\nIntro line\n\n- one\n- two [1]\n\n1. first\n2) second');
  assert.deepEqual(blocks.map((b) => b.type), ['h', 'p', 'ul', 'ol']);
  assert.equal(blocks[2].items.length, 2);
  assert.equal(blocks[3].items.length, 2);
  assert.deepEqual(blocks[2].items[1].at(-1), { t: 'cite', n: 1 });
});

test('blocks: fenced code is kept verbatim, including markup and unclosed fences', () => {
  const closed = parseRich('before\n```python\nx = "**not bold**" # [1]\n```\nafter');
  assert.deepEqual(closed.map((b) => b.type), ['p', 'pre', 'p']);
  assert.equal(closed[1].text, 'x = "**not bold**" # [1]');
  const open = parseRich('```\nnever closed');
  assert.deepEqual(open, [{ type: 'pre', text: 'never closed' }]);
});

test('blocks: markdown tables with a header row', () => {
  const [table] = parseRich('| Method | Pixels |\n|---|---|\n| Bilinear | 4 |\n| Bicubic | 16 [1] |');
  assert.equal(table.type, 'table');
  assert.deepEqual(table.head.map((c) => c[0].v), ['Method', 'Pixels']);
  assert.equal(table.rows.length, 2);
  assert.deepEqual(table.rows[1][1], [{ t: 'text', v: '16 ' }, { t: 'cite', n: 1 }]);
});

test('blocks: tables without a header row, and pipes in ordinary sentences', () => {
  const [table] = parseRich('| a | b |\n| c | d |');
  assert.equal(table.head, null);
  assert.equal(table.rows.length, 2);
  assert.equal(parseRich('use a | pipe here')[0].type, 'p');
});

test('empty and odd input never throws', () => {
  assert.deepEqual(parseRich(''), []);
  assert.deepEqual(parseRich(null), []);
  assert.doesNotThrow(() => parseRich('**unclosed and `unclosed and [1 and | | |\r\n\r\n```'));
});

import { speakable, splitSentences } from '../../app/static/rich.js';

test('speech: citation markers, code, urls and markdown symbols are not read out', () => {
  assert.equal(speakable('Bicubic uses **16 pixels** [1][2] and is smoother [3, 4].'), 'Bicubic uses 16 pixels and is smoother .');
  assert.equal(speakable('Use `mlflow.log_param` here.'), 'Use mlflow.log param here.');  // underscores are read as spaces
  assert.equal(speakable('See https://www.youtube.com/watch?v=abc for more'), 'See for more');
  assert.equal(speakable('- first point\n- second point'), 'first point second point');
  assert.equal(speakable('## Heading\n1. one\n2) two'), 'Heading one two');
  assert.equal(speakable('| a | b |'), 'a b');
});

test('speech: code blocks are skipped and empty results are empty strings', () => {
  assert.equal(speakable('Before\n```python\nprint("x")\n```\nAfter'), 'Before After');
  assert.equal(speakable('```never closed\ncode'), '');
  assert.equal(speakable('[1][2]'), '');
  assert.equal(speakable('   '), '');
  assert.equal(speakable(null), '');
});

test('sentences: finished sentences are separated from the unfinished tail', () => {
  assert.deepEqual(splitSentences('First one. Second one! Third is unfin'), [['First one.', ' Second one!'], ' Third is unfin']);
  assert.deepEqual(splitSentences('no end yet'), [[], 'no end yet']);
  assert.deepEqual(splitSentences('line one\nline two'), [['line one\n'], 'line two']);
});

test('sentences: decimals and abbreviations inside a word are not split points', () => {
  assert.deepEqual(splitSentences('It has 3.5 million pixels. Next'), [['It has 3.5 million pixels.'], ' Next']);
  assert.deepEqual(splitSentences('A 4x4 grid'), [[], 'A 4x4 grid']);
});

test('sentences: streaming in small pieces yields the same sentences as one big piece', () => {
  const text = 'Alpha is first. Beta is second! Gamma? Delta finishes here.\nEpsilon';
  const spoken = [];
  let buffer = '';
  for (const piece of text.match(/.{1,4}/gs)) {
    buffer += piece;
    const [done, rest] = splitSentences(buffer);
    spoken.push(...done);
    buffer = rest;
  }
  spoken.push(buffer);
  assert.equal(spoken.join(''), text, 'nothing is lost or duplicated');
});
