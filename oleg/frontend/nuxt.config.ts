export default defineNuxtConfig({
  compatibilityDate: '2026-05-15',
  devtools: { enabled: false },
  modules: ['@nuxtjs/tailwindcss'],
  css: ['~/assets/css/main.css'],
  app: {
    head: {
      title: 'Inspection AI — Hackathon Vienna',
      meta: [
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        { name: 'description', content: 'AI-powered inspection report generator. Vienna Hackathon 2026.' },
        { name: 'color-scheme', content: 'dark' },
      ],
      link: [
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
        {
          rel: 'stylesheet',
          href: 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap',
        },
      ],
      htmlAttrs: { class: 'dark' },
    },
  },
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || '',
    },
  },
  nitro: {
    devProxy: {
      '/report': {
        target: 'http://127.0.0.1:8000/report',
        changeOrigin: true,
        prependPath: true,
      },
    },
  },
})
