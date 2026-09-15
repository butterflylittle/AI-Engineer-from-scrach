import { Suspense } from "react";

import { AuthForm } from "@/features/auth/auth-form";

export default function ResetPasswordPage() {
  return <Suspense><AuthForm mode="reset" /></Suspense>;
}
