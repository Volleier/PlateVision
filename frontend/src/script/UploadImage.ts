import { defineComponent, ref } from "vue";

export default defineComponent({
  name: "UploadImageView",
  setup() {
    const fileInput = ref<HTMLInputElement | null>(null);
    const selectedFile = ref<File | null>(null);
    const previewSrc = ref<string>("");
    const annotatedSrc = ref<string>("");
    const isDragging = ref(false);
    const errorMsg = ref<string>("");
    // 标记是否已经尝试过用后端完整地址回退（避免无限重试）
    const triedBackendFull = ref(false);

    function openFile() {
      fileInput.value?.click();
    }

    function onFileChange(e: Event) {
      const target = e.target as HTMLInputElement;
      const f = target.files && target.files[0];
      if (!f) return;
      selectedFile.value = f;
      previewSrc.value = URL.createObjectURL(f);
      annotatedSrc.value = "";
      errorMsg.value = "";
      triedBackendFull.value = false;
    }

    function onDragOver(e: DragEvent) {
      if (e.dataTransfer) e.dataTransfer.dropEffect = "copy";
    }
    function onDragEnter() {
      isDragging.value = true;
    }
    function onDragLeave() {
      isDragging.value = false;
    }
    function onDrop(e: DragEvent) {
      isDragging.value = false;
      const f =
        e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (!f) return;
      selectedFile.value = f;
      previewSrc.value = URL.createObjectURL(f);
      annotatedSrc.value = "";
      errorMsg.value = "";
      triedBackendFull.value = false;
    }

    function pathToStaticUrl(serverPath: string | undefined | null): string {
      if (!serverPath) return "";
      const p = String(serverPath).replace(/\\/g, "/");
      const marker = "/backend/static";
      const idx = p.indexOf(marker);
      if (idx >= 0) {
        return "/static" + p.slice(idx + marker.length);
      }
      if (p.startsWith("/static/")) return p;
      const name = p.split("/").pop() || "";
      return name ? `/static/results/number/${name}` : "";
    }

    function tryNormalizeToBackendUrl(urlOrPath: string): string {
      const p = (urlOrPath || "").replace(/\\/g, "/");
      if (!p) return "";
      if (p.startsWith("/static/")) {
        return `http://localhost:5000${p}`;
      }
      if (p.startsWith("http://") || p.startsWith("https://")) return p;
      // 如果是绝对 fs path e:/.../backend/static/...
      const marker = "/backend/static";
      const idx = p.indexOf(marker);
      if (idx >= 0) {
        return `http://localhost:5000/static${p.slice(idx + marker.length)}`;
      }
      return "";
    }

    async function uploadFile() {
      if (!selectedFile.value) return;
      errorMsg.value = "";
      annotatedSrc.value = "";
      triedBackendFull.value = false;

      const fd = new FormData();
      fd.append("file", selectedFile.value);

      try {
        const resp = await fetch("http://localhost:5000/api/upload", {
          method: "POST",
          body: fd,
        });
        if (!resp.ok) {
          errorMsg.value = `Upload failed: ${resp.status} ${resp.statusText}`;
          console.error("Upload failed response:", await resp.text());
          return;
        }
        const data = await resp.json();
        console.log("upload response:", data);

        const { job_id, file_id } = data;

        if (!job_id) {
          // 同步处理（无 executor），直接显示结果
          handleResult(data.result);
          return;
        }

        // 异步处理，轮询任务状态
        errorMsg.value = "处理中，请稍候...";
        const pollInterval = setInterval(async () => {
          try {
            const statusResp = await fetch(
              `http://localhost:5000/api/tasks/${job_id}`
            );
            const statusData = await statusResp.json();

            if (statusData.status === "done") {
              clearInterval(pollInterval);
              errorMsg.value = "";
              // 获取结果图片
              annotatedSrc.value = `http://localhost:5000/api/send/${file_id}?t=${Date.now()}`;
            } else if (statusData.status === "error") {
              clearInterval(pollInterval);
              errorMsg.value = `处理失败: ${statusData.error}`;
            }
            // pending 状态继续轮询
          } catch (err) {
            clearInterval(pollInterval);
            errorMsg.value = `轮询失败: ${err}`;
          }
        }, 1000); // 每秒轮询一次
      } catch (err: any) {
        errorMsg.value = String(err || "upload error");
        console.error("uploadFile error:", err);
      }
    }

    // 处理同步返回的结果（兼容无 executor 的情况）
    function handleResult(result: any) {
      if (!result) return;
      const internal =
        result.detector_result?.internal || result.internal || {};
      const annotatedPath =
        internal.annotated_image || internal.exported_image || "";
      if (annotatedPath) {
        const candidate =
          tryNormalizeToBackendUrl(annotatedPath) || annotatedPath;
        annotatedSrc.value =
          candidate + (candidate.includes("?") ? "&" : "?") + `t=${Date.now()}`;
      }
    }

    // 当 <img> 报错（无法加载）时，尝试把 /static/... 转为后端完整地址一次
    function onAnnotatedError(e: Event) {
      if (triedBackendFull.value) {
        errorMsg.value = "Failed to load processed image";
        return;
      }
      triedBackendFull.value = true;
      const current = annotatedSrc.value || "";
      // 如果已经是完整 URL 则无法修复
      if (current.startsWith("http://") || current.startsWith("https://")) {
        errorMsg.value = "Failed to load processed image";
        return;
      }
      // 尝试基于原路径构造后端完整地址
      // extract path part if query exists
      const raw = current.split("?")[0];
      const backendUrl = tryNormalizeToBackendUrl(raw);
      if (backendUrl) {
        annotatedSrc.value =
          backendUrl +
          (backendUrl.includes("?") ? "&" : "?") +
          `t=${Date.now()}`;
      } else {
        errorMsg.value = "Failed to load processed image";
      }
    }

    return {
      fileInput,
      selectedFile,
      previewSrc,
      annotatedSrc,
      isDragging,
      errorMsg,
      openFile,
      onFileChange,
      onDragOver,
      onDragEnter,
      onDragLeave,
      onDrop,
      uploadFile,
      onAnnotatedError,
    };
  },
});
