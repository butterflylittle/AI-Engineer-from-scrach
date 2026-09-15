"use client";

import { createAuthClient } from "better-auth/react";
import { jwtClient } from "better-auth/client/plugins";

export const authClient = createAuthClient({ plugins: [jwtClient()] });

export async function accessToken() {
  const { data, error } = await authClient.token();
  if (error || !data?.token) throw new Error("Unable to create API token");
  return data.token;
}
