"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, BookOpen, Library, LogOut, Plus, Search, Settings2 } from "lucide-react";
import Link from "next/link";
import { FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiFetch } from "@/lib/api";
import { authClient } from "@/lib/auth-client";
import type { KnowledgeBase } from "@/types";

export function Dashboard({ userName }: { userName: string }) {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [search, setSearch] = useState("");
  const { data = [], isLoading, error } = useQuery<KnowledgeBase[]>({
    queryKey: ["knowledge-bases"],
    queryFn: async () => (await apiFetch("/api/knowledge-bases")).json(),
  });
  const create = useMutation({
    mutationFn: async (payload: { name: string; description: string }) =>
      (await apiFetch("/api/knowledge-bases", { method: "POST", body: JSON.stringify(payload) })).json(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] });
      setCreating(false);
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    create.mutate({ name: String(form.get("name")), description: String(form.get("description")) });
  }

  const filtered = data.filter((item) => `${item.name} ${item.description}`.toLowerCase().includes(search.toLowerCase()));
  return (
    <main className="app-frame">
      <aside className="sidebar">
        <Link href="/" className="brand-mark"><span>●</span> FIELDNOTE</Link>
        <nav>
          <Link className="nav-item active" href="/"><Library size={17} /> Library</Link>
          <span className="nav-item"><BookOpen size={17} /> Conversations</span>
          <span className="nav-item"><Settings2 size={17} /> Settings</span>
        </nav>
        <div className="sidebar-foot">
          <div className="avatar">{userName.slice(0, 1).toUpperCase()}</div>
          <div><strong>{userName}</strong><small>Private workspace</small></div>
          <button aria-label="Sign out" onClick={() => authClient.signOut({ fetchOptions: { onSuccess: () => location.assign("/login") } })}><LogOut size={16} /></button>
        </div>
      </aside>
      <section className="content-shell">
        <header className="topbar">
          <div><p className="eyebrow">YOUR LIBRARY</p><h1>Knowledge bases</h1></div>
          <Button onClick={() => setCreating(true)}><Plus size={17} /> New knowledge base</Button>
        </header>
        <div className="library-tools">
          <Search size={17} />
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search your library" aria-label="Search knowledge bases" />
          <span>{filtered.length} collections</span>
        </div>
        {creating && (
          <Card className="create-card">
            <form onSubmit={submit}>
              <Input name="name" placeholder="Collection name" required autoFocus />
              <Input name="description" placeholder="What belongs here?" />
              <Button type="button" variant="ghost" onClick={() => setCreating(false)}>Cancel</Button>
              <Button disabled={create.isPending}>Create</Button>
            </form>
          </Card>
        )}
        {error && <p className="error-note">{error.message}</p>}
        <div className="kb-grid">
          {isLoading && [1, 2, 3].map((item) => <div key={item} className="kb-skeleton" />)}
          {filtered.map((item, index) => (
            <Link href={`/kb/${item.id}`} key={item.id} className="kb-card" style={{ animationDelay: `${index * 70}ms` }}>
              <div className="kb-index">{String(index + 1).padStart(2, "0")}</div>
              <div><p>COLLECTION</p><h2>{item.name}</h2><span>{item.description || "A focused space for trusted source material."}</span></div>
              <ArrowUpRight size={19} />
            </Link>
          ))}
          {!isLoading && !filtered.length && (
            <button className="empty-library" onClick={() => setCreating(true)}>
              <Plus size={22} /><strong>Create your first knowledge base</strong><span>Upload a document and ask a sourced question.</span>
            </button>
          )}
        </div>
      </section>
    </main>
  );
}
