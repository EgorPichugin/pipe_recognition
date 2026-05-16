<template>
  <div class="flex w-12 shrink-0 items-stretch justify-center">
    <svg viewBox="0 0 48 200" preserveAspectRatio="none" class="h-full w-full" aria-hidden="true">
      <defs>
        <linearGradient id="fan-grad" x1="0" x2="1">
          <stop offset="0" stop-color="#A855F7" stop-opacity="0.4" />
          <stop offset="1" stop-color="#A855F7" stop-opacity="0.9" />
        </linearGradient>
      </defs>
      <!-- single point on left → 3 endpoints on right -->
      <path d="M 0 100 C 24 100, 24 30, 44 30" fill="none" stroke="url(#fan-grad)" stroke-width="1.5" />
      <path d="M 0 100 L 44 100" fill="none" stroke="url(#fan-grad)" stroke-width="1.5" />
      <path d="M 0 100 C 24 100, 24 170, 44 170" fill="none" stroke="url(#fan-grad)" stroke-width="1.5" />
      <circle cx="44" cy="30" r="2" fill="#A855F7" />
      <circle cx="44" cy="100" r="2" fill="#A855F7" />
      <circle cx="44" cy="170" r="2" fill="#A855F7" />
    </svg>
  </div>
</template>
