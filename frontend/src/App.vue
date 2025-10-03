<template>
	<div id="app" class="app-root">
		<header class="app-header">
			<div class="container">
				<h1>PlateVision</h1>
			</div>
		</header>

		<main class="app-main container">
			<router-view />
		</main>

	</div>
</template>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
	name: 'App'
})
</script>

<style lang="scss" scoped src="./assets/styles/App.scss"></style>
