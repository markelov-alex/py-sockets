import hashlib
from threading import Thread, Event, Condition
from unittest import TestCase

from napalm.core import SocketGameApplication
from napalm.play.client import GameClientProtocol, GameClientConfig
from napalm.play.core import HouseConfig
from napalm.play.protocol import GameProtocol
from napalm.socket.client import BlockingTCPClient
from napalm.socket.server import ThreadedTCPServer


class MyGameProtocol(GameProtocol):

    def __init__(self, send_bytes_method=None, close_connection_method=None, address=None, config=None, app=None):
        super().__init__(send_bytes_method, close_connection_method, address, config, app)

        self.processed_command_codes = []

    def _process_command(self, command_code, command_params, params_count):
        super()._process_command(command_code, command_params, params_count)

        self.processed_command_codes.append(command_code)
        with TestServerSystem.condition:
            TestServerSystem.condition.notify()


class MyGameClientProtocol(GameClientProtocol):

    def __init__(self, send_bytes_method=None, close_connection_method=None, address=None, config=None, app=None):
        super().__init__(send_bytes_method, close_connection_method, address, config, app)

        self.processed_command_codes = []

    def _process_command(self, command_code, command_params, params_count):
        super()._process_command(command_code, command_params, params_count)

        self.processed_command_codes.append(command_code)
        with TestServerSystem.condition:
            TestServerSystem.condition.notify()


class TestServerSystem(TestCase):
    condition = Condition()

    CLIENT_COUNT = 3
    server_class = ThreadedTCPServer
    client_class = BlockingTCPClient

    server_config = HouseConfig(house_id="0", data_dir_path="initial_configs/", protocol_class=MyGameProtocol)
    client_config = GameClientConfig("localhost", 41001, MyGameClientProtocol)

    server_app = None
    server_app_thread = None
    clients = []
    client_thread_by_client = {}

    @staticmethod
    def make_auth_sig(social_id, access_token, app_secret):
        md5 = hashlib.md5()
        md5.update((social_id + "_" + access_token + "_" + app_secret).encode('utf-8'))
        sig = md5.hexdigest()
        return sig

    def setUp(self):
        super().setUp()

        self.server_app = SocketGameApplication(self.server_config, self.server_class)
        self.start_server(self.server_app)

        for i in range(self.CLIENT_COUNT):
            credentials = {
                "user_id": str(i + 1),
                "social_id": str(i + 1001),
                "access_token": "qwertyuiopasdfghjklzxcvbnm" + str(i + 1),
                "auth_sig": TestServerSystem.make_auth_sig(str(i + 1), 
                                                           "qwertyuiopasdfghjklzxcvbnm" + str(i + 1), 
                                                           "tyuiop12345"),
                "backend": "fb_local"
            }
            client = self.client_class(self.client_config, credentials)
            self.clients.append(client)
            self.clients.append(client)

    def tearDown(self):
        super().tearDown()

        self.server_app.dispose()
        self.server_app_thread.join()
        # (list() needed to make a copy)
        for client in list(self.clients):
            client.dispose()
        for client, client_thread in self.client_thread_by_client:
            client_thread.join()
        self.server_app = None
        self.server_app_thread = None
        self.clients.clear()
        self.client_thread_by_client.clear()

    # Utility

    def start_server(self):
        self.server_app_thread = Thread(target=self.server_app.start)
        self.server_app_thread.start()

    def stop_server(self):
        self.server_app.stop()
        self.server_app_thread.join()

    def connect_client(self, client):
        client_thread = Thread(target=client.connect)
        client_thread.start()
        self.client_thread_by_client[client] = client_thread

    def close_client(self, client):
        client.close()
        client_thread = self.client_thread_by_client[client]
        client_thread.join()

    # Tests

    def test_client_server_connections(self):
        house = self.server_app.house
        # client1 and client2 are of same user
        client1 = self.clients[0]
        client2 = self.clients[1]
        client3 = self.clients[2]

        # Ensure house created successfully
        self.assertEqual(len(house.house_model.lobby_model_list), 3)

        # Test 3 client of 2 users connected
        self.connect_client(client1)
        self.connect_client(client2)
        self.connect_client(client3)

        with self.condition:
            self.condition.wait_for(lambda : len(client1.protocol.processed_command_codes) > 1)
        # client1.protocol.processed_command_codes.clear()

        self.assertEqual(len(house.users_online), 2)
        self.assertEqual(len(house.players_online), 3)
        self.assertEqual(len(house.players_connected), 3)

        # Disconnect 1st client
        self.close_client(client1)

        self.assertEqual(len(house.users_online), 2)
        self.assertEqual(len(house.players_online), 2)
        self.assertEqual(len(house.players_connected), 2)

        # Disconnect 3rd client
        self.close_client(client1)

        self.assertEqual(len(house.users_online), 1)
        self.assertEqual(len(house.players_online), 1)
        self.assertEqual(len(house.players_connected), 1)

        # Restart server (test save/restore)
        self.stop_server()
        self.start_server()
        house = self.server_app.house

        self.assertEqual(len(house.users_online), 12)
        self.assertEqual(len(house.players_online), 1)
        self.assertEqual(len(house.players_connected), 1)

        # Reconnect 1st client
        self.connect_client(client1)

        self.assertEqual(len(house.users_online), 2)
        self.assertEqual(len(house.players_online), 2)
        self.assertEqual(len(house.players_connected), 2)
