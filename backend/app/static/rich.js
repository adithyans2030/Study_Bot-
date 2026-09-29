// A small, DOM-free parser for the light Markdown that language models produce.
// It only builds a data structure; app.js turns that into elements with textContent, never
// innerHTML, so model output (which may echo untrusted document text) cannot inject HTML.
//
// Blocks:  {type:'p'|'h', inline}  {type:'ul'|'ol', items:[inline]}  {type:'pre', text}
//          {type:'table', head:[inline]|null, rows:[[inline]]}
// Inline:  {t:'text', v}  {t:'strong', v}  {t:'code', v}  {t:'cite', n}

const INLINE = /(\*\*[^*\n]+\*\*|`[^`\n]+`|\[\d+(?:\s*[,;]\s*\d+)*\])/g;

export function parseInline(text) {
  const out = [];
  let last = 0;
  for (const match of text.matchAll(INLINE)) {
    if (match.index > last) out.push({ t: 'text', v: text.slice(last, match.index) });
    const token = match[0];
    if (token.startsWith('**')) out.push({ t: 'strong', v: token.slice(2, -2) });
    else if (token.startsWith('`')) out.push({ t: 'code', v: token.slice(1, -1) });
    else for (const n of token.slice(1, -1).split(/[,;]/)) out.push({ t: 'cite', n: Number(n) });
    last = match.index + token.length;
  }
  if (last < text.length) out.push({ t: 'text', v: text.slice(last) });
  return out;
}

function tableCells(line) {
  return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim());
}

const isSeparator = (line) => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(line);
const isTableRow = (line) => /^\s*\|.*\|\s*$/.test(line);

export function parseRich(text) {
  const blocks = [];
  const lines = String(text ?? '').replace(/\r\n?/g, '\n').split('\n');
  let list = null;
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (line.trim().startsWith('```')) {  // fenced code, up to the closing fence (or the end)
      const code = [];
      i += 1;
      while (i < lines.length && !lines[i].trim().startsWith('```')) code.push(lines[i++]);
      i += 1;
      blocks.push({ type: 'pre', text: code.join('\n') });
      list = null;
      continue;
    }

    if (isTableRow(line)) {
      const rows = [];
      while (i < lines.length && isTableRow(lines[i])) rows.push(lines[i++]);
      const hasHead = rows.length > 1 && isSeparator(rows[1]);
      const body = rows.filter((r, idx) => !(hasHead && idx === 1) && !isSeparator(r));
      const cells = body.map((r) => tableCells(r).map(parseInline));
      blocks.push({ type: 'table', head: hasHead ? cells[0] : null, rows: hasHead ? cells.slice(1) : cells });
      list = null;
      continue;
    }

    const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
    const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);
    if (bullet || numbered) {
      const type = bullet ? 'ul' : 'ol';
      if (!list || list.type !== type) {
        list = { type, items: [] };
        blocks.push(list);
      }
      list.items.push(parseInline((bullet || numbered)[1]));
      i += 1;
      continue;
    }

    list = null;
    i += 1;
    if (!line.trim()) continue;
    const heading = line.match(/^#{1,4}\s+(.*)$/);
    blocks.push({ type: heading ? 'h' : 'p', inline: parseInline(heading ? heading[1] : line) });
  }
  return blocks;
}

// ---- reading answers aloud -------------------------------------------------------------------

const CITATION = /\[\d+(?:\s*[,;]\s*\d+)*\]/g;

/** What a voice should say for a piece of answer text: no citation markers, code, URLs or Markdown
 *  symbols. Returns '' if nothing speakable is left. */
export function speakable(text) {
  const cleaned = String(text ?? '')
    .replace(/```[\s\S]*?(```|$)/g, ' ')          // code blocks are not read out
    .replace(CITATION, ' ')
    .replace(/https?:\/\/\S+/g, ' ')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/\*\*([^*]*)\*\*/g, '$1')
    .replace(/^\s*(?:#{1,4}\s+|[-*\u2022]\s+|\d+[.)]\s+)/gm, '')
    .replace(/[|*_#`>]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  return /[A-Za-z0-9]/.test(cleaned) ? cleaned : '';
}

/** Split streamed text into finished sentences plus the unfinished remainder, so speech can start
 *  before the whole answer has arrived. A sentence ends at . ! ? followed by whitespace, or a newline. */
export function splitSentences(buffer) {
  const sentences = [];
  let start = 0;
  const end = /[.!?]+(?=\s)|\n/g;
  for (let match = end.exec(buffer); match; match = end.exec(buffer)) {
    const stop = match.index + match[0].length;
    sentences.push(buffer.slice(start, stop));
    start = stop;
  }
  return [sentences, buffer.slice(start)];
}
