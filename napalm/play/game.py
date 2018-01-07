import threading

from napalm.core import ExportableMixIn, ConfigurableMixIn
from napalm.play.protocol import MessageCode, GameID
from napalm.utils import object_util


class BaseGameConfig(ConfigurableMixIn):
    # Override
    @property
    def _config_property_name_list(self):
        return []

    @property
    def _game_id_lookup_list(self):
        # List here all classes which contain game_id constants available for current game
        return [GameID]

    @property
    def _game_type_lookup_list(self):
        # List here all classes which contain game_type constants available for current game
        return []

    def __init__(self, game_id, game_type=None, game_config_by_type=None):
        self.game_id = game_id
        self.game_type = game_type

        game_id_key = object_util.get_key_by_value(self.game_id, self._game_id_lookup_list)
        game_type_key = object_util.get_key_by_value(self.game_type, self._game_type_lookup_list)

        self.min_player_count_to_play = 2

        initial_config = {}
        if game_id_key and game_id_key in game_config_by_type:
            object_util.set_up_object(initial_config, game_config_by_type[game_id_key])
        if game_type_key and game_type_key in game_config_by_type:
            object_util.set_up_object(initial_config, game_config_by_type[game_type_key])
        # print("#########@@@@@initial_config", initial_config, "game_id_key:", game_id_key,
        #       "game_type_key:", game_type_key)
        super().__init__(initial_config)


