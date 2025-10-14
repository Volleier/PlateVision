from flask import jsonify
from werkzeug.exceptions import HTTPException

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

    @app.errorhandler(HTTPException)
    def handle_http_exception(e: HTTPException):
        app.logger.warning("HTTPException: %s %s", getattr(e, "code", None), getattr(e, "description", ""))
        return jsonify({"error": e.name, "code": e.code, "description": e.description}), e.code

    @app.errorhandler(Exception)
    def handle_unhandled_exception(e: Exception):
        app.logger.exception("Unhandled exception:")
        return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred."}), 500