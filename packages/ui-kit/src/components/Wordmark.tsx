/** Education OS brand: the mark (a cap over an open book) and the EDUCATION OS wordmark. */

export function EduMark({ size = 36 }: { size?: number }) {
  return (
    <span className="eos-mark" style={{ width: size, height: size }} aria-hidden>
      <svg viewBox="0 0 48 48" fill="none">
        <path d="M24 8 4 17l20 9 20-9z" fill="#2d3fa3" />
        <path d="M12 22v8c0 3.5 5.4 6 12 6s12-2.5 12-6v-8l-12 5.4z" fill="#f28d1e" />
        <path d="M40 17v11" stroke="#f04e3e" strokeWidth="2.5" strokeLinecap="round" />
        <path d="M8 36c4-2 8-2 12 0 4-2 8-2 12 0 4-2 8-2 12 0v4c-4-2-8-2-12 0-4-2-8-2-12 0-4-2-8-2-12 0z" fill="#2ba66b" />
      </svg>
    </span>
  );
}

export function Wordmark({ inverse = false, size = 17 }: { inverse?: boolean; size?: number }) {
  return (
    <span className={inverse ? "eos-wordmark eos-wordmark--inverse" : "eos-wordmark"} style={{ fontSize: size }} aria-label="Education OS">
      <span className="eos-wordmark__name">Education</span>
      <span className="eos-wordmark__os">OS</span>
    </span>
  );
}
