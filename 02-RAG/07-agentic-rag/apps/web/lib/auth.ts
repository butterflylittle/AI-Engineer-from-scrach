import { betterAuth } from "better-auth";
import { jwt } from "better-auth/plugins";
import { Pool } from "pg";

async function sendEmail(to: string, subject: string, url: string) {
  if (!process.env.RESEND_API_KEY) {
    console.warn(`Email delivery skipped for ${subject}; configure RESEND_API_KEY.`);
    return;
  }
  const response = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.RESEND_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from: process.env.EMAIL_FROM,
      to,
      subject,
      html: `<p>${subject}</p><p><a href="${url}">Continue securely</a></p>`,
    }),
  });
  if (!response.ok) throw new Error("Email delivery failed");
}

const google =
  process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET
    ? {
        google: {
          clientId: process.env.GOOGLE_CLIENT_ID,
          clientSecret: process.env.GOOGLE_CLIENT_SECRET,
          scope: ["openid", "email", "profile"],
        },
      }
    : {};

export const auth = betterAuth({
  baseURL: process.env.BETTER_AUTH_URL,
  secret: process.env.BETTER_AUTH_SECRET,
  database: new Pool({ connectionString: process.env.BETTER_AUTH_DATABASE_URL }),
  emailAndPassword: {
    enabled: true,
    requireEmailVerification: true,
    sendResetPassword: async ({ user, url }) =>
      sendEmail(user.email, "Reset your Agentic RAG password", url),
  },
  emailVerification: {
    sendOnSignUp: true,
    sendVerificationEmail: async ({ user, url }) =>
      sendEmail(user.email, "Verify your Agentic RAG email", url),
  },
  socialProviders: google,
  rateLimit: { enabled: true, window: 60, max: 20 },
  advanced: {
    database: { joins: true, generateId: "uuid" },
    useSecureCookies: process.env.BETTER_AUTH_URL?.startsWith("https://") ?? false,
  },
  plugins: [
    jwt({
      jwks: { keyPairConfig: { alg: "RS256", modulusLength: 2048 } },
      jwt: {
        issuer: process.env.AUTH_JWT_ISSUER,
        audience: process.env.AUTH_JWT_AUDIENCE,
        expirationTime: "15m",
        definePayload: ({ user }) => ({ sub: user.id, email: user.email }),
      },
    }),
  ],
});
