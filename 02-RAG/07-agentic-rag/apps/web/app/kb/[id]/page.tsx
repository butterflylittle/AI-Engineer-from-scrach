import { KnowledgeWorkspace } from "@/features/knowledge-base/workspace";
import { requireSession } from "@/lib/session";

export default async function KnowledgeBasePage({ params }: { params: Promise<{ id: string }> }) {
  await requireSession();
  const { id } = await params;
  return <KnowledgeWorkspace knowledgeBaseId={id} />;
}
