from app import app
from config import Config
import logging

logger = logging.getLogger(__name__)

if __name__ == '__main__':
    port = Config.PORT
    debug = not Config.PRODUCTION
    
    logger.info(f"Starting Flask app on port {port} with debug={debug}")
    app.run(debug=debug, host='0.0.0.0', port=port)