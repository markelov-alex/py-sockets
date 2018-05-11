import hashlib
import json
import unittest

from napalm.play.service import GameService


class TestGameService(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.service = GameService()
        # FB
        # self.service.domain = "fb.poker.local"
        # self.service.secured = False
        # self.service.app_secret = "5b84f30dd8735b25531dcb8a1f7c27b5"
        # self.service.napalm_secret = "myrandomforsocketserverSnJdG6dDZq6Os3i6iilo"
        # self.service.social_id = "10208394160283890"
        # self.service.access_token = "EAAAAEWTRH1UBACC8MGkHUMZBuGuAqYzvJkauzCcZCSDqD1LFENT1a7JNAZBvk1szoXVJlE83WUL2XZBfBzbsthhYwZCkljUzYdIm90OFZCR7B8wJu1GZBFpN7T5t7DKl5DHHTvPFugYPa8dVlCAVk9fkhpZCZBce9g6cZD"
        # VK
        self.service.domain = "vk.poker.local"
        self.service.secured = False
        self.service.app_secret = "PftmdquD4O1kjguwrfdQ"
        self.service.napalm_secret = "myrandomforsocketserverSnJdG6dDZq6Os3i6iilo"
        self.service.social_id = "10306045"
        self.service.access_token = "49515a063773f12ac01a906dc4e4264e4c1e4a8354d9a26fd6813c815ff4e5aa1517cb66e484ade50f9a9"
        
        md5 = hashlib.md5()
        md5.update((self.service.social_id + "_" + self.service.access_token + "_" + self.service.app_secret).encode("utf-8"))
        self.service.auth_sig = md5.hexdigest()

    def tearDown(self):
        super().tearDown()

    def test_User_getCurrentUserFullInfo(self):
        result = self.service.getCurrentUserFullInfo()
        self.assertIsNotNone(result)
        print(json.dumps(result))
