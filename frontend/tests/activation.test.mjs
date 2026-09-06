// Production TypeScript executed against a minimal DOM and controlled HTTP/clock.
// These are host interaction regressions, not browser or assistive certification.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { createContext, runInContext } from "node:vm";
import { webcrypto } from "node:crypto";
import { stripTypeScriptTypes } from "node:module";

const source = readFileSync(new URL("../src/main.ts", import.meta.url), "utf8");
const compiled = stripTypeScriptTypes(source.replace('import "./styles.css";', ""), { mode: "transform" });
const flush = () => new Promise((resolve) => setImmediate(resolve));

async function harness(origin = "http://127.0.0.1:8131") {
  let activeElement;
  class Element {
    children = [];
    listeners = {};
    attributes = {};
    textContent = "";
    className = "";
    disabled = false;
    constructor(tag) { this.tag = tag; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; }
    setAttribute(key, value) { this.attributes[key] = value; }
    addEventListener(name, listener) { (this.listeners[name] ??= []).push(listener); }
    focus() { activeElement = this; }
    click() { if (!this.disabled) for (const fn of this.listeners.click ?? []) fn(); }
    querySelector(selector) {
      const matches = (node) => selector.startsWith(".")
        ? node.className.split(" ").includes(selector.slice(1)) : node.tag === selector;
      for (const child of this.children) {
        if (matches(child)) return child;
        const nested = child.querySelector(selector);
        if (nested) return nested;
      }
      return null;
    }
    get text() { return [this.textContent, ...this.children.map((child) => child.text)].join(" "); }
  }
  const root = new Element("div");
  const responses = [{ status: 401 }];
  const requests = [];
  const timers = new Map();
  let timerId = 0;
  const context = createContext({
    exports: {}, require: () => ({}), Headers, URL, URLSearchParams, crypto: webcrypto,
    document: {
      querySelector: () => root, createElement: (tag) => new Element(tag),
      get activeElement() { return activeElement; }
    },
    window: {
      location: { origin, hash: "" }, scrollTo() {}, addEventListener() {},
      setTimeout(callback, delay) { timers.set(++timerId, { callback, delay }); return timerId; },
      clearTimeout(id) { timers.delete(id); }
    },
    async fetch(path, options) {
      requests.push({ path, options });
      const next = responses.shift();
      assert.notEqual(next, undefined, `Unexpected request: ${path}`);
      const value = typeof next === "function" ? await next() : next;
      if (value instanceof Error) throw value;
      return {
        ok: value.status < 400, status: value.status,
        headers: new Headers(value.headers),
        json: async () => value.body ?? { error: { code: "FIXTURE_ERROR", request_id: "fixture-request" } }
      };
    }
  });
  runInContext(compiled, context);
  await flush();
  return {
    root, responses, requests, timers, context,
    async click(selector = "button") { root.querySelector(selector).click(); await flush(); },
    async tick() {
      const [id, timer] = timers.entries().next().value;
      timers.delete(id);
      await timer.callback();
      await flush();
    }
  };
}

const activation = {
  status: 201, body: { activation_code: "FG-ABCDE-FGHJK", expires_at: "2099-01-01T00:00:00Z", poll_after_seconds: 1 }
};

for (const origin of ["http://127.0.0.1:8131", "http://localhost:8000", "http://[::1]:8131", "http://127.0.0.1"]) {
  test(`activation command preserves current origin ${origin}`, async () => {
    const app = await harness(origin);
    app.responses.push(activation);
    await app.click();
    assert.equal(app.root.querySelector("code").textContent,
      `forgegate dashboard-activate FG-ABCDE-FGHJK --server ${origin} --identity IDENTITY.json --private-key KEY.pem --role ROLE --project PROJECT_ID`);
    assert.equal(app.requests.at(-1).options.credentials, "same-origin");
    assert.equal(app.requests.at(-1).options.cache, "no-store");
    assert.equal(app.timers.size, 1);
  });
}

for (const failure of [new Error("connection unavailable"), { status: 500 }]) {
  test(`failed activation has an explicit working retry (${failure.status ?? "network"})`, async () => {
    const app = await harness();
    app.responses.push(failure);
    await app.click();
    assert.match(app.root.text, /Retry local activation/);
    assert.equal(app.timers.size, 0);
    app.responses.push(activation);
    await app.click();
    assert.match(app.root.text, /--server http:\/\/127.0.0.1:8131/);
    assert.equal(app.requests.length, 3);
  });
}

test("429 waits for Retry-After without automatically resubmitting", async () => {
  const app = await harness();
  app.responses.push({ status: 429, headers: { "Retry-After": "7" } });
  await app.click();
  assert.equal(app.root.querySelector("button").disabled, true);
  assert.equal([...app.timers.values()][0].delay, 7000);
  await app.click();
  assert.equal(app.requests.length, 2);
  await app.tick();
  assert.equal(app.root.querySelector("button").disabled, false);
  assert.equal(app.requests.length, 2);
});

for (const status of [401, 404, 410]) {
  test(`expired/unknown activation ${status} explains recovery`, async () => {
    const app = await harness();
    app.responses.push(activation, { status });
    await app.click();
    await app.tick();
    assert.match(app.root.text, /expired or is no longer available/);
    assert.equal(app.root.querySelector("code"), null);
    assert.equal(app.root.querySelector("button").textContent, "Start local activation");
    assert.equal(app.timers.size, 0);
    app.responses.push(activation);
    await app.click();
    assert.match(app.root.text, /A new one-time activation is pending/);
    assert.doesNotMatch(app.root.text, /expired or is no longer available/);
  });
}

test("poll network failure retains a route back to activation", async () => {
  const app = await harness();
  app.responses.push(activation, new Error("offline"));
  await app.click();
  await app.tick();
  assert.match(app.root.text, /Retry local activation/);
  await app.click();
  assert.match(app.root.text, /Start local activation/);
  assert.equal(app.requests.length, 3);
  assert.equal(app.timers.size, 0);
});

test("late activation creation cannot restart polling after leaving the screen", async () => {
  const app = await harness();
  let finish;
  app.responses.push(() => new Promise((resolve) => { finish = resolve; }));
  await app.click();
  runInContext("renderActivation()", app.context);
  finish(activation);
  await flush();
  assert.equal(app.timers.size, 0);
  assert.equal(app.root.querySelector("code"), null);
});

test("late polling response cannot replace a newer activation screen", async () => {
  const app = await harness();
  let finish;
  app.responses.push(activation, () => new Promise((resolve) => { finish = resolve; }));
  await app.click();
  const pending = app.tick();
  await flush();
  runInContext("renderActivation('New screen')", app.context);
  finish({ status: 401 });
  await pending;
  assert.match(app.root.text, /New screen/);
  assert.doesNotMatch(app.root.text, /expired or is no longer available/);
  assert.equal(app.timers.size, 0);
});
