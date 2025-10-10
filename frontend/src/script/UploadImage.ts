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

        // 兼容包装在 detection 的情况
        let payload: any = data;
        if (data && typeof data === "object" && data.detection)
          payload = data.detection;
        const detectorResult = payload.detector_result || payload;
        const internal =
          (detectorResult && detectorResult.internal) || payload.internal || {};

        // 打印 number_results（如果有）
        const numberResults =
          internal.number_results ||
          detectorResult.number_results ||
          payload.number_results;

        // 优先使用 number_results 中的图片（来自 static/results/number）
        if (
          numberResults &&
          Array.isArray(numberResults.images) &&
          numberResults.images.length > 0
        ) {
          const nrImg = numberResults.images[0]; // 取第一张识别后的图
          const candidate = tryNormalizeToBackendUrl(nrImg) || nrImg;
          annotatedSrc.value =
            candidate +
            (candidate.includes("?") ? "&" : "?") +
            `t=${Date.now()}`;
          console.log("Using number_results image for display:", nrImg);
        } else {
          // 原有回退逻辑：寻找 annotated/expor ted 字段
          let annotatedPath =
            internal.annotated_url ||
            internal.exported_url ||
            internal.annotated_image ||
            internal.exported_image ||
            detectorResult.annotated_url ||
            detectorResult.annotated_image ||
            payload.annotated_url ||
            payload.annotated_image ||
            payload.url ||
            "";

          if (annotatedPath) {
            // 优先把 /static/... 转为后端完整 URL，避免被 vite dev server 拦截
            const candidate =
              tryNormalizeToBackendUrl(annotatedPath) || annotatedPath;
            annotatedSrc.value =
              candidate +
              (candidate.includes("?") ? "&" : "?") +
              `t=${Date.now()}`;
          } else {
            errorMsg.value = "No annotated image returned from server";
            console.warn("No annotated image in server response:", data);
          }
        }

        if (numberResults) console.log("number_results:", numberResults);
      } catch (err: any) {
        errorMsg.value = String(err || "upload error");
        console.error("uploadFile error:", err);
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
