import hashlib
import json
import logging

import certifi
import requests
import urllib3


class GameService:
    """
    To make requests to PHP server.

    TODO return cached values on request is too frequent
    """

    @staticmethod
    def make_auth_sig(social_id, access_token, app_secret):
        if not social_id or not access_token or not app_secret:
            return "(empty_auth_arg)"
        md5 = hashlib.md5()
        md5.update((social_id + "_" + access_token + "_" + app_secret).encode('utf-8'))
        sig = md5.hexdigest()
        return sig

    logging = None

    social_id = None
    access_token = None
    auth_sig = None
    backend_info = None

    @property
    def domain(self):
        return self.backend_info["domain"] if self.backend_info else None

    @property
    def secured(self):
        return self.backend_info["secured"] if self.backend_info else None

    @property
    def app_secret(self):
        return self.backend_info["app_secret"] if self.backend_info else None

    @property
    def napalm_secret(self):
        return self.backend_info["napalm_secret"] if self.backend_info else None

    def __init__(self):  # , social_id=None, access_token=None, auth_sig=None, backend_info=None):
        self.logging = logging.getLogger("SERVICE")

        # self.social_id = social_id
        # self.access_token = access_token
        # self.auth_sig = auth_sig
        # if backend_info:
        #     self.domain = backend_info["domain"]
        #     self.secured = backend_info["secured"]
        #     self.app_secret = backend_info["app_secret"]
        #     self.napalm_secret = backend_info["napalm_secret"]

    # todo call
    def dispose(self):
        # self.logging = None
        pass

    def check_auth_sig(self, social_id, access_token, auth_sig, backend_info=None):
        if self.social_id and social_id != self.social_id:
            return False

        self.backend_info = backend_info or self.backend_info
        if not self.app_secret:
            return False

        sig = self.__class__.make_auth_sig(social_id, access_token, self.app_secret)

        # Log if mismatch
        if sig != auth_sig:
            self.logging.warning(
                "WARNING! auth_sig mismatch! social_id: %s  %s => sig: %s != auth_sig: %s",
                social_id, social_id + "_" + access_token + "_" + self.app_secret, sig, auth_sig)
        else:
            # Set up
            # (Note: Updating credentials we are trying to avoid access_token expired)
            # self.social_id = social_id
            self.access_token = access_token
            self.auth_sig = auth_sig

        return sig == auth_sig

    def getCurrentUserFullInfo(self):
        if not self.access_token:
            return

        data = self._request("User", "getCurrentUserFullInfo")
        # {"social_id": 10306045, "level": 51, "country": "Беларусь", "is_online": 0, "server": 1,
        #  "updated_at": "2017-08-29 10:49:13", "created_at": "2017-08-29 10:49:13", "id": 46629,
        #  "first_name": "Александр", "last_name": "Маркелов", "nickname": null, "gender": 2, "birthdate": null,
        #  "profile_url": "\/\/vk.com\/alex.markelov", "language": null, "country_id": "BY", "city_id": 282,
        #  "city": "Минск", "photo_url": "https:\/\/pp.userapi.com\/c637617\/v637617045\/14a6d\/tjA0DP7sJDM.jpg",
        #  "friends": [{"id": 46632, "social_id": "7006568", "level": 52, "country": "2", "is_online": 0, "server": 2,
        #               "created_at": "2017-08-29 10:49:13", "updated_at": "2017-08-29 10:49:13"}],
        #  "game_data": {"money": 72653, "xp": 1454},
        #  "poker_stats": {"hands_played": 80, "hands_won": 56, "shootout_rounds_won": 19, "sitngos_won": 0,
        #                  "biggest_pot_win": 677, "highest_chips_level": 440674, "best_hand": "9;As,Ks,Qs,Js,Ts"},
        #  "buddies": [{"id": 46633, "social_id": "1378086", "level": 8, "country": "2", "is_online": 0, "server": 2,
        #               "created_at": "2017-08-29 10:49:13", "updated_at": "2017-08-29 10:49:13"},
        #              {"id": 46634, "social_id": "2331693", "level": 25, "country": "4", "is_online": 0, "server": 3,
        #               "created_at": "2017-08-29 10:49:13", "updated_at": "2017-08-29 10:49:13"},
        #              {"id": 46632, "social_id": "7006568", "level": 52, "country": "2", "is_online": 0, "server": 2,
        #               "created_at": "2017-08-29 10:49:13", "updated_at": "2017-08-29 10:49:13"}], "payments_real": [
        #     {"id": 19480, "order_id": 394742, "preorder_id": 0, "price_amount": "424.96", "product_type": "bonus",
        #      "product_id": 21, "product_amount": 4, "award": "{\"money\": 737,\"toy\": 65}", "award_status": 3,
        #      "created_at": "2017-08-29 10:49:13", "updated_at": "2017-08-29 10:49:13", "payed_at": null}],
        #  "payments_virtual": [
        #      {"id": 19247, "price_type": "796.22", "price_amount": 909, "product_type": "shop", "product_id": 53,
        #       "product_amount": 2, "award": "{\"money\": 966,\"toy\": 82}", "created_at": "2017-08-29 13:49:13"}],
        #  "achievements": [], "mail": [], "bonuses": [], "gifts": []}
        game = data["game_data"]
        stats = data["poker_stats"]
        best_hand = stats["best_hand"].split(";")
        user_info = [str(data["id"]), str(data["social_id"]), data["first_name"], data["last_name"],
                     data["profile_url"], None, None, data["level"], game["money"], 0, 0, data["created_at"], "",
                     0, 0, best_hand[0] if len(best_hand) else '', best_hand[1] if len(best_hand) > 1 else '']
        return user_info

    def increase(self, money=0, xp=0):
        if not self.access_token:
            return

        data = {}
        if money > 0:
            data["money"] = money
        if xp > 0:
            data["xp"] = xp

        if not data:
            return {}

        data = json.dumps(data)
        return self._request("User", "increase", {"data": data}, secure=True)

    def decrease(self, money=0, xp=0):
        if not self.access_token:
            return

        data = {}
        if money > 0:
            data["money"] = money
        if xp > 0:
            data["xp"] = xp

        if not data:
            return {}

        data = json.dumps(data)
        return self._request("User", "decrease", {"data": data}, secure=True)

    # def win(self, pot, max_combo_id, hand_cards, shootout=False, sitngo=False):
    #     hand_cards = max_combo_id + ";" + (",".join(hand_cards))
    #     data = json.dumps({"pot": pot, "hand_cards": hand_cards, "shootout": shootout, "sitngo": sitngo})
    #     return self._request("User", "win", {"data": data}, secure=True)
    # 
    # def loose(self):
    #     return self._request("User", "loose", secure=True)

    def gameEnd(self, winners_data, loser_ids, shootout=False, sitngo=False):
        if not self.access_token:
            return

        data = json.dumps({"win": winners_data, "loose": loser_ids, "shootout": shootout, "sitngo": sitngo})
        return self._request("User", "gameEnd", {"data": data}, secure=True)

    def _request(self, controller, method, data=None, secure=False, post=False):
        if not self.access_token:
            return

        url = ("https://" if self.secured else "http://") + self.domain + "/api/" + controller + "/" + method

        if not data:
            data = {}
        data["social_id"] = self.social_id
        data["access_token"] = self.access_token
        data["auth_sig"] = self.auth_sig
        if secure:
            data["secret"] = self.napalm_secret

        # if post:
        #     data = urllib.parse.urlencode(data)
        #     data = data.encode("ascii")
        #     result = urllib.request.urlopen(url, data).read()
        #     # result = urllib2.urlopen(url, data).read()
        # else:
        #     data = urllib.parse.urlencode(data, True)
        #     result = urllib.request.urlopen(url + "?" + data).read()
        #     # result = urllib2.urlopen(url, data).read()
        # 
        # result = json.loads(result)

        if post:
            result = requests.post(url, data, verify=False).json()
        else:
            result = requests.get(url, data, verify=False).json()
            # result = requests.get(url, data, verify="D:\\Work\\napalm\\library_server\\python\cert/cacert.pem").json()

        # http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
        # response = http.request("POST" if post else "GET", url, data)
        # result = json.load(response.data.decode("utf-8"))

        return result
