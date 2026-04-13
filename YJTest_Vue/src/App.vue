<template>
  <router-view />
</template>

<script setup lang="ts">
import { onMounted, watch } from 'vue';
import { useRoute } from 'vue-router';
import { useAuthStore } from '@/store/authStore';
import { buildDocumentTitle } from '@/config/brand';

const authStore = useAuthStore();
const route = useRoute();

watch(
  () => route.name,
  (routeName) => {
    document.title = buildDocumentTitle(routeName);
  },
  { immediate: true }
);

onMounted(() => {
  authStore.checkAuthStatus();
});
</script>

<style>
#app {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: var(--theme-page-text);
  min-height: 100vh;
}

body,
html {
  margin: 0;
  padding: 0;
  height: 100%;
}
</style>
