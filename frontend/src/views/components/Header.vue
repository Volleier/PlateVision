<template>
    <header class="app-header">
        <div class="header-inner container">
            <h1 class="title">PlateVision</h1>

            <!-- Split-action buttons -->
            <nav class="split-actions" role="navigation" aria-label="header actions">
                <router-link to="/upload" class="split-half" :class="{ active: $route.path === '/upload' }"
                    :aria-current="$route.path === '/upload' ? 'page' : null">
                    <span class="label">Upload</span>
                </router-link>

                <router-link to="/check" class="split-half" :class="{ active: $route.path === '/check' }"
                    :aria-current="$route.path === '/check' ? 'page' : null">
                    <span class="label">Check</span>
                </router-link>
            </nav>
        </div>
    </header>
</template>

<script lang="ts">
import { onMounted, onUnmounted } from 'vue';

export default {
    name: 'AppHeader',
    setup() {
        const resizeHandler = () => {
            const app = document.getElementById('app');
            const header = document.querySelector('.app-header') as HTMLElement | null;
            if (app && header) {
                app.style.paddingTop = `${header.offsetHeight}px`;
            }
        };

        onMounted(() => {
            // Initialize and attach listener
            resizeHandler();
            window.addEventListener('resize', resizeHandler);
        });
        onUnmounted(() => {
            // Clean up and restore (optional)
            const app = document.getElementById('app');
            if (app) app.style.paddingTop = '';
            window.removeEventListener('resize', resizeHandler);
        });
    },
};
</script>

<style lang="scss" scoped src="../../assets/styles/Header.scss"></style>
