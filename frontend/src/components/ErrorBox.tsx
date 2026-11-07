import { errorMessage } from "../api/client";

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  return <p className="error">{errorMessage(error)}</p>;
}