# todo: what to do if you are the only player left and you also stand up before award was applied,
#       where does the award goes (answer: award should be applied immediately, but applying can be showed
#       a bit later)
class Game(ExportableMixIn):
    FIND_FREE_PLACE_IF_SPECIFIED_ONE_TAKEN = True

    @property
    def player_by_place_index_list(self):
        # Return cached value
        if self._player_by_place_index_list:
            return self._player_by_place_index_list

        self._player_by_place_index_list = [None] * (self.max_playing_count if self.max_playing_count > 0
                                                     else len(self._player_by_place_index))
        for place_index, player in self._player_by_place_index.items():
            self._player_by_place_index_list[place_index] = player
        return self._player_by_place_index_list

    # Override
    @property
    def _export_property_name_list(self):
        # (Always sync changes in client's code! - if _public_export_property_name_list uses this)
        return ["room_id", "_is_finished", "round_index", "player_in_turn_index",
                "prev_player_in_turn_index"]

    def __init__(self, room, game_config):
        self._room = room
        self.lobby_model = room.lobby_model
        self.room_model = room.room_model
        self.game_config = game_config

        self.room_id = self.room_model.room_id

        self.prev_time = 0
        # current_time = time.time()
        # print("__init__ TIMER", current_time, current_time - self.prev_time)

        # (I use separate variable for each timer use to find quickly needed timer in the code.
        # All timers cannot overlap, so only one variable can be used for all of them.)
        self._turn_timeout_timer = None
        self._end_round_timer = None
        # self._show_winner_timer = None
        self._end_game_timer = None

        self.max_playing_count = -1
        self.round_count = -1

        self.player_list = []
        self._player_by_place_index = {}
        self._player_by_place_index_list = None
        self._restarting_player_list = []

        # Game state
        self._is_finished = True

        self.round_index = 0
        self.player_in_turn_index = -1
        self.prev_player_in_turn_index = -1

        # Use in properties mentioned in self._public_export_property_name_list
        # to send only those data which available for specified player
        # (for example, some cards are shown and some are hidden).
        self.place_index_to_get_card_list_for = -1

    def dispose(self):
        print("G (dispose)", self)
        self.remove_all_players()

        self._room = None
        self.room_model = None
        self.player_list = None
        self._player_by_place_index = None
        self._player_by_place_index_list = None
        self._restarting_player_list = None

    def __repr__(self):
        return "<{0} room_id:{1} room_name:{2} place_count:{3} player_count:{4}>".format(
            self.__class__.__name__, self.room_model.room_id, self.room_model.room_name,
            len(self.player_by_place_index_list), len(self.player_list))

    def set_timeout(self, timeout, callback, name=None):
        if not callback:
            return None

        if timeout <= 0:
            print("G (set_timeout) call-now", "timeout:", timeout)
            callback()
            return None
        print("G (set_timeout) create-timer", "timeout:", timeout)
        timer = self.lobby_model.timer_class(timeout, 1, None, callback, True, name=name)
        timer.start()
        return timer

    def export_data(self, is_public=True, for_place_index=-1):
        self.place_index_to_get_card_list_for = for_place_index
        result = super().export_data(is_public)
        self.place_index_to_get_card_list_for = -1
        return result

    # Players

    def add_player(self, player, place_index=-1, money_in_play=0):
        if player in self.player_list:
            # Player could be already added if player rejoin the play buying more chips or
            # after client reconnection (on client or server restart or due network problems)
            print("G (add_player) Player is already added. Possibly restoring session or bought more chips. "
                  "player:", player)

            # On adding money in play in Cashier dialog
            if money_in_play:
                self._add_money_in_play(player, money_in_play)

            # Restore session on client reconnect
            self._room.send_player_joined_the_game(player)

            self._on_add_player(player)
            return True

        if self.max_playing_count < 0 or len(self.player_list) < self.max_playing_count:
            if place_index < 0 or (place_index in self._player_by_place_index and
                                   # self._player_by_place_index[place_index] and
                                   Game.FIND_FREE_PLACE_IF_SPECIFIED_ONE_TAKEN):
                place_index = self._find_free_place()
            if place_index < 0:
                print("G WARNING! (play.add_player) Cannot add player. The chosen place is not free place_index:",
                      place_index, "len(player_list):", len(self.player_list))
                return False

            print("G (add_player)", "player:", player, "place_index:", place_index, "money_in_play:", money_in_play)
            self._add_money_in_play(player, money_in_play)

            player.place_index = place_index
            player.game = self

            self._player_by_place_index[place_index] = player
            self.player_list.append(player)
            # (Clear cache)
            self._player_by_place_index_list = None
            print("G BEFORE sort player_list:", self.player_list)
            self.player_list.sort(key=lambda p: p.place_index)
            print("G     AFTER sort player_list:", self.player_list)

            self._room.send_player_joined_the_game(player)
            log_text = " ".join((player.first_name, player.last_name, "joined the play"))
            self._room.send_log(log_text)

            self._on_add_player(player)

            return True
        else:
            print("G WARNING! (add_player) Cannot add player. There is no free place in the play. "
                  "max_playing_count:", self.max_playing_count, "len(player_list):", len(self.player_list))
            player.protocol.show_ok_message_dialog(MessageCode.JOIN_GAME_FAIL_TITLE, MessageCode.JOIN_GAME_FAIL)
            return False

    def remove_player(self, player):
        print("G (remove_player)", player)
        if player in self.player_list:
            print("G  (remove_player)", "before-self.player_list:", self.player_list,
                  "self._player_by_place_index_list:", self._player_by_place_index_list)
            self._on_remove_player(player)

            # self._player_by_place_index[player.place_index] = None
            del self._player_by_place_index[player.place_index]
            self.player_list.remove(player)
            # (Clear cache)
            self._player_by_place_index_list = None

            self._room.send_player_left_the_game(player)

            player.game = None
            player.place_index = -1
            player.money_amount += player.money_in_play
            player.money_in_play = 0
            
            player.service.increase(player.money_in_play)
            player.protocol.update_self_user_info(player.export_data())
            print("G   (remove_player)", "after-self.player_list:", self.player_list,
                  "self.player_by_place_index_list:", self.player_by_place_index_list)

            self._check_end_game()

            return True
        else:
            print("G WARNING! (play.remove_player) Cannot remove player because it's not in player_list:",
                  self.player_list, "for player:", player)

        return False

    # Override
    def _on_add_player(self, player):
        # Start play
        # (Check is_connected - to avoid start_game() while restoring lobby after server restart)
        if player.is_connected and self._is_finished:
            self.check_start_game()

    # Override
    def _on_remove_player(self, player):
        pass

    def remove_all_players(self):
        for player in self.player_list:
            self.remove_player(player)

    def _find_free_place(self):
        # For infinite max_playing_count
        if self.max_playing_count < 0:
            index = 0
            while index in self._player_by_place_index:
                index += 1
            return index

        # For fixed max_playing_count
        for index in range(0, self.max_playing_count):
            if index not in self._player_by_place_index or not self._player_by_place_index[index]:
                return index

        # No free place for fixed max_playing_count
        return -1

    def _find_index_with_player(self, start_index, is_check_playing=True, is_money_in_play=True):
        # Returns start_index or next index of place with player
        index = start_index

        print("G temp (_find_index_with_player)", "start_index:", start_index, "checks:",
              is_check_playing, is_money_in_play, "self._player_by_place_index:", self._player_by_place_index)
        while index not in self._player_by_place_index or \
                (is_check_playing and not self._player_by_place_index[index].is_playing) or \
                (is_money_in_play and self._player_by_place_index[index].money_in_play <= 0):
            index += 1
            if index >= self.max_playing_count:
                print("G temp  (_find_index_with_player)", "index >= self.max_playing_count set-index=0. "
                      "index:", index, "self.max_playing_count:", self.max_playing_count)
                index = 0
            if index == start_index:
                print("G temp  (_find_index_with_player)", "index == start_index break")
                break  # return -1

        print("G temp  (_find_index_with_player)", "result index:", index)
        return index

    def _add_money_in_play(self, player, money_in_play=0):
        # print("temp(_add_money_in_play)", "player:", player, "money_in_play:", money_in_play,
        # "player.money_amount:", player.money_amount, "player.money_in_play:", player.money_in_play)
        money_in_play = min(money_in_play, player.money_amount)
        # (Check money_in_play>0 for restoring after server restart: player.money_in_play already set)
        if money_in_play > 0:
            player.money_amount -= money_in_play
            player.money_in_play += money_in_play
            
            player.service.decrease(money_in_play)
            print("  temp(_add_money_in_play)", "player:", player, "money_in_play:", money_in_play,
                  "player.money_amount:", player.money_amount, "player.money_in_play:", player.money_in_play)

    # Game

    def restart_game(self, player):
        # Restart play if it've been finished by now and all players wish to restart
        if self._is_finished:
            if player not in self._restarting_player_list:
                self._restarting_player_list.append(player)
                # todo send wish-to-restart message to all players

            if len(self.player_list) == len(self._restarting_player_list):
                self._restarting_player_list = []
                self.start_game()
        else:
            print("G WARNING! (play.restart_game) Cannot restart play because it's not finished yet. is_finished:",
                  self._is_finished)
    # --
    # def cancel_restart_game(self, player):
    #     if player in self._restarting_player_list:
    #         self._restarting_player_list.remove(player)
    #         # todo send cancel-wish-to-restart message to all players

    def restore_game(self):
        print("G (restore_game)", self)
        # todo start after 5 seconds, meanwhile show "restoring in x seconds..." dialog on clients connecting
        # (Restore last action after set_up(saved_data) after server restart)
        if self.player_list and self.player_in_turn_index != -1:
            self._start_player_turn(self.player_in_turn_index)

    def check_start_game(self):
        available_player_list = [player for player in self.player_list
                                 if player.money_in_play > self.room_model.max_stake]

        if self._is_finished and len(available_player_list) >= self.game_config.min_player_count_to_play:
            self.start_game()
            return True
        else:
            print("G (check_start_game) failed", "is_finished(t):", self._is_finished, "playing-player-count(>1):", len(available_player_list))
        return False

    # Template method
    def start_game(self):
        self._is_finished = False

        self._reset_game()

        self.on_start_game()

        # Start
        self._start_round(self.round_index)

    # Override
    def on_start_game(self):
        pass

    # Override
    def _reset_game(self):
        # (Reset all play params here)
        self.round_index = 0
        self.player_in_turn_index = -1
        self.prev_player_in_turn_index = -1

        for player in self.player_list:
            player.reset_game_state()
            # todo player.money_in_play > raise_step - else show cash dialog
            if player.is_connected:
                if player.money_in_play > self.room_model.max_stake:
                    player.is_playing = True
                else:
                    # show cashier dialog
                    pass

        self._room.send_reset_game()

    # Override
    def _start_next_round(self):
        self.round_index += 1
        print("G (_start_next_round)", "round_index:", self.round_index)
        self._apply_round(self.round_index)

        if not self._check_end_game():
            self._start_round(self.round_index)

    # Override
    def _start_round(self, round_index):
        print("G (_start_round)", "round_index:", round_index)

        # (Start play/play round here even if there is only one round in play)
        self._start_player_turn(self.player_in_turn_index)

    def _apply_round(self, round_index):
        pass

    # Override
    def _start_player_turn(self, player_in_turn_index):
        print("G (_start_player_turn)", "player_in_turn_index:", player_in_turn_index)
        # (It's possible to make play faster (if it's getting too long) cutting off the turn timeout)
        # todo send current timeout value
        self._room.send_change_player_turn(player_in_turn_index, self.room_model.turn_timeout_sec)
        # ?-if self._turn_timeout_timer:
        #     self._turn_timeout_timer.dispose()

        # (Set turn_timeout_sec <= 0 to do not call _end_turn() on time out)
        print("G  (_start_player_turn)", "turn_timeout_sec:", self.room_model.turn_timeout_sec)
        if self.room_model.turn_timeout_sec > 0:
            self._turn_timeout_timer = self.set_timeout(self.room_model.turn_timeout_sec, self.on_turn_timeout,
                                                        "turn_timeout")

    # (Player is making actions between _start_player_turn() and  _end_turn())

    def on_turn_timeout(self):
        print("G (on_turn_timeout)", "turn_timeout_sec:", self.room_model.turn_timeout_sec)
        # Default
        self._end_turn()

    # Template method (final)
    def _end_turn(self):
        if self._turn_timeout_timer:
            self._turn_timeout_timer.dispose()
            self._turn_timeout_timer = None

        self.prev_player_in_turn_index = self.player_in_turn_index
        self.player_in_turn_index = self._find_index_with_player(self.player_in_turn_index + 1)
        print("G (_end_turn)", "prev_player_in_turn_index:", self.prev_player_in_turn_index,
              "player_in_turn_index:", self.player_in_turn_index)

        # (In poker: for fold or all in actions (all in - always on money out))
        if self._check_end_game():
            return

        if self._check_end_round(self.player_in_turn_index, self.prev_player_in_turn_index):
            self._end_round()
            # Start next round or end the play
            self._end_round_timer = self.set_timeout(self.room_model.end_round_delay_sec, self._start_next_round,
                                                     "end_round")
            # self._start_next_round()
        else:
            self._start_player_turn(self.player_in_turn_index)

    # Override
    # Call self._end_round() from subclass
    def _check_end_round(self, player_in_turn_index, prev_player_in_turn_index):
        # By default there are no rounds (only one)
        return False

    # Override
    # (Note could be called twice on play end)
    def _end_round(self):
        # print("G (_end_round)", "prev-round_index:", self.round_index)
        pass

    # Override
    def _check_end_game(self):
        # If have been already ended
        if self._is_finished:
            print("G temp (_check_end_game) Have been already finished. False", "is_finished:", self._is_finished)
            return True

        # Ignore rounds if round_count=-1
        if self.round_index >= self.round_count >= 0:
            print("G temp (_check_end_game) Final round completed. True",
                  "round_index:", self.round_index, "round_count:", self.round_count)
            self._end_game()
            return True

        if len([player for player in self.player_list if player.is_playing]) <= 1:
            print("G temp (_check_end_game) No players left to play with. True")
            self._end_game()
            return True
        print("G temp (_check_end_game) Not ended yet (basic check). False")
        return False

    # Template method (final)
    # (Call only from _check_end_game())
    def _end_game(self, process_rounds_to_end=False):
        """Place where we find the winner (call _player_wins())"""

        print("G temp (_end_game)", "process_rounds_to_end:", process_rounds_to_end)
        self._is_finished = True

        self._end_round()

        # Process all rounds to the end (For case when there are no more money for bids)
        if process_rounds_to_end and self.round_count > -1:
            # print("G temp  (_end_game) process rounds to end", "round_index:", self.round_index,
            #       "round_count:", self.round_count)
            while self.round_index < self.round_count:
                self.round_index += 1
                self._apply_round(self.round_index)

        print("G GAME-END start thread:", threading.current_thread())
        self._find_winners(self._on_game_ended)

    # Override
    def _find_winners(self, on_complete=None):
        # (Default)
        if on_complete:
            on_complete()

    def _on_game_ended(self):
        print("G GAME-END end thread:", threading.current_thread())
        # Called from _find_winners()
        # Check enough money_in_play to continue
        for player in self.player_list:
            # Kick off disconnected players from play
            if not player.is_connected:
                player.dispose()
            elif player.money_in_play <= 0:
                self._player_no_money_in_play(player)

        print("G Delay before new game starts. end_round_delay_sec:", self.room_model.end_round_delay_sec)
        self._end_game_timer = self.set_timeout(self.room_model.end_round_delay_sec, self._on_game_finished, "end_game")
        # self.check_start_game()

    def _on_game_finished(self):
        # Called after game end and some delay to see the result.
        # After game finished it should be reset
        if not self.check_start_game():
            self._reset_game()

    def _player_no_money_in_play(self, player):
        # Then rejoin the play with money added
        player.protocol.show_cashbox_dialog(player.place_index)

    def _send_player_wins(self, player, money_win, is_tournament=False):
        if is_tournament:
            self._room.send_player_wins_the_tournament(player.place_index, money_win)
        else:
            self._room.send_player_wins(player.place_index, money_win, player.money_in_play)

    # Protocol process methods (Room)

    def get_player_info(self, asking_player, place_index):
        player = self._player_by_place_index[place_index]
        asking_player.protocol.player_info(place_index, player.export_data() if player else None)

    def get_all_player_info(self, asking_player):
        for place_index in self._player_by_place_index:
            player = self._player_by_place_index[place_index]
            # ? if player != asking_player:
            asking_player.protocol.player_info(place_index, player.export_data() if player else None)

    # Protocol process methods (Game)

    # ...
    def action1(self, params_list):
        # Reserved
        pass

    def action2(self, params_list):
        # Reserved
        pass

    def process_raw_binary_action(self, raw_binary):
        # Reserved
        pass
