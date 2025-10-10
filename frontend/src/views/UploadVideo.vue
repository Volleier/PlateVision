<template>
    <div class="home-root">
        <section class="home-grid">
            <aside class="home-grid__upload">
                <!-- Image Upload Area -->
                <div class="upload-box" :class="{ 'drag-over': isDragging }" @dragover.prevent="onDragOver"
                    @dragenter.prevent="onDragEnter" @dragleave.prevent="onDragLeave" @drop.prevent="onDrop">
                    <p class="home-title">Upload Video</p>
                    <p class="upload-instruction">Drag the video here, or click to select</p>

                    <!-- 按钮行：选择 + 上传 -->
                    <div class="upload-actions">
                        <button class="upload-btn" @click.prevent="openFile()">Select Video</button>
                        <button class="upload-btn upload-btn--send" @click.prevent="uploadFile()"
                            :disabled="!selectedFile">
                            Upload
                        </button>
                    </div>

                    <input ref="fileInput" id="fileInput" type="file" accept="image/*" style="display:none"
                        @change="onFileChange" />
                    <div class="upload-preview">
                        <video v-if="previewSrc" :src="previewSrc" alt="uploaded preview" class="preview-video"
                            controls />
                        <p v-else class="placeholder">No video uploaded</p>
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

<script lang="ts" src="../script/UploadVideo.ts"></script>

<style lang="scss" scoped src="../assets/styles/UploadVideo.scss"></style>
