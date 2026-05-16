<template>
  <div class="flex w-12 shrink-0 items-stretch justify-center">
    <svg viewBox="0 0 48 200" preserveAspectRatio="none" class="h-full w-full" aria-hidden="true">
      <defs>
        <linearGradient id="fanin-grad" x1="0" x2="1">
          <stop offset="0" stop-color="#EC4899" stop-opacity="0.4" />
          <stop offset="1" stop-color="#EC4899" stop-opacity="0.9" />
        </linearGradient>
      </defs>
      <!-- 3 points on left → single point on right -->
      <path d="M 4 30 C 24 30, 24 100, 44 100" fill="none" stroke="url(#fanin-grad)" stroke-width="1.5" />
      <path d="M 4 100 L 44 100" fill="none" stroke="url(#fanin-grad)" stroke-width="1.5" />
      <path d="M 4 170 C 24 170, 24 100, 44 100" fill="none" stroke="url(#fanin-grad)" stroke-width="1.5" />
      <path d="M 38 96 L 44 100 L 38 104" fill="none" stroke="#EC4899" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  </div>
</template>
