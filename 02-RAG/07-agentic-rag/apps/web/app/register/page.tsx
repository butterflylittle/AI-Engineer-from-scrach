import { Suspense } from "react";

import { AuthForm } from "@/features/auth/auth-form";

export default function RegisterPage() {
  const googleEnabled = Boolean(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET);
  const emailDeliveryConfigured = Boolean(process.env.RESEND_API_KEY && process.env.EMAIL_FROM);
  return <Suspense><AuthForm mode="register" googleEnabled={googleEnabled} emailDeliveryConfigured={emailDeliveryConfigured} /></Suspense>;
}
