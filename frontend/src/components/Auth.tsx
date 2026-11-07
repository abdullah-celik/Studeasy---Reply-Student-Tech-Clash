import { useState } from "react";
import { supabase } from "../api/client";
import { LEGAL_VERSION, type LegalDoc } from "../lib/legal";
import { LegalDialog, LegalLinks } from "./Legal";
import { Logo } from "./Logo";
import { PasswordInput } from "./PasswordInput";

type Mode = "in" | "up";

export function Auth() {
  const [mode, setMode] = useState<Mode>("in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [msg, setMsg] = useState<{ kind: "error" | "notice"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [legal, setLegal] = useState<LegalDoc | null>(null);

  function switchMode(m: Mode) {
    setMode(m);
    setMsg(null);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (mode === "up" && !agreed) {
      setMsg({ kind: "error", text: "Please accept the Terms of Use and Privacy Policy to create an account." });
      return;
    }
    setBusy(true);
    setMsg(null);
    const { error } =
      mode === "in"
        ? await supabase.auth.signInWithPassword({ email, password })
        : await supabase.auth.signUp({
            email,
            password,
            // Record which version of the terms was accepted, and when.
            options: { data: { terms_version: LEGAL_VERSION, terms_accepted_at: new Date().toISOString() } },
          });
    setBusy(false);
    if (error) setMsg({ kind: "error", text: error.message });
    else if (mode === "up") {
      setMsg({ kind: "notice", text: "Account created. Check your inbox to confirm your email if asked, then sign in." });
      setMode("in");
    }
  }

  return (
    <div className="card narrow auth">
      <Logo size={96} className="auth-logo" />
      <h1>Studeasy</h1>
      <p className="muted">Your notes, turned into a study buddy.</p>

      <div className="segmented auth-tabs" role="tablist" aria-label="Sign in or create an account">
        <button role="tab" type="button" aria-selected={mode === "in"} className={mode === "in" ? "on" : ""} onClick={() => switchMode("in")}>
          Sign in
        </button>
        <button role="tab" type="button" aria-selected={mode === "up"} className={mode === "up" ? "on" : ""} onClick={() => switchMode("up")}>
          Create account
        </button>
      </div>

      <form onSubmit={submit}>
        <input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
        <PasswordInput
          value={password}
          onChange={setPassword}
          placeholder={mode === "up" ? "Password (min. 6 characters)" : "Password"}
          autoComplete={mode === "up" ? "new-password" : "current-password"}
          minLength={mode === "up" ? 6 : undefined}
        />

        {mode === "up" && (
          <label className="consent">
            <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} required />
            <span>
              I have read and agree to the{" "}
              <button type="button" className="link" onClick={() => setLegal("terms")}>Terms of Use</button> and the{" "}
              <button type="button" className="link" onClick={() => setLegal("privacy")}>Privacy Policy</button>, including that my
              material is processed by AI services.
            </span>
          </label>
        )}

        <button type="submit" disabled={busy || (mode === "up" && !agreed)}>
          {busy ? "Please wait…" : mode === "in" ? "Sign in" : "Create account"}
        </button>
      </form>

      {msg && <p className={msg.kind}>{msg.text}</p>}

      {mode === "in" && (
        <p className="muted small legal-note">
          <LegalLinks open={setLegal} sep=" and ">By signing in you agree to our </LegalLinks>.
        </p>
      )}

      <LegalDialog doc={legal} onClose={() => setLegal(null)} />
    </div>
  );
}
