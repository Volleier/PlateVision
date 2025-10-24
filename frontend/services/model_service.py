import requests
import logging
import json
from typing import Optional

logger = logging.getLogger(__name__)

class ModelService:
    """Frontend model service: 将图片以 multipart/form-data POST 到后端 Flask 服务（/api/upload）。"""

    def __init__(self, backend_url: Optional[str] = None, timeout: float = 10.0):
        # backend URL and timeout
        self.backend_url = backend_url or "http://localhost:5000"
        self.timeout = timeout

    def _health_ok(self) -> bool:
        """简易健康检查；尝试 /health 和 /api/health 两个路径以兼容后端可能的路由。"""
        try:
            base = self.backend_url.rstrip('/')
            for suffix in ("/health", "/api/health"):
                try:
                    r = requests.get(f"{base}{suffix}", timeout=2.0)
                except Exception:
                    continue
                if r.status_code == 200:
                    try:
                        data = r.json()
                        return data.get("status") == "ok"
                    except Exception:
                        return False
        except Exception:
            pass
        return False

    def process_image(self, image, config: Optional[dict] = None) -> dict:
        """
        将上传的图片发送到后端 /api/upload 并返回后端 JSON。
        - 使用表单字段 'file'（后端会优先检查 'file'，也兼容 'image'）
        """
        if image is None:
            raise ValueError("No image provided")

        # 健康检查（尝试 localhost 与 127.0.0.1）
        health_checked = False
        last_error = None
        base = self.backend_url.rstrip('/')
        candidates = [f"{base}/health"]
        if "localhost" in base:
            candidates.append(base.replace("localhost", "127.0.0.1") + "/health")

        for url in candidates:
            try:
                resp = requests.get(url, timeout=5)
                logger.warning("Backend health check url=%s status=%s body=%s", url, resp.status_code, resp.text)
                if resp.status_code == 200:
                    try:
                        payload = resp.json()
                        if payload.get("status") == "ok":
                            health_checked = True
                            break
                        else:
                            last_error = f"unhealthy_response:{payload}"
                    except Exception as e:
                        last_error = f"invalid_json:{e}"
                else:
                    last_error = f"status_{resp.status_code}:{resp.text}"
            except Exception as e:
                last_error = str(e)
                logger.exception("Health check request failed for %s", url)

        if not health_checked:
            raise RuntimeError(f"Backend health check failed for {self.backend_url}: {last_error}")

        # 读取 bytes
        try:
            img_bytes = image.getvalue() if hasattr(image, "getvalue") else image.read()
        except Exception as e:
            raise RuntimeError(f"Failed to read uploaded file bytes: {e}")

        filename = getattr(image, "name", "image")
        content_type = getattr(image, "type", "application/octet-stream") or "application/octet-stream"
        files = {
            "file": (filename, img_bytes, content_type)
        }
        data = {}
        if config is not None:
            data["config"] = json.dumps(config)

        try:
            resp = requests.post(f"{self.backend_url}/api/upload", files=files, data=data, timeout=self.timeout)
        except Exception as e:
            raise RuntimeError(f"Failed to call backend {self.backend_url}/api/upload: {e}")

        try:
            resp.raise_for_status()
        except Exception:
            body = None
            try:
                body = resp.text
            except Exception:
                body = "<no-body>"
            raise RuntimeError(f"Backend returned status {resp.status_code}: {body}")

        # 处理异步 accepted（202）与同步返回（200）
        if resp.status_code == 202:
            try:
                payload = resp.json()
            except Exception:
                payload = {"message": "accepted", "raw_body": resp.text}
            return {"status": "accepted", **payload}

        try:
            return resp.json()
        except Exception as e:
            raise RuntimeError(f"Failed to parse backend JSON response: {e}")
