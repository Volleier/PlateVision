import { defineComponent, ref, onUnmounted } from 'vue'

const MAX_FILE_SIZE = 5 * 1024 * 1024 // 5MB

export default defineComponent({
    name: 'HomeView',
    setup() {
        const previewSrc = ref<string | null>(null)
        const isDragging = ref(false)
        const errorMsg = ref<string | null>(null)
        const fileInput = ref<HTMLInputElement | null>(null)
        let currentObjectUrl: string | null = null
        let dragCounter = 0

        function revokeCurrentUrl() {
            if (currentObjectUrl) {
                URL.revokeObjectURL(currentObjectUrl)
                currentObjectUrl = null
            }
        }

        function validateFile(file: File) {
            if (!file.type.startsWith('image/')) {
                return 'Please upload an image file.'
            }
            if (file.size > MAX_FILE_SIZE) {
                return 'File is too large. Max 5MB allowed.'
            }
            return null
        }

        function processFile(file: File | null) {
            errorMsg.value = null
            if (!file) {
                revokeCurrentUrl()
                previewSrc.value = null
                return
            }

            const validationError = validateFile(file)
            if (validationError) {
                errorMsg.value = validationError
                return
            }

            revokeCurrentUrl()
            currentObjectUrl = URL.createObjectURL(file)
            previewSrc.value = currentObjectUrl
        }

        function onFileChange(e: Event) {
            const input = e.target as HTMLInputElement
            if (!input.files || input.files.length === 0) {
                processFile(null)
                return
            }
            processFile(input.files[0])
        }

        function openFile() {
            fileInput.value?.click()
        }

        function onDragOver(e: DragEvent) {
            e.dataTransfer && (e.dataTransfer.dropEffect = 'copy')
            isDragging.value = true
        }

        function onDragEnter() {
            dragCounter++
            isDragging.value = true
        }

        function onDragLeave() {
            dragCounter--
            if (dragCounter <= 0) {
                isDragging.value = false
                dragCounter = 0
            }
        }

        function onDrop(e: DragEvent) {
            dragCounter = 0
            isDragging.value = false
            const dt = e.dataTransfer
            if (!dt || !dt.files || dt.files.length === 0) {
                return
            }
            const file = dt.files[0]
            processFile(file)
        }

        onUnmounted(() => {
            revokeCurrentUrl()
        })

        return {
            previewSrc,
            onFileChange,
            openFile,
            isDragging,
            onDragOver,
            onDragEnter,
            onDragLeave,
            onDrop,
            fileInput,
            errorMsg
        }
    }
})
