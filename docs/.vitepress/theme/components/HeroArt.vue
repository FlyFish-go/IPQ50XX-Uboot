<template>
  <div class="art" aria-hidden="true">
    <svg viewBox="0 0 360 330" role="img">
      <defs>
        <linearGradient id="ha-brand" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="var(--vp-c-brand-1)" />
          <stop offset="1" stop-color="var(--art-accent)" />
        </linearGradient>
      </defs>

      <!-- SBL -->
      <rect x="70" y="14" width="220" height="44" rx="12" class="box" />
      <text x="180" y="41" class="t-muted" text-anchor="middle">高通启动链 SBL</text>

      <path d="M180 58 V96" class="flow" />

      <!-- our U-Boot -->
      <rect x="30" y="98" width="300" height="86" rx="16" fill="url(#ha-brand)" class="hero-box" />
      <text x="180" y="134" class="t-hero" text-anchor="middle">IPQ50XX-Uboot</text>
      <g class="pills">
        <rect x="52" y="148" width="76" height="22" rx="11" />
        <rect x="142" y="148" width="76" height="22" rx="11" />
        <rect x="232" y="148" width="76" height="22" rx="11" />
      </g>
      <text x="90" y="163" class="t-pill" text-anchor="middle">网页救砖</text>
      <text x="180" y="163" class="t-pill" text-anchor="middle">双系统</text>
      <text x="270" y="163" class="t-pill" text-anchor="middle">写入核对</text>

      <path d="M120 184 C120 214 95 214 95 240" class="flow" />
      <path d="M240 184 C240 214 265 214 265 240" class="flow flow--b" />

      <!-- slots -->
      <rect x="22" y="242" width="146" height="64" rx="14" class="box box--slot" />
      <text x="95" y="270" class="t-slot" text-anchor="middle">系统 A</text>
      <text x="95" y="290" class="t-muted t-sm" text-anchor="middle">原厂固件</text>

      <rect x="192" y="242" width="146" height="64" rx="14" class="box box--slot" />
      <text x="265" y="270" class="t-slot" text-anchor="middle">系统 B</text>
      <text x="265" y="290" class="t-muted t-sm" text-anchor="middle">OpenWrt / 第三方</text>
    </svg>
  </div>
</template>

<style scoped>
.art {
  --art-accent: #22c55e;
  position: relative; width: 100%; max-width: 380px; margin: 0 auto;
}
.art::before {
  content: ''; position: absolute; inset: 12% 8%; z-index: -1; border-radius: 50%;
  background: radial-gradient(closest-side, var(--vp-c-brand-soft), transparent);
  filter: blur(24px);
}
svg { width: 100%; height: auto; display: block; overflow: visible; }
.box { fill: var(--vp-c-bg-soft); stroke: var(--vp-c-divider); stroke-width: 1.5; }
.box--slot { fill: var(--vp-c-bg); stroke: var(--vp-c-brand-2); stroke-opacity: .45; }
.hero-box { filter: drop-shadow(0 10px 24px rgba(15, 118, 110, .28)); }
.pills rect { fill: rgba(255, 255, 255, .2); }
.t-hero { font-size: 24px; font-weight: 800; fill: #fff; letter-spacing: -0.01em; }
.t-pill { font-size: 12px; font-weight: 600; fill: #fff; }
.t-slot { font-size: 17px; font-weight: 700; fill: var(--vp-c-text-1); }
.t-muted { font-size: 14px; fill: var(--vp-c-text-2); }
.t-sm { font-size: 12px; }
.flow {
  fill: none; stroke: var(--vp-c-brand-2); stroke-width: 2.5; stroke-linecap: round;
  stroke-dasharray: 2 8; animation: flow 1.2s linear infinite;
}
.flow--b { animation-delay: -.6s; }
@keyframes flow { to { stroke-dashoffset: -20; } }
@media (prefers-reduced-motion: reduce) { .flow { animation: none; } }
@media (max-width: 959px) { .art { max-width: 320px; margin-top: 24px; } }
</style>
