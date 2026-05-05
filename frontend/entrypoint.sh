#!/bin/sh
# Write runtime env vars into a JS snippet loaded before the main bundle
cat > /usr/share/nginx/html/env.js << ENVEOF
window.CLOUDLIFT_ENV = "${CLOUDLIFT_ENV:-unknown}";
window.APP_ENV_NAME = "${APP_ENV_NAME:-${CLOUDLIFT_ENV:-unknown}}";
ENVEOF
exec "$@"
