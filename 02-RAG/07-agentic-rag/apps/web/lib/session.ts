import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { auth } from "@/lib/auth";

export async function requireSession() {
  if (process.env.AUTH_DISABLED === "true") {
    return { user: { name: "Demo user" } };
  }
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) redirect("/login");
  return session;
}
