<template>
	<section class="home-root container">
		<h1 class="home-title">PlateVision</h1>

		<div class="actions" role="navigation" aria-label="home actions">
			<router-link to="/upload" class="btn primary" aria-label="Upload">Upload</router-link>
			<router-link to="/check" class="btn secondary" aria-label="Check">Check</router-link>
		</div>
	</section>
</template>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
	name: 'Home'
})
</script>

<style lang="scss" scoped src="../assets/styles/Home.scss"></style>
