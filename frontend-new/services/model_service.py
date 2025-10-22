import requests
from typing import Optional
import re

class SimpleModelService:
    """Frontend model service: calls backend FastAPI service, falls back to a default message on failure."""

    def __init__(self, backend_url: Optional[str] = None, timeout: float = 10.0):
        # backend URL and timeout
        self.backend_url = backend_url or "http://localhost:8000"
        self.timeout = timeout

    def _health_ok(self) -> bool:
        # simple health check: ensure model is loaded
        try:
            r = requests.get(f"{self.backend_url}/health", timeout=2.0)
            if r.status_code == 200:
                data = r.json()
                return bool(data.get("model_loaded", False))
        except Exception:
            pass
        return False

    def summarize(self, text: str, max_length: int = 150, min_length: int = 30,
                  do_sample: bool = False, temperature: float = 0.7,
                  num_beams: int = 4, length_penalty: float = 2.0) -> str:
        """Call backend /summarize, fall back locally on failure."""
        payload = {
            "text": text,
            "max_length": max_length,
            "min_length": min_length,
            "num_beams": num_beams,
            "length_penalty": length_penalty
        }

        # 如果健康检查未通过，直接回退并标明原因
        if not self._health_ok():
            reason = "HEALTH_CHECK_FAILED"
            print(f"[model_service] Health check failed, falling back to local summary. reason={reason}")
            return self._local_fallback_summary(text, max_length, min_length, do_sample, temperature, num_beams, reason)

        try:
            r = requests.post(f"{self.backend_url}/summarize", json=payload, timeout=self.timeout)
            if r.status_code == 200:
                j = r.json()
                if isinstance(j, dict):
                    if "summary" in j:
                        return j["summary"]
                    if "summaries" in j and isinstance(j["summaries"], list) and j["summaries"]:
                        return j["summaries"][0]
                    if "result" in j:
                        return j["result"]
                if isinstance(j, str):
                    return j
                # 响应解析失败
                reason = "BACKEND_MALFORMED_RESPONSE"
                print(f"[model_service] Backend returned malformed response, falling back. reason={reason}, raw={j}")
            else:
                reason = f"BACKEND_STATUS_{r.status_code}"
                print(f"[model_service] Backend returned status code {r.status_code}, falling back to local summary. reason={reason}, body={r.text}")
        except Exception as e:
            reason = f"BACKEND_EXCEPTION:{type(e).__name__}:{e}"
            print(f"[model_service] Failed to call backend: {e}, falling back to local summary. reason={reason}")

        return self._local_fallback_summary(text, max_length, min_length, do_sample, temperature, num_beams, reason)

    def _local_fallback_summary(self, text, max_length, min_length, do_sample, temperature, num_beams, reason: Optional[str] = None):
        # 任何回退都直接抛错，带上明确原因；如果没有原因则标记为 UNKNOWN_REASON。
        if not reason:
            reason = "UNKNOWN_REASON"

        tag = f"[LOCAL SUMMARY FALLBACK:{reason}]"

        # 空输入单独报 EMPTY_INPUT
        if not text or not text.strip():
            reason = "EMPTY_INPUT"
            tag = f"[LOCAL SUMMARY FALLBACK:{reason}]"
            msg = f"{tag} 输入文本为空，无法生成摘要。"
            print(f"[model_service] {msg}")
            raise RuntimeError(msg)

        # 有明确失败原因或默认 UNKNOWN_REASON，一律抛错
        msg = f"{tag} 无法生成摘要，原因：{reason}"
        print(f"[model_service] {msg}")
        raise RuntimeError(msg)
