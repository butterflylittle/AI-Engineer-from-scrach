import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../lib/chat.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const chat = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`);

test("Enter submits when the message can be sent", () => {
  assert.equal(
    chat.chatKeyAction({ key: "Enter", shiftKey: false, isComposing: false }, true),
    "submit",
  );
});

test("Shift+Enter keeps the textarea newline behavior", () => {
  assert.equal(
    chat.chatKeyAction({ key: "Enter", shiftKey: true, isComposing: false }, true),
    "default",
  );
});

test("Enter during IME composition does not submit", () => {
  assert.equal(
    chat.chatKeyAction({ key: "Enter", shiftKey: false, isComposing: true }, true),
    "default",
  );
});

test("Enter does not submit an empty or disabled message", () => {
  assert.equal(
    chat.chatKeyAction({ key: "Enter", shiftKey: false, isComposing: false }, false),
    "prevent",
  );
});

test("a cached conversation is restored after a refresh", () => {
  const values = new Map();
  const storage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
  const key = chat.chatCacheKey("user-1", "kb-1");
  const messages = [
    { id: "question-1", role: "user", content: "What is RAG?" },
    { id: "answer-1", role: "assistant", content: "Retrieval-augmented generation." },
  ];

  chat.writeChatCache(storage, key, messages, "conversation-1");

  assert.deepEqual(chat.readChatCache(storage, key), {
    version: 1,
    conversationId: "conversation-1",
    messages,
  });
});

test("invalid or outdated cache data is discarded", () => {
  const values = new Map([["chat", JSON.stringify({ version: 0, messages: [] })]]);
  const storage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };

  assert.equal(chat.readChatCache(storage, "chat"), undefined);
  assert.equal(values.has("chat"), false);
});

test("unavailable storage safely falls back to memory-only chat", () => {
  assert.equal(chat.readChatCache(undefined, "chat"), undefined);
  assert.doesNotThrow(() => chat.writeChatCache(undefined, "chat", []));
  assert.doesNotThrow(() => chat.clearChatCache(undefined, "chat"));
});
