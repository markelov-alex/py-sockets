try:
    import napalm
except ImportError:
    import sys
    # Link libraries (to launch from command line console)
    sys.path.append("../../library_server/python/")
    import napalm

from napalm.utils.parsing_util import get_command_line_param
from napalm.core import SocketGameApplication
from napalm.play.poker.lobby import PokerLobbyModel
from napalm.socket.server import NonBlockingTCPServer, ThreadedTCPServer, TwistedTCPServer

if __name__ == "__main__":
    # Get params from command line (sys.argv)
    lobby_id = get_command_line_param("-server-id", 1)
    data_dir_path = get_command_line_param("-data-path")  # or "../server_data"
    is_twisted = get_command_line_param("-twisted")
    is_non_blocking = get_command_line_param("-non-blocking")
    is_no_restore = get_command_line_param("-no-restore")

    # Config play and server
    server_config = PokerLobbyModel(lobby_id=lobby_id, data_dir_path=data_dir_path)
    server_config.napalm_secret = "myrandomforsocketserverSnJdG6dDZq6Os3i6iilo"
    if is_no_restore:
        server_config.save_lobby_state_enabled = False

    server_class = TwistedTCPServer if is_twisted else (NonBlockingTCPServer if is_non_blocking else ThreadedTCPServer)

    # Create and start
    app = SocketGameApplication(server_config, server_class)
    app.start()
