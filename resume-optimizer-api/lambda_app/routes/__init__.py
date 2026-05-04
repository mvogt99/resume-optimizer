"""Routes registration."""


def register_routes(app):
    """Register all routes with the Flask app."""
    # Placeholder: routes to be added in Phase 2.3
    @app.route("/health", methods=["GET"])
    def health():
        return {"status": "ok"}, 200
