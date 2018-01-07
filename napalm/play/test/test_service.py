import hashlib
import json
import unittest

from napalm.play.service import GameService


class TestGameService(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.service = GameService()
        # todo get all credentials from externel file
        # FB
        # self.service.domain = "fb.poker.local"
        # self.service.secured = False
        # self.service.app_secret = ""
        # self.service.napalm_secret = ""
        # self.service.social_id = ""
        # self.service.access_token = ""
        # VK
        self.service.domain = "vk.poker.local"
        self.service.secured = False
        self.service.app_secret = ""
        self.service.napalm_secret = ""
        self.service.social_id = ""
        self.service.access_token = ""
        
        md5 = hashlib.md5()
        md5.update((self.service.social_id + "_" + self.service.access_token + "_" + self.service.app_secret).encode("utf-8"))
        self.service.auth_sig = md5.hexdigest()

    def tearDown(self):
        super().tearDown()

    def test_User_getCurrentUserFullInfo(self):
        result = self.service.getCurrentUserFullInfo()
        self.assertIsNotNone(result)
        print(json.dumps(result))
