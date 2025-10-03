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

<style lang="scss" scoped>
.app-root {
	display: flex;
	flex-direction: column;
	min-height: 100vh;
}

.app-header {
	background: #2d6cdf;
	color: #fff;
	padding: 1rem 0;
}

.container {
	width: 100%;
	max-width: 1100px;
	margin: 0 auto;
	padding: 0 1rem;
}

.logo {
	margin: 0;
}

.app-main {
	flex: 1 0 auto;
	padding: 2rem 0;
	background: #f7f9fc;
}

.app-footer {
	padding: 1rem 0;
	text-align: center;
	background: #eef2f7;
}

.nav a {
	color: rgba(255, 255, 255, 0.95);
	text-decoration: none;
	margin-left: 1rem;
}
</style>
