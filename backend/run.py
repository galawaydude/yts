import logging
from config import Config

# --- THIS IS THE FIX ---
# Configure logging at the very top, BEFORE importing app
# This ensures all loggers (even in __init__.py) are ready.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# ---------------------

# Now, import the app
from app import app

if __name__ == '__main__':
    # We already configured logging, so just get the port/debug
    port = Config.PORT
    
    # Set this to False to see the logs
    debug = False 
    
    # Or, set it back to normal when you're done:
    # debug = not Config.PRODUCTION
    
    logger.info(f"Starting Flask app on port {port} with debug={debug}")
    app.run(debug=debug, host='0.0.0.0', port=port)