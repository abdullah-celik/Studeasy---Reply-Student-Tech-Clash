import { useState } from "react";
import { PixelIcon } from "./PixelIcon";

/** Password field with a show/hide eye button. */
export function PasswordInput({
  value,
  onChange,
  placeholder = "Password",
  autoComplete,
  minLength,
  id,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  autoComplete?: string;
  minLength?: number;
  id?: string;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="password">
      <input
        id={id}
        type={visible ? "text" : "password"}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        minLength={minLength}
        required
        spellCheck={false}
        autoCapitalize="off"
      />
      <button
        type="button"
        className="mini eye"
        aria-label={visible ? "Hide password" : "Show password"}
        aria-pressed={visible}
        title={visible ? "Hide password" : "Show password"}
        onClick={() => setVisible((v) => !v)}
      >
        <PixelIcon name={visible ? "eyeOff" : "eye"} size={16} />
      </button>
    </div>
  );
}
