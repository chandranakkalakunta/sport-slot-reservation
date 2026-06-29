/**
 * Flat inline SVG wordmark for use in footers and small co-branding contexts.
 * Crisp at 13–20px. No gradients or raster — do not shrink the raster icon here.
 */
export function SlotSenseWordmark({ className }: { className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium${className ? ` ${className}` : ""}`}
    >
      {/* Navy rounded square with flat white "SS" glyph */}
      <svg
        width="18"
        height="18"
        viewBox="0 0 18 18"
        fill="none"
        aria-hidden="true"
        focusable="false"
      >
        <rect width="18" height="18" rx="3" fill="#1a4d8f" />
        <text
          x="9"
          y="13"
          textAnchor="middle"
          fill="white"
          fontSize="9"
          fontWeight="700"
          fontFamily="system-ui,sans-serif"
        >
          SS
        </text>
      </svg>
      <span>SlotSense</span>
    </span>
  );
}
