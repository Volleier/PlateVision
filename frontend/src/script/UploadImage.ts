import { defineComponent, ref } from 'vue';

export default defineComponent({
  name: 'HomeView',
  setup() {
    const fileInput = ref<HTMLInputElement | null>(null);
    const isDragging = ref(false);
    const selectedFile = ref<File | null>(null);
    const previewSrc = ref<string>('');
    const errorMsg = ref<string>('');
    const uploadedUrl = ref<string>('');

    function openFile() {
      fileInput.value?.click();
    }

    function onFileChange(e: Event) {
      const input = e.target as HTMLInputElement;
      const f = input.files?.[0] ?? null;
      setFile(f);
    }

    function onDragOver(e: DragEvent) { e.dataTransfer && (e.dataTransfer.dropEffect = 'copy'); }
    function onDragEnter() { isDragging.value = true; }
    function onDragLeave() { isDragging.value = false; }

    function onDrop(e: DragEvent) {
      isDragging.value = false;
      const f = e.dataTransfer?.files?.[0] ?? null;
      setFile(f);
    }

    function setFile(f: File | null) {
      errorMsg.value = '';
      uploadedUrl.value = '';
      selectedFile.value = f;
      if (!f) {
        previewSrc.value = '';
        return;
      }
      const reader = new FileReader();
      reader.onload = () => { previewSrc.value = String(reader.result || ''); };
      reader.onerror = () => { errorMsg.value = 'Cannot read file'; previewSrc.value = ''; };
      reader.readAsDataURL(f);
    }

    async function uploadFile() {
      errorMsg.value = '';
      if (!selectedFile.value) {
        errorMsg.value = 'No file selected';
        return;
      }
      try {
        const form = new FormData();
        form.append('image', selectedFile.value); // 与后端约定字段名 'image'

        const res = await fetch('http://localhost:5000/api/upload', {
          method: 'POST',
          body: form,
        });

        if (!res.ok) {
          const text = await res.text().catch(() => '');
          let json = null;
          try { json = JSON.parse(text); } catch { json = { error: text || res.statusText }; }
          throw new Error(json.error || json.detail || 'upload failed');
        }

        const data = await res.json();
        uploadedUrl.value = data.url || data.path || '';
      } catch (err: any) {
        errorMsg.value = String(err.message ?? err);
      }
    }

    return {
      fileInput,
      isDragging,
      selectedFile,
      previewSrc,
      errorMsg,
      uploadedUrl,
      openFile,
      onFileChange,
      onDragOver,
      onDragEnter,
      onDragLeave,
      onDrop,
      uploadFile,
    };
  },
});
