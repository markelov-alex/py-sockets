
# Utility
import random
from unittest.mock import Mock

import math

from napalm.play.house import User


def create_user(house_config, user_id, money_amount=0):
    user = User(house_config, user_id)
    user.first_name = "Some"
    user.last_name = "Name" + user_id
    user.money_amount = money_amount
    user._service = Mock(increase=lambda money: {"money": money}, decrease=lambda money: {"money": money})
    # user._service.increase = MagicMock(side_effect=lambda value: {"money": value})
    # user._service.decrease = MagicMock(side_effect=lambda value: {"money": value})
    return user


def create_player(user, is_connected=True, lobby=None):

    player = user.on_connect()
    player.protocol = Mock(is_ready=is_connected)
    if lobby:
        lobby.add_player(player)
    return player


def create_some_player(house_config, money_amount=0, is_connected=True, lobby=None):
    user = create_user(house_config, str(random.uniform(1000, 10000)), money_amount)
    return create_player(user, is_connected, lobby)
