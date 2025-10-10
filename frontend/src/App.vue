<template>
	<div id="app" class="app-root">
		<Header v-if="!($route.meta && $route.meta.hideHeader)" @upload="onUpload" @check="onCheck" />

		<main class="app-main">
			<router-view />
		</main>
	</div>
</template>

<script lang="ts">
import { defineComponent } from 'vue'
import Header from './views/components/Header.vue'

export default defineComponent({
	name: 'App',
	components: { Header },
	methods: {
		onUpload() { },
		onCheck() { }
	}
})
</script>
