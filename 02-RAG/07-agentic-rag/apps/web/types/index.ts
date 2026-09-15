export type KnowledgeBase = {
  id: string;
  name: string;
  description: string;
  created_at: string;
};

export type DocumentItem = {
  id: string;
  knowledge_base_id: string;
  filename: string;
  mime_type: string;
  size: number;
  status: "uploaded" | "processing" | "ready" | "failed";
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type Citation = {
  document_id: string;
  chunk_id: string;
  filename: string;
  page: number | null;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
};
