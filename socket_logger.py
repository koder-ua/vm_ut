# ============== Socket Logger =============== #
import os
import sys
import logging
import logging.handlers # you NEED this line

logger = logging.getLogger("%s_%s" % (os.getpid(), sys.argv[1]) )
logger.setLevel(logging.DEBUG)
socketHandler = logging.handlers.SocketHandler('localhost',
                    logging.handlers.DEFAULT_TCP_LOGGING_PORT)
logger.addHandler(socketHandler)
# ============== Socket Logger =============== #