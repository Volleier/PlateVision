<template>
    <div class="home-root">
        <section class="home-grid">
            <aside class="home-grid__upload">
                <!-- Image Upload Area -->
                <div class="upload-box" :class="{ 'drag-over': isDragging }" @dragover.prevent="onDragOver"
                    @dragenter.prevent="onDragEnter" @dragleave.prevent="onDragLeave" @drop.prevent="onDrop">
                    <p class="home-title">Upload Image</p>

                    <div class="upload-actions" @click.stop>
                        <button class="upload-btn upload-btn--send" @click.stop.prevent="uploadFile()"
                            :disabled="!selectedFile">
                            Upload
                        </button>
                    </div>

                    <input ref="fileInput" id="fileInput" type="file" accept="image/*" style="display:none"
                        @change="onFileChange" />

                    <!-- 仅保留图片预览区域响应点击，移除 wrapper 与 Enter 键处理 -->
                    <div class="upload-preview" @click="openFile">
                        <img v-if="previewSrc" :src="previewSrc" alt="uploaded preview" class="preview-image" />
                        <p v-else class="placeholder">Drag the image here, or click here to select</p>
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

<script lang="ts" src="../script/UploadImage.ts"></script>

<style lang="scss" scoped src="../assets/styles/UploadImage.scss"></style>
