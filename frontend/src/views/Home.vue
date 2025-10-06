<template>
	<div class="home-root">
		<section class="home-grid">
			<aside class="home-grid__upload">
				<!-- Image Upload Area -->
				<div class="upload-box" :class="{ 'drag-over': isDragging }" @dragover.prevent="onDragOver"
					@dragenter.prevent="onDragEnter" @dragleave.prevent="onDragLeave" @drop.prevent="onDrop">
					<p class="home-title">Upload Image</p>
					<p class="upload-instruction">Drag the image here, or click to select</p>

					<!-- 按钮行：选择 + 上传 -->
					<div class="upload-actions">
						<button class="upload-btn" @click.prevent="openFile()">Select Image</button>
						<button class="upload-btn upload-btn--send" @click.prevent="uploadFile()"
							:disabled="!selectedFile">
							Upload
						</button>
					</div>

					<input ref="fileInput" id="fileInput" type="file" accept="image/*" style="display:none"
						@change="onFileChange" />
					<div class="upload-preview">
						<img v-if="previewSrc" :src="previewSrc" alt="uploaded preview" class="preview-image" />
						<p v-else class="placeholder">No image uploaded</p>
					</div>
					<p v-if="errorMsg" class="error">{{ errorMsg }}</p>
				</div>
			</aside>

			<section class="home-grid__preview">
				<!-- Image Show Area (kept empty per layout) -->
				<div class="preview-box">
					<p class="home-title">Show Area</p>
					<!-- Intentionally left blank; left-side upload area shows uploaded image -->
				</div>
			</section>
		</section>
	</div>
</template>

<script lang="ts" src="../script/Home.ts"></script>

<style lang="scss" scoped src="../assets/styles/Home.scss"></style>
