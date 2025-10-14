from flask import Flask
from flask_cors import CORS
import os

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # Limit upload size to 16 MB

    # Initialize logging
    from logger import setup_logging
    setup_logging(app)

    # Initialize error handlers
    from error_handlers import register_error_handlers
    register_error_handlers(app)

    # Allow frontend cross-origin access to /api/* during development
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Register upload blueprint
    from api.upload import bp as upload_bp
    app.register_blueprint(upload_bp)

    return app

if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)