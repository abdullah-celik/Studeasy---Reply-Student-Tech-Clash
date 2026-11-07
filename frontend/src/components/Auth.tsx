import { useState } from "react";
import { supabase } from "../api/client";

export function Auth() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(mode: "in" | "up") {
    setBusy(true);
    setMsg(null);
    const { error } =
      mode === "in"
        ? await supabase.auth.signInWithPassword({ email, password })
        : await supabase.auth.signUp({ email, password });
    setBusy(false);
    if (error) setMsg(error.message);
    else if (mode === "up") setMsg("Signed up. Check your email if confirmation is enabled, then sign in.");
  }

  return (
    <div className="card narrow">
      <h1>Studeasy</h1>
      <p className="muted">Sign in with your Supabase account.</p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit("in");
        }}
      >
        <input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <div className="row">
          <button type="submit" disabled={busy}>Sign in</button>
          <button type="button" className="secondary" disabled={busy} onClick={() => submit("up")}>
            Sign up
          </button>
        </div>
      </form>
      {msg && <p className="notice">{msg}</p>}
    </div>
  );
}
