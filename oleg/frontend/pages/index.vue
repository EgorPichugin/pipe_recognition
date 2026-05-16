<script setup lang="ts">
const outputRefreshKey = ref(0)

function onGenerated() {
  outputRefreshKey.value += 1
  nextTick(() => {
    const el = document.getElementById('output')
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}
</script>

<template>
  <div>
    <SiteNav />
    <main>
      <HeroSection />
      <ArchitectureSection />
      <MetricsSection />
      <InputSection @generated="onGenerated" />
      <HistorySection />
      <OutputSection :refresh-key="outputRefreshKey" />
    </main>
    <SiteFooter />
  </div>
</template>
