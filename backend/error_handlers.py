from flask import jsonify
import traceback

class ApiError(Exception):
    """
    业务中可抛出的结构化错误。
    用法： raise ApiError("缺少字段", status_code=422, payload={"field":"name"})
    """
    def __init__(self, message, status_code=400, payload=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload or {}

def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def handle_api_error(e: ApiError):
        app.logger.warning("ApiError: %s", e.message)
        body = {"error": e.message}
        body.update(e.payload)
        return jsonify(body), e.status_code

    @app.errorhandler(Exception)
    def handle_exception(e):
        # 记录完整堆栈以便排查
        app.logger.exception("Unhandled exception during request")
        payload = {"error": "Internal Server Error", "message": "An unexpected error occurred."}
        # 在开发模式下返回详细信息（仅用于调试）
        if app.debug or app.config.get("ENV") == "development":
            payload["detail"] = traceback.format_exc()
            payload["type"] = type(e).__name__
        return jsonify(payload), 500