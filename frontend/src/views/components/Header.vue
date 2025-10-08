<template>
    <header class="app-header">
        <div class="header-inner container">
            <h1 class="title">PlateVision</h1>

            <div class="actions">
                <button class="btn" @click="$emit('upload')">Upload</button>
                <button class="btn" @click="$emit('check')">Check</button>
            </div>
        </div>
    </header>
</template>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
    name: 'AppHeader',
    emits: ['upload', 'check']
})
</script>

<style lang="scss" scoped>
.app-header {
    padding: 1.5rem 0;
    background: #fff;
    border-bottom: 1px solid #e6e6e6;

    .header-inner {
        text-align: center;
    }

    .title {
        margin: 0;
        font-size: 1.5rem;
        font-weight: 600;
    }

    .actions {
        margin-top: 0.75rem;
        display: flex;
        gap: 0.5rem;
        justify-content: center;

        .btn {
            padding: 0.5rem 1rem;
            border-radius: 4px;
            border: 1px solid #cfcfcf;
            background: #f7f7f7;
            cursor: pointer;
            transition: background .12s ease;

            &:hover {
                background: #efefef;
            }
        }
    }
}
</style>