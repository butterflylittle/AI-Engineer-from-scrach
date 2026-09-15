"use client";

import { ArrowRight, KeyRound, Mail } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { authClient } from "@/lib/auth-client";

type Mode = "login" | "register" | "forgot" | "reset";

const copy = {
  login: ["Welcome back", "Open your private research room."],
  register: ["Create your archive", "A quiet place for your team knowledge."],
  forgot: ["Reset access", "We’ll send a secure reset link."],
  reset: ["Choose a new password", "Use at least eight characters."],
} as const;

export function AuthForm({
  mode,
  googleEnabled = false,
  emailDeliveryConfigured = false,
}: {
  mode: Mode;
  googleEnabled?: boolean;
  emailDeliveryConfigured?: boolean;
}) {
  const router = useRouter();
  const params = useSearchParams();
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [emailAddress, setEmailAddress] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setMessage("");
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "");
    const password = String(form.get("password") ?? "");
    try {
      if (mode === "login") {
        const result = await authClient.signIn.email({ email, password });
        if (result.error) throw new Error(result.error.message);
        router.push("/");
      } else if (mode === "register") {
        if (password !== form.get("confirm")) throw new Error("Passwords do not match");
        const result = await authClient.signUp.email({
          name: String(form.get("name") ?? ""),
          email,
          password,
          callbackURL: "/",
        });
        if (result.error) throw new Error(result.error.message);
        setMessage(
          emailDeliveryConfigured
            ? "Check your inbox to verify your email."
            : "Account created, but email delivery is not configured yet.",
        );
      } else if (mode === "forgot") {
        const result = await authClient.requestPasswordReset({ email, redirectTo: "/reset-password" });
        if (result.error) throw new Error(result.error.message);
        setMessage("If that address exists, a reset link is on its way.");
      } else {
        const token = params.get("token");
        if (!token) throw new Error("This reset link is invalid");
        const result = await authClient.resetPassword({ newPassword: password, token });
        if (result.error) throw new Error(result.error.message);
        router.push("/login");
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Something went wrong");
    } finally {
      setPending(false);
    }
  }

  async function resendVerification() {
    if (!emailAddress) return;
    setPending(true);
    const result = await authClient.sendVerificationEmail({ email: emailAddress, callbackURL: "/" });
    setMessage(result.error?.message ?? "Verification email sent.");
    setPending(false);
  }

  const showEmail = mode !== "reset";
  const showPassword = mode !== "forgot";
  return (
    <main className="auth-shell">
      <section className="auth-story">
        <Link href="/" className="brand-mark"><span>●</span> FIELDNOTE</Link>
        <div>
          <p className="eyebrow">PRIVATE KNOWLEDGE, CLEAR ANSWERS</p>
          <h1>Turn the documents you trust into answers you can trace.</h1>
          <p className="story-copy">Every response keeps its source attached—file, page, and passage.</p>
        </div>
        <p className="fine-print">Encrypted sessions · Isolated workspaces · Verifiable citations</p>
      </section>
      <section className="auth-panel">
        <div className="auth-card">
          <div className="auth-icon">{mode === "forgot" || mode === "reset" ? <KeyRound size={20} /> : <Mail size={20} />}</div>
          <h2>{copy[mode][0]}</h2>
          <p>{copy[mode][1]}</p>
          {!emailDeliveryConfigured && (mode === "register" || mode === "forgot") && (
            <p className="form-message">Email delivery is unavailable until Resend is configured.</p>
          )}
          {(mode === "login" || mode === "register") && googleEnabled && (
            <>
              <Button className="mt-8 w-full" variant="outline" onClick={() => authClient.signIn.social({ provider: "google", callbackURL: "/" })}>
                Continue with Google
              </Button>
              <div className="divider"><span>or</span></div>
            </>
          )}
          <form onSubmit={submit} className="space-y-4">
            {mode === "register" && <Input name="name" placeholder="Name" autoComplete="name" required />}
            {showEmail && <Input name="email" type="email" placeholder="Email address" autoComplete="email" required onChange={(event) => setEmailAddress(event.target.value)} />}
            {showPassword && <Input name="password" type="password" placeholder="Password" minLength={8} autoComplete="current-password" required />}
            {mode === "register" && <Input name="confirm" type="password" placeholder="Confirm password" minLength={8} required />}
            <Button className="w-full" disabled={pending}>{pending ? "Please wait…" : copy[mode][0]} <ArrowRight size={16} /></Button>
          </form>
          {message && <p className="form-message" role="status">{message}</p>}
          {emailDeliveryConfigured && ((mode === "register" && message.startsWith("Check")) || (mode === "login" && emailAddress)) && (
            <Button
              className="mt-3 w-full"
              variant="ghost"
              disabled={pending}
              onClick={resendVerification}
            >
              Resend verification email
            </Button>
          )}
          <div className="auth-links">
            {mode === "login" && <><Link href="/forgot-password">Forgot password?</Link><Link href="/register">Create account</Link></>}
            {mode !== "login" && <Link href="/login">Back to sign in</Link>}
          </div>
        </div>
      </section>
    </main>
  );
}
