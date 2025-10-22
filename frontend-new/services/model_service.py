import requests
from typing import Optional
import re

class SimpleModelService:
    """Frontend model service: 将图片以 multipart/form-data POST 到后端 FastAPI 服务。后端必须可用，否则抛出异常。"""

    def __init__(self, backend_url: Optional[str] = None, timeout: float = 10.0):
        # backend URL and timeout
        self.backend_url = backend_url or "http://localhost:5000"
        self.timeout = timeout

    def _health_ok(self) -> bool:
        """简易健康检查；若无法连接或返回非预期则返回 False。"""
        try:
            r = requests.get(f"{self.backend_url}/health", timeout=2.0)
            if r.status_code == 200:
                data = r.json()
                return bool(data.get("model_loaded", False))
        except Exception:
            pass
        return False

    def process_image(self, uploaded_file, config: Optional[dict] = None) -> dict:
        """
        将上传的图片发送到后端 /process-image 并返回后端 JSON。
        - uploaded_file: Streamlit UploadedFile（支持 .getvalue() 或 .read()，并具有 .name/.type）
        - config: 可选字典，会以 form 字段 "config" 的 JSON 字符串形式发送
        - 如果后端不可达或返回非 2xx，将抛出 RuntimeError / requests 异常
        """
        if uploaded_file is None:
            raise ValueError("No image provided")

        # 健康检查：如果后端未通过健康检查，直接抛出异常（不做本地回退）
        if not self._health_ok():
            raise RuntimeError(f"Backend health check failed for {self.backend_url}")

        # 读取 bytes
        try:
            img_bytes = uploaded_file.getvalue() if hasattr(uploaded_file, "getvalue") else uploaded_file.read()
        except Exception as e:
            raise RuntimeError(f"Failed to read uploaded file bytes: {e}")

        # 构造 multipart/form-data
        filename = getattr(uploaded_file, "name", "image")
        content_type = getattr(uploaded_file, "type", "application/octet-stream") or "application/octet-stream"
        files = {
            "image": (filename, img_bytes, content_type)
        }
        data = {}
        if config is not None:
            import json
            data["config"] = json.dumps(config)

        # 发送请求到后端 /process-image
        try:
            resp = requests.post(f"{self.backend_url}/process-image", files=files, data=data, timeout=self.timeout)
        except Exception as e:
            # 网络/连接错误：按要求抛出异常
            raise RuntimeError(f"Failed to call backend {self.backend_url}/process-image: {e}")

        # 非成功响应也视为错误并抛出
        try:
            resp.raise_for_status()
        except Exception:
            # 尝试包含后端返回的文本以便调试
            body = None
            try:
                body = resp.text
            except Exception:
                body = "<no-body>"
            raise RuntimeError(f"Backend returned status {resp.status_code}: {body}")

        # 返回解析后的 JSON（如果非 JSON，会抛出 ValueError）
        try:
            return resp.json()
        except Exception as e:
            raise RuntimeError(f"Failed to parse backend JSON response: {e}")
