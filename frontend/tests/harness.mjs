// Production TypeScript executed against a minimal DOM and controlled HTTP/clock.
// These are host interaction regressions, not browser or assistive certification.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createContext, runInContext } from "node:vm";
import { webcrypto } from "node:crypto";
import { stripTypeScriptTypes } from "node:module";

const source = readFileSync(new URL("../src/main.ts", import.meta.url), "utf8");
const compiled = stripTypeScriptTypes(source.replace('import "./styles.css";', ""), { mode: "transform" });
export const flush = () => new Promise((resolve) => setImmediate(resolve));

export async function harness(origin = "http://127.0.0.1:8131") {
  let activeElement;
  class Element {
    children = [];
    listeners = {};
    attributes = {};
    textContent = "";
    className = "";
    disabled = false;
    files = undefined;
    customValidity = "";
    open = false;
    isConnected = true;
    constructor(tag) { this.tag = tag; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; }
    setAttribute(key, value) { this.attributes[key] = value; }
    setCustomValidity(value) { this.customValidity = value; }
    addEventListener(name, listener) { (this.listeners[name] ??= []).push(listener); }
    focus() { activeElement = this; }
    click() { if (!this.disabled) for (const fn of this.listeners.click ?? []) fn(); }
    get firstElementChild() { return this.children[0] ?? null; }
    reportValidity() { return false; }
    showModal() { this.open = true; }
    close() { this.open = false; for (const fn of this.listeners.close ?? []) fn(); }
    remove() { this.isConnected = false; }
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
    Blob, TextDecoder, TextEncoder, btoa,
    document: {
      querySelector: () => root, createElement: (tag) => new Element(tag),
      body: root,
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
      const responseBytes = value.bytes ?? new TextEncoder().encode(
        value.text ?? JSON.stringify(value.body ?? { error: { code: "FIXTURE_ERROR", request_id: "fixture-request" } })
      );
      return {
        ok: value.status < 400, status: value.status,
        headers: new Headers(value.headers),
        json: async () => value.body ?? { error: { code: "FIXTURE_ERROR", request_id: "fixture-request" } },
        arrayBuffer: async () => responseBytes.buffer.slice(responseBytes.byteOffset, responseBytes.byteOffset + responseBytes.byteLength),
        blob: async () => new Blob([responseBytes])
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
