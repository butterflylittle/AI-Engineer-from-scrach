import type { ChatMessage, Citation } from "@/types";

const CHAT_CACHE_VERSION = 1;

type ChatCache = {
  version: typeof CHAT_CACHE_VERSION;
  conversationId?: string;
  messages: ChatMessage[];
};

type ChatStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

type ChatKeyEvent = {
  key: string;
  shiftKey: boolean;
  isComposing: boolean;
};

export function getChatStorage(): ChatStorage | undefined {
  if (typeof window === "undefined") return undefined;
  try {
    return window.localStorage;
  } catch {
    return undefined;
  }
}

export function chatCacheKey(userId: string, knowledgeBaseId: string) {
  return `fieldnote:chat:${userId}:${knowledgeBaseId}`;
}

function isCitation(value: unknown): value is Citation {
  if (!value || typeof value !== "object") return false;
  const citation = value as Record<string, unknown>;
  return (
    typeof citation.document_id === "string" &&
    typeof citation.chunk_id === "string" &&
    typeof citation.filename === "string" &&
    (citation.page === null || typeof citation.page === "number")
  );
}

function isMessage(value: unknown): value is ChatMessage {
  if (!value || typeof value !== "object") return false;
  const message = value as Record<string, unknown>;
  return (
    typeof message.id === "string" &&
    (message.role === "user" || message.role === "assistant") &&
    typeof message.content === "string" &&
    (message.citations === undefined ||
      (Array.isArray(message.citations) && message.citations.every(isCitation)))
  );
}

export function readChatCache(storage: ChatStorage | undefined, key: string): ChatCache | undefined {
  if (!storage) return undefined;
  try {
    const raw = storage.getItem(key);
    if (!raw) return undefined;
    const cache = JSON.parse(raw) as Partial<ChatCache>;
    if (
      cache.version !== CHAT_CACHE_VERSION ||
      (cache.conversationId !== undefined && typeof cache.conversationId !== "string") ||
      !Array.isArray(cache.messages) ||
      !cache.messages.every(isMessage)
    ) {
      storage.removeItem(key);
      return undefined;
    }
    return cache as ChatCache;
  } catch {
    return undefined;
  }
}

export function writeChatCache(
  storage: ChatStorage | undefined,
  key: string,
  messages: ChatMessage[],
  conversationId?: string,
) {
  if (!storage) return;
  try {
    storage.setItem(key, JSON.stringify({ version: CHAT_CACHE_VERSION, conversationId, messages }));
  } catch {
    // Browsing modes and full quotas can make localStorage unavailable.
  }
}

export function clearChatCache(storage: ChatStorage | undefined, key: string) {
  if (!storage) return;
  try {
    storage.removeItem(key);
  } catch {
    // A new in-memory conversation should still work when storage is unavailable.
  }
}

export function chatKeyAction(event: ChatKeyEvent, canSend: boolean) {
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) return "default" as const;
  return canSend ? ("submit" as const) : ("prevent" as const);
}
