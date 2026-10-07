/** The logo mark (same drawing as public/favicon.svg) plus the name. */
export function Logo({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 512 512" aria-hidden>
      <defs>
        <linearGradient id="logo-bg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#151a2b" />
          <stop offset="1" stopColor="#07090f" />
        </linearGradient>
        <linearGradient id="logo-hl" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#ff6a88" />
          <stop offset="1" stopColor="#ffb35c" />
        </linearGradient>
      </defs>
      <rect width="512" height="512" rx="116" fill="url(#logo-bg)" />
      <rect x="146" y="150" width="220" height="40" rx="20" fill="#fff" opacity="0.28" />
      <rect x="96" y="236" width="320" height="52" rx="26" fill="url(#logo-hl)" />
      <rect x="166" y="334" width="180" height="40" rx="20" fill="#fff" opacity="0.28" />
    </svg>
  );
}

export function Brand() {
  return (
    <a href="/" className="brand">
      <Logo />
      <span>DriveLyrics</span>
    </a>
  );
}
