import { Dashboard } from "@/features/knowledge-base/dashboard";
import { requireSession } from "@/lib/session";

export default async function HomePage() {
  const session = await requireSession();
  return <Dashboard userName={session.user.name} />;
}
