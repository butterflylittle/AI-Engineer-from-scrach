"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowUp,
  Check,
  FileText,
  LoaderCircle,
  MessageSquarePlus,
  Paperclip,
  Sparkles,
  Trash2,
  UploadCloud,
} from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";
import {
  chatCacheKey,
  chatKeyAction,
  clearChatCache,
  getChatStorage,
  readChatCache,
  writeChatCache,
} from "@/lib/chat";
import type { ChatMessage, Citation, DocumentItem, KnowledgeBase } from "@/types";

const stages: Record<string, string> = {
  route: "Deciding whether to search",
  retrieve: "Searching the knowledge base",
  rerank: "Ranking the strongest evidence",
  grade: "Checking evidence quality",
  rewrite: "Refining the search query",
  generate: "Composing a grounded answer",
};

export function KnowledgeWorkspace({ knowledgeBaseId, userId }: { knowledgeBaseId: string; userId: string }) {
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const messageRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController>(null);
  const askingRef = useRef(false);
  const cacheKey = chatCacheKey(userId, knowledgeBaseId);
  const storage = getChatStorage();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string>();
  const [draft, setDraft] = useState("");
  const [stage, setStage] = useState("");
  const [asking, setAsking] = useState(false);
  const [chatError, setChatError] = useState("");

  const { data: knowledgeBases = [] } = useQuery<KnowledgeBase[]>({
    queryKey: ["knowledge-bases"],
    queryFn: async () => (await apiFetch("/api/knowledge-bases")).json(),
  });
  const { data: documents = [] } = useQuery<DocumentItem[]>({
    queryKey: ["documents", knowledgeBaseId],
    queryFn: async () => (await apiFetch(`/api/knowledge-bases/${knowledgeBaseId}/documents`)).json(),
    refetchInterval: (query) =>
      (query.state.data as DocumentItem[] | undefined)?.some((item) => item.status === "uploaded" || item.status === "processing") ? 2000 : false,
  });
  const upload = useMutation({
    mutationFn: async (file: File) => {
      const body = new FormData();
      body.set("file", file);
      return apiFetch(`/api/knowledge-bases/${knowledgeBaseId}/documents`, { method: "POST", body });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents", knowledgeBaseId] }),
  });
  const remove = useMutation({
    mutationFn: (id: string) => apiFetch(`/api/documents/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents", knowledgeBaseId] }),
  });

  const current = knowledgeBases.find((item) => item.id === knowledgeBaseId);

  useEffect(() => {
    const cached = readChatCache(storage, cacheKey);
    if (!cached) return;
    setMessages(cached.messages);
    setConversationId(cached.conversationId);
  }, [cacheKey, storage]);

  useEffect(() => () => abortRef.current?.abort(), []);

  async function openCitation(citation: Citation) {
    const response = await apiFetch(`/api/documents/${citation.document_id}/content`);
    const url = URL.createObjectURL(await response.blob());
    window.open(`${url}${citation.page ? `#page=${citation.page}` : ""}`, "_blank", "noopener,noreferrer");
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  }

  async function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const question = draft.trim();
    if (!question || askingRef.current) return;
    askingRef.current = true;
    setDraft("");
    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: "user", content: question };
    const answerId = crypto.randomUUID();
    const sentMessages = [...messages, userMessage];
    setMessages([...sentMessages, { id: answerId, role: "assistant", content: "", citations: [] }]);
    writeChatCache(storage, cacheKey, sentMessages, conversationId);
    setAsking(true);
    setChatError("");
    const controller = new AbortController();
    abortRef.current = controller;
    let activeConversationId = conversationId;
    let answer = "";
    let citations: Citation[] = [];
    let completed = false;
    try {
      const response = await apiFetch("/api/chat", {
        method: "POST",
        signal: controller.signal,
        body: JSON.stringify({
          conversation_id: conversationId,
          knowledge_base_id: knowledgeBaseId,
          message: question,
        }),
      });
      if (!response.body) throw new Error("Streaming is unavailable");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";
        for (const frame of frames) {
          const eventName = frame.match(/^event: (.+)$/m)?.[1];
          const payload = JSON.parse(frame.match(/^data: (.+)$/m)?.[1] ?? "{}");
          if (eventName === "conversation") {
            activeConversationId = payload.conversation_id;
            setConversationId(activeConversationId);
            writeChatCache(storage, cacheKey, sentMessages, activeConversationId);
          }
          if (eventName === "status") setStage(stages[payload.stage] ?? payload.stage);
          if (eventName === "citation") {
            citations = [...citations, payload];
            setMessages((items) => items.map((item) => item.id === answerId ? { ...item, citations } : item));
          }
          if (eventName === "token") {
            answer += payload.text;
            setMessages((items) => items.map((item) => item.id === answerId ? { ...item, content: answer } : item));
          }
          if (eventName === "done") {
            activeConversationId = payload.conversation_id;
            const completedMessages = [...sentMessages, { id: answerId, role: "assistant" as const, content: answer, citations }];
            completed = true;
            setConversationId(activeConversationId);
            setMessages(completedMessages);
            writeChatCache(storage, cacheKey, completedMessages, activeConversationId);
          }
          if (eventName === "error") throw new Error(payload.message);
        }
        if (done) break;
      }
      if (!completed) throw new Error("Connection closed before the answer completed");
    } catch (error) {
      setMessages(sentMessages);
      writeChatCache(storage, cacheKey, sentMessages, activeConversationId);
      if (!(error instanceof DOMException && error.name === "AbortError")) {
        setChatError(error instanceof Error ? error.message : "Unable to answer");
      }
    } finally {
      askingRef.current = false;
      abortRef.current = null;
      setAsking(false);
      setStage("");
    }
  }

  function startNewConversation() {
    if (askingRef.current) return;
    setMessages([]);
    setConversationId(undefined);
    setDraft("");
    setChatError("");
    clearChatCache(storage, cacheKey);
  }

  const canSend = draft.trim().length > 0 && !asking;

  return (
    <main className="workspace-shell">
      <aside className="document-rail">
        <div className="rail-head">
          <Link href="/" aria-label="Back to library"><ArrowLeft size={18} /></Link>
          <div><p>KNOWLEDGE BASE</p><h1>{current?.name ?? "Loading…"}</h1></div>
        </div>
        <button className="upload-zone" onClick={() => inputRef.current?.click()} disabled={upload.isPending}>
          <UploadCloud size={23} />
          <strong>{upload.isPending ? "Uploading…" : "Add source"}</strong>
          <span>PDF, DOCX, Markdown or TXT · 25 MB max</span>
        </button>
        <input
          ref={inputRef}
          hidden
          type="file"
          accept=".pdf,.docx,.md,.markdown,.txt"
          onChange={(event) => event.target.files?.[0] && upload.mutate(event.target.files[0])}
        />
        <div className="source-title"><span>Sources</span><small>{documents.length}</small></div>
        <div className="document-list">
          {documents.map((document) => (
            <div className="document-row" key={document.id}>
              <div className="file-icon"><FileText size={18} /></div>
              <div><strong title={document.filename}>{document.filename}</strong><span className={`status ${document.status}`}>
                {document.status === "ready" ? <Check size={11} /> : document.status === "processing" || document.status === "uploaded" ? <LoaderCircle className="spin" size={11} /> : null}
                {document.status}
              </span></div>
              <button aria-label={`Delete ${document.filename}`} onClick={() => remove.mutate(document.id)}><Trash2 size={15} /></button>
            </div>
          ))}
          {!documents.length && <p className="empty-sources">Your source list is empty.<br />Add one document to begin.</p>}
        </div>
        <p className="rail-foot"><Sparkles size={14} /> Agentic search chooses when retrieval is needed.</p>
      </aside>
      <section className="chat-room">
        <header className="chat-head">
          <div className="live-dot" /><span>Grounded assistant</span><small>Sources only</small>
          <button className="new-chat" type="button" onClick={startNewConversation} disabled={asking} aria-label="New conversation" title="New conversation"><MessageSquarePlus size={16} /></button>
        </header>
        <div className="messages">
          {!messages.length && (
            <div className="chat-welcome">
              <span className="spark-orbit"><Sparkles size={28} /></span>
              <p className="eyebrow">READY WHEN YOU ARE</p>
              <h2>Ask the archive,<br />not the internet.</h2>
              <p>I’ll decide whether retrieval is necessary, search the strongest passages, and keep every citation attached.</p>
              <div className="suggestions">
                {["Summarize the main ideas", "What claims need evidence?", "Compare the uploaded sources"].map((text) => (
                  <button key={text} onClick={() => {
                    setDraft(text);
                    messageRef.current?.focus();
                  }}>{text}</button>
                ))}
              </div>
            </div>
          )}
          {messages.map((message) => (
            <article key={message.id} className={`message ${message.role}`}>
              <div className="message-label">{message.role === "user" ? "YOU" : "FIELDNOTE"}</div>
              <div className="message-body">{message.content || <span className="typing"><i /><i /><i /></span>}</div>
              {!!message.citations?.length && (
                <div className="citations">
                  {message.citations.map((citation, index) => (
                    <button key={citation.chunk_id} onClick={() => openCitation(citation)}><Paperclip size={13} /> {index + 1} · {citation.filename}{citation.page ? ` · p.${citation.page}` : ""}</button>
                  ))}
                </div>
              )}
            </article>
          ))}
          {stage && <div className="agent-stage"><LoaderCircle className="spin" size={14} /> {stage}</div>}
          {chatError && <p className="error-note">{chatError}</p>}
        </div>
        <form className="composer" onSubmit={ask}>
          <textarea
            ref={messageRef}
            name="message"
            rows={2}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              const action = chatKeyAction({ key: event.key, shiftKey: event.shiftKey, isComposing: event.nativeEvent.isComposing }, canSend);
              if (action === "default") return;
              event.preventDefault();
              if (action === "submit") event.currentTarget.form?.requestSubmit();
            }}
            placeholder={documents.some((item) => item.status === "ready") ? "Ask a question about your sources…" : "Upload a source, or say hello…"}
            aria-label="Message"
          />
          <Button type="submit" size="icon" disabled={!canSend} aria-label="Send message"><ArrowUp size={18} /></Button>
          <span>Shift + Enter for a new line</span>
        </form>
      </section>
    </main>
  );
}
