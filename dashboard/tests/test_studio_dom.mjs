// Run with `node --test dashboard/tests/test_studio_dom.mjs`; no browser or network.
//
// Regression guard for the blank Surveillance Studio feed.
//
// `.studio-prompt-chips` is a SIBLING of `.studio-feed`, not a child of it.
// The WIP refactor passed it as the `before` reference to `insertBefore`, e.g.
// `feed.insertBefore(runNode, chips)`. `Node.insertBefore(newNode, refNode)`
// throws `NotFoundError` when `refNode` is not a child of `newNode`'s parent,
// so `run()` threw on its first line and nothing was ever rendered into the
// feed — the user saw `#studio-feed` go completely blank after clicking a
// question chip and then Investigate.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../static/js/studio.js", import.meta.url), "utf8");
const template = source.slice(source.indexOf("root.innerHTML = `") + "root.innerHTML = `".length, source.lastIndexOf("`;"));

test("the prompt chips bar is a sibling of the feed, not nested inside it", () => {
  const feedAt = template.indexOf('class="studio-feed"');
  const chipsAt = template.indexOf('class="studio-prompt-chips"');
  assert.ok(feedAt >= 0, "the studio feed must exist in the shell template");
  assert.ok(chipsAt > feedAt, "the chips bar must come after the feed in the shell template");

  // Walk the template from the feed's opening tag to its matching close and
  // prove the chips bar is outside it.
  const open = template.indexOf(">", feedAt);
  let depth = 1, cursor = open + 1;
  while (cursor < template.length && depth > 0) {
    const nextOpen = template.indexOf("<div", cursor);
    const nextClose = template.indexOf("</div>", cursor);
    if (nextClose === -1) break;
    if (nextOpen !== -1 && nextOpen < nextClose) { depth += 1; cursor = nextOpen + 4; }
    else { depth -= 1; cursor = nextClose + 6; }
  }
  assert.ok(cursor < chipsAt, "the chips bar must sit outside the feed element");
});

test("the feed only inserts before a reference that is actually its child", () => {
  assert.match(
    source,
    /if \(before\?\.parentNode === target\) target\.insertBefore\(node, before\); else target\.append\(node\);/,
    "add() must fall back to append() when the reference is not a child of the target",
  );
});

test("investigation nodes are appended to the feed, never anchored to the sibling chips bar", () => {
  assert.doesNotMatch(
    source,
    /feed\.insertBefore\(runNode,\s*chips\)/,
    "runNode must be appended to the feed; anchoring it to the sibling chips bar throws NotFoundError",
  );
  assert.doesNotMatch(
    source,
    /add\(feed,[^)]*,\s*chips\)/,
    "welcome content must be appended to the feed, not inserted before the sibling chips bar",
  );
  assert.match(source, /feed\.querySelector\("\.studio-welcome"\)\?\.remove\(\); feed\.append\(runNode\);/);
});
