import logging

import time

from napalm.async import AbstractTimer
from napalm.core import ExportableMixIn, ReloadableMultiModel
from napalm.play.protocol import MessageCode


# Model

class GameConfigModel(ReloadableMultiModel):
    # (Loaded changes take effect only after apply_changes() called)
    is_change_on_command = True

    # Game config

    is_find_free_place_if_specified_one_taken = True
    # (True for games like Monopoly, False - for Poker)
    is_join_only_between_games = False
    is_start_tournament_only_if_full = True
    # (True for Poker, False - for Monopoly)
    is_reset_on_game_finish = True
    # (If greater than max_player_count, the latter will be used instead)
    min_players_to_start = 2
    is_sit_out_enabled = False
    is_sit_out_after_missed_turn = True
    kick_off_after_missed_turns_count = 2
    kick_off_after_sit_out_games_count = 2
    is_divide_same_pot_simultaneously = True

    bet_step = 1

    # Override
    @property
    def _config_property_names(self):
        # Note: game_config_model should not have id
        return ["is_find_free_place_if_specified_one_taken",
                "is_join_only_between_games", "is_reset_on_game_finish", "min_players_to_start",
                "is_sit_out_enabled", "is_sit_out_after_missed_turn",
                "kick_off_after_missed_turns_count", "kick_off_after_sit_out_games_count",
                "bet_step"]


# Game

class GamePlayerManagerMixIn:
    # (Dependencies)
    logging = None
    room = None
    room_model = None
    game_config_model = None
    _is_in_progress = None
    # _check_end_game = None
    # is_tournament = None

    @property
    def max_player_count(self):
        return self.room_model.max_player_count if self.room_model else -1

    @property
    def player_by_place_index_list(self):
        # Return cached value
        if self._player_by_place_index_list:
            return self._player_by_place_index_list

        max_place_index = self.max_player_count if self.max_player_count > 0 \
            else max(self._player_by_place_index.keys(), default=0)
        self._player_by_place_index_list = [None] * max_place_index
        for place_index, player in self._player_by_place_index.items():
            self._player_by_place_index_list[place_index] = player
        return self._player_by_place_index_list

    def __init__(self):
        self.player_list = []
        self._player_by_place_index = {}
        # (Must be generated for infinite max_player_count (-1))
        self._player_by_place_index_list = None
        self._ready_to_start_players = []

    def dispose(self):
        self._remove_all_players()

        self.player_list.clear()
        self._player_by_place_index.clear()
        self._player_by_place_index_list = None
        self._ready_to_start_players.clear()

    # Players

    def can_be_added(self, player, place_index=-1, money_in_play=0):
        """Can be used in lobby to avoid joining the room where you couldn't play"""

        # Check already added and is restoring now
        if player.place_index >= 0:
            return True

        # Check place
        if place_index >= 0 and place_index in self._player_by_place_index and \
                not self.game_config_model.is_find_free_place_if_specified_one_taken:
            return False
        # Check money_in_play
        if 0 <= self.room_model.min_buy_in > money_in_play:
            return False

        # Check joining during game (can't join for long games, like Monopoly)
        if self.game_config_model.is_join_only_between_games and self._is_in_progress:
            return False

        # Check max_player_count
        result = self.max_player_count < 0 or len(self.player_list) < self.max_player_count
        return result

    # (todo in future: use room.join_the_room/game, not room/game.add_player; lobby.join... acts only as a proxy)
    def add_player(self, player, place_index=-1, money_in_play=0):
        """
        Used for:
        - joining the game;
        - add more money in play;
        - restoring player in game after server restart.
        :param player:
        :param place_index:
        :param money_in_play:
        :return:
        """

        # On rebuy or reconnect
        if player in self.player_list:
            self.logging.debug("G (add_player) Player is already added. Possibly restoring "
                               "session or bought more chips. player: %s", player)
            # Change place
            if place_index >= 0 and place_index != player.place_index and \
                    place_index not in self._player_by_place_index:
                del self._player_by_place_index[player.place_index]
                self._player_by_place_index[place_index] = player
                player.place_index = place_index
                # (Clear cache)
                self._player_by_place_index_list = None

            # On adding money in play in Cashier dialog
            if money_in_play > 0:
                # self._add_money_in_play(player, money_in_play)
                player.add_money_in_play(money_in_play)

            # Restore session on client reconnect
            self.room.send_player_joined_the_game(player)

            self._on_add_player(player)
            return True

        # (If restoring player in game)
        if place_index < 0:
            place_index = player.place_index
        # --- if not money_in_play and player.money_in_play:
        #     money_in_play = player.money_in_play

        if not self.can_be_added(player, place_index, money_in_play):
            self.logging.warning("G WARNING! (add_player) Player can not be added. %s "
                                 "max_player_count: %s len(player_list): %s",
                                 player, self.max_player_count, len(self.player_list))
            player.protocol.show_ok_message_dialog(MessageCode.JOIN_GAME_FAIL_TITLE, MessageCode.JOIN_GAME_FAIL)
            return False

        if place_index < 0 or (place_index in self._player_by_place_index and
                               self.game_config_model.is_find_free_place_if_specified_one_taken):
            place_index = self._find_free_place_index(place_index)
        if place_index < 0 or place_index in self._player_by_place_index:
            self.logging.warning("G WARNING! (game.add_player) Cannot add player. "
                                 "The chosen place is not free. place_index: %s len(player_list): %s",
                                 place_index, len(self.player_list))
            return False

        self.logging.debug("G (add_player) player: %s place_index: %s money_in_play: %s",
                           player, place_index, money_in_play)

        player.place_index = place_index
        player.game = self

        player.add_money_in_play(money_in_play)

        self._player_by_place_index[place_index] = player
        self.player_list.append(player)
        # (Clear cache)
        self._player_by_place_index_list = None
        # self.logging.debug("G BEFORE sort player_list: %s", self.player_list)
        self.player_list.sort(key=lambda p: p.place_index)
        # self.logging.debug("G     AFTER sort player_list: %s", self.player_list)
        self.room_model.playing_count = len(self.player_list)

        self.room.send_player_joined_the_game(player)
        log_text = " ".join((player.first_name, player.last_name, "joined the game"))
        self.room.send_log(log_text)

        self._on_add_player(player)

        return True

    def remove_player(self, player):
        self.logging.debug("G (remove_player) %s", player)
        if player not in self.player_list:
            self.logging.warning("G WARNING! (play.remove_player) Cannot remove player because it's not in "
                                 "player_list: %s for player: %s", self.player_list, player)

            return False

        self.logging.debug("G  (remove_player) before-self.player_list: %s self._player_by_place_index_list: %s",
                           self.player_list, self._player_by_place_index_list)
        self._on_remove_player(player)

        # self._player_by_place_index[player.place_index] = None
        del self._player_by_place_index[player.place_index]
        self.player_list.remove(player)
        if player in self._ready_to_start_players:
            self._ready_to_start_players.remove(player)
        # (Clear cache)
        self._player_by_place_index_list = None

        self.room_model.playing_count = len(self.player_list)

        self.room.send_player_left_the_game(player)

        log_text = " ".join((player.first_name, player.last_name, "left the game"))
        self.room.send_log(log_text)

        player.game = None
        player.place_index = -1
        player.is_playing = False

        player.remove_money_in_play()
        # player.protocol.update_self_user_info(player.export_public_data())

        self.logging.debug("G   (remove_player) after-self.player_list: %s self.player_by_place_index_list: %s",
                           self.player_list, self.player_by_place_index_list)

        self._check_end_game()

        return True

    def _remove_all_players(self):
        # (list() makes a copy to iterate through while items removing)
        for player in list(self.player_list):
            self.remove_player(player)

    def _remove_all_players_from_room(self):
        for player in self.player_list:
            # or go to lobby??
            self.room.remove_player(player)

    # Override
    def _on_add_player(self, player):
        pass

    # Override
    def _on_remove_player(self, player):
        pass

    def _find_free_place_index(self, start_index=-1):
        if not self.max_player_count:
            return -1

        start_index = max(0, start_index)
        if self.max_player_count > 0:
            start_index = start_index % self.max_player_count
        index = start_index if self.max_player_count > 0 else 0
        while index in self._player_by_place_index:
            index += 1
            if index >= self.max_player_count:
                index = 0
            if index == start_index:
                return -1
        return index

        # For fixed max_player_count
        for index in range(0, self.max_player_count):
            if index not in self._player_by_place_index or not self._player_by_place_index[index]:
                return index

        # No free place for fixed max_player_count
        return -1

    def _find_nearest_right_hand_player_to(self, start_index, check_is_playing=True):  # , is_check_playing=True, is_money_in_play=True):
        """Returns start_index or next index of place with player"""
        # -start_index = max([0, min([start_index, self.max_player_count - 1])])
        if start_index >= self.max_player_count or start_index < 0:
            start_index = 0
        index = start_index

        # self.logging.debug("G temp (_find_nearest_right_hand_player_to) start_index: %s checks: %s %s "
        #                    "self._player_by_place_index: %s", start_index, is_check_playing, is_money_in_play,
        #                    self._player_by_place_index)
        # while index not in self._player_by_place_index or \
        #         (is_check_playing and not self._player_by_place_index[index].is_playing) or \
        #         (is_money_in_play and self._player_by_place_index[index].money_in_play <= 0):
        while index not in self._player_by_place_index or \
                (check_is_playing and not self._player_by_place_index[index].is_playing) or \
                self._player_by_place_index[index].money_in_play <= 0 or \
                self._player_by_place_index[index].is_sit_out:
            index += 1
            if index >= self.max_player_count:
                # self.logging.debug("G temp  (_find_nearest_right_hand_player_to) index >= self.max_player_count set-index=0. "
                #                    "index: %s self.max_player_count: %s", index, self.max_player_count)
                index = 0
            if index == start_index:
                # self.logging.debug("G temp  (_find_nearest_right_hand_player_to) index == start_index break")
                return -1
                # break

        # self.logging.debug("G temp  (_find_nearest_right_hand_player_to) result index: %s", index)
        return index


# todo? what to do if you are the only player left and you also have stood up before award was applied,
#       where does the award goes (answer: award should be applied immediately, but applying can be showed
#       a bit later)
class Game(GamePlayerManagerMixIn, ExportableMixIn):
    """
    Logic based on:
    - Zynga Poker https://apps.facebook.com/texas_holdem/
    - Business Tour (Monopoly) https://minigames.mail.ru/monopolia
    - Hockey Stars http://www.agame.com/game/hockey-stars, https://play.google.com/store/apps/details?id=com.miniclip.hockeystars
    """
    logging = None

    # Save/Restore

    # Override
    @property
    def _property_names(self):
        # (Always sync changes in client's code! - if _public_property_names uses this)
        return ["room_id", "_is_in_progress", "_is_paused", "game_elapsed_time"]

    @property
    def room_id(self):
        return self.room_model.room_id if self.room_model else None

    @property
    def game_elapsed_time(self):
        return self._game_timer.get_elapsed_time()

    @game_elapsed_time.setter
    def game_elapsed_time(self, value):
        self._game_timer.elapsed_time = value

    # State

    @property
    def is_in_progress(self):
        return self._is_in_progress

    @property
    def is_paused(self):
        return self._is_paused or self._is_resuming_pause

    @property
    def _start_countdown_sec(self):
        player_count = len(self.player_list)

        if player_count < self.game_config_model.min_players_to_start:
            return -1
        all_ready = player_count == len(self._ready_to_start_players)
        start_countdown_sec = self.room_model.start_game_countdown_sec \
            if all_ready else self.room_model.waiting_for_other_players_countdown_sec
        # (max() - if waiting_for_other_players_countdown_sec < start_game_countdown_sec)
        return max(start_countdown_sec, self.room_model.start_game_countdown_sec)

    @property
    def _is_game_can_be_started(self):
        # ?min_players_to_start = min(self.game_config_model.min_players_to_start, self.max_player_count)
        min_players_to_start = self.game_config_model.min_players_to_start
        return not self._is_in_progress and not self._is_showing_winners and \
               len(self._available_player_list) >= min_players_to_start

    @property
    def _available_player_list(self):
        return [player for player in self.player_list if player.money_in_play > 0]

    def __init__(self, room):
        self.logging = logging.getLogger("GAME")

        self.room = room if room else None
        """:type: Room"""
        self.house_config = room.house_config if room else None
        self.room_model = room.room_model if room else None
        self.game_config_model = self.room_model.game_config_model if self.room_model else None

        # Timers
        self._start_game_timer = self.create_timer()
        self._resume_game_timer = self.create_timer()
        self._game_timer = self.create_timer()
        self._show_game_winner_timer = self.create_timer()
        self._rebuying_timers = []

        # State
        # todo replace with self._is_in_progress = False
        self._is_in_progress = False
        self._is_showing_winners = False
        self._is_paused = False
        self._is_resuming_pause = False

        GamePlayerManagerMixIn.__init__(self)
        ExportableMixIn.__init__(self)

    def dispose(self):
        if self.logging:
            self.logging.debug("G (dispose) %s", self)
        self._return_bets()

        self._is_in_progress = False
        # To stop all timers
        # self._reset_game()
        if self.room_model:  # Some properties got by getattr() fail without models after dispose() was called
            for attr in dir(self):
                value = getattr(self, attr)
                if isinstance(value, AbstractTimer):
                    value.dispose()

        # Remove all players first
        GamePlayerManagerMixIn.dispose(self)

        # (list() needed to make a copy - just a best practice)
        for timer in list(self._rebuying_timers):
            timer.dispose()
        self._rebuying_timers.clear()

        self.room = None
        self.house_config = None
        self.room_model = None
        self.game_config_model = None

        # self.logging = None

    def __repr__(self):
        if not self.room_model:
            return super().__repr__()
        return "<{0} room_id:{1} room_name:{2} place_count:{3} player_count:{4}>".format(
            self.__class__.__name__, self.room_model.room_id, self.room_model.room_name,
            len(self.player_by_place_index_list), len(self.player_list))

    def export_public_data_for(self, for_place_index=-1):
        return self.export_public_data()

    # todo unittests
    def check_and_apply_changes(self):
        # Can be applied only between games
        if not self._is_in_progress and self.game_config_model \
                and self.game_config_model.is_changed:
            # Apply
            self.game_config_model.apply_changes()
            # -# Inform about
            # for player in self.room.player_set:
            #     self.room.get_game_info(player)

    # Start

    def _on_add_player(self, player):
        super()._on_add_player(player)

        # Start play
        # (Checking is_connected to avoid _start_game() while restoring lobby after server restart)
        if player.is_connected and not self._is_in_progress:
            self._refresh_starting_game(player)

    def _on_remove_player(self, player):
        super()._on_remove_player(player)

        # - Wrong behavior; cause starting game on dispose
        # self._refresh_starting_game(player)
        # -? (_on_remove_player() called before player removed)
        # self._check_end_game()

    def ready_to_start(self, player, is_ready=True):
        """Called on player pressed "Ready" button"""
        # Restart play if it've been finished by now and all players wish to restart
        if not self._is_in_progress and not self._is_showing_winners:
            # Add/remove
            if is_ready and player not in self._ready_to_start_players:
                self._ready_to_start_players.append(player)
            elif not is_ready and player in self._ready_to_start_players:
                self._ready_to_start_players.remove(player)
            else:
                return

            # Refresh
            self._refresh_starting_game(player)
        else:
            self.logging.warning("G WARNING! (play.restart_game) Cannot restart play (because it's "
                                 "not finished yet). is_in_progress: %s", self._is_in_progress)

    def _refresh_starting_game(self, changed_player=None):
        if self._is_in_progress or self._is_showing_winners:
            return

        self._check_start_game()

        # todo? check _is_in_progress
        is_ready_to_start_enabled = self.room_model.waiting_for_other_players_countdown_sec > 0
        if changed_player and is_ready_to_start_enabled:
            is_ready = changed_player in self._ready_to_start_players
            self.room.send_ready_to_start(changed_player.place_index, is_ready, self._start_countdown_sec)

    def _check_start_game(self):
        # available_player_list = [player for player in self.player_list
        #                          if player.money_in_play > self.room_model.max_stake]
        # available_player_list = [player for player in self.player_list if player.money_in_play > 0]

        # Check min_players_to_start
        if self._is_game_can_be_started:
            start_countdown_sec = self._start_countdown_sec
            # print("Start game", ("after %f sec" % start_countdown_sec) if start_countdown_sec > 0 else "")
            if start_countdown_sec <= 0:
                self._start_game()
            else:
                self._start_game_timer.restart(self._start_game, start_countdown_sec)
            return True

        # (For example, some players went out before start_game_timer complete)
        self._start_game_timer.stop()
        # self.logging.debug("G (_check_start_game) failed is_in_progress(t): %s playing-player-count(>1): %s",
        #                    self._is_in_progress, len(available_player_list))
        return False

    def _start_game(self):
        """Template method. Called only once per game."""
        if self._is_in_progress or self._is_showing_winners:
            return

        self._reset_game()

        # Set is_playing
        playing_count = 0
        for player in self.player_list:
            if player.is_connected and not player.is_sit_out:
                if player.money_in_play > 0 or self.room_model.min_buy_in <= 0:
                    player.is_playing = True
                    playing_count += 1

        # Check it's enough available players to start game
        if playing_count < self.game_config_model.min_players_to_start:
            # todo check: player_list or available_player_list
            for player in self.player_list:
                player.is_playing = False
            # self.logging.debug("Not enough available players to start the game")
            return

        # Start
        self._is_in_progress = True

        self._on_start_game()

        # Start game timer (only of > 0)
        self._game_timer.is_start_zero_delay = False
        self._game_timer.start(self._on_game_timeout, self.room_model.game_timeout_sec)

    # Override
    def _on_start_game(self):
        """Important! Can be called multiple times during a game, so it should be
        idempotent(?), not making game state changes, but only indicate (send to
        client) current game state"""
        pass

    # Override
    def _reset_game(self):
        self._start_game_timer.reset()
        self._resume_game_timer.reset()
        self._game_timer.reset()
        self._show_game_winner_timer.reset()

        self._is_showing_winners = False
        self._is_paused = False
        self._is_resuming_pause = False

        # (Reset all play params here)
        self._ready_to_start_players.clear()

        for player in self.player_list:
            player.reset_game_state()

        # todo add to unittests
        if self.room:
            self.room.check_and_apply_changes()
        self.check_and_apply_changes()

        # Send
        if self.room:
            self.room.send_reset_game()

    # Pause/resume

    def pause_game(self):
        if not self._is_paused and self._is_in_progress:
            self._is_paused = True
            self._do_pause_game()

    def resume_game(self):
        if self._is_paused and self._is_in_progress:
            self._is_paused = False
            resume_delay_sec = self.room_model.resume_game_countdown_sec
            if resume_delay_sec > 0:
                # (To send delay seconds to start countdown on client)
                self.room.send_pause_game(False, resume_delay_sec)
                self._is_resuming_pause = True
                self._resume_game_timer.restart(self._do_resume_game, resume_delay_sec)
            else:
                self._do_resume_game()

    # Override
    def _do_pause_game(self):
        # All timers should be paused here
        self._start_game_timer.pause()
        self._resume_game_timer.pause()
        self._game_timer.pause()
        self._show_game_winner_timer.pause()

        self.room.send_pause_game(True)

    # Override
    def _do_resume_game(self):
        self._is_resuming_pause = False

        self.room.send_pause_game(False)

        # All timers should be resumed here (For restoring, start() also should be called)
        self._start_game_timer.resume()
        self._resume_game_timer.resume()
        self._game_timer.resume()
        self._show_game_winner_timer.resume()

        self._on_resume_game()

    def _on_resume_game(self):
        """Called in two cases:
        1) after server restarted and restored;
        2) on resume after pause.
        Should initiate client if just restored, or updates client (especially
        its timers) if resuming after pause by sending appropriate commands"""

        self._on_start_game()

    # End

    # Override
    def _check_end_game(self):
        # If have been already ended
        if not self._is_in_progress:
            self.logging.debug("G temp (_check_end_game) Have been already finished. False is_in_progress: %s",
                               self._is_in_progress)
            return True

        # Only 1 (or 0) player left in playing in game
        if len([player for player in self.player_list if player.is_playing]) <= 1:
            self.logging.debug("G temp (_check_end_game) No players left to play with. True")
            self._end_game()
            return True

        self.logging.debug("G temp (_check_end_game) Not ended yet (basic check). False")
        return False

    def _on_game_timeout(self):
        self._end_game()

    # (Call only from _check_end_game())
    def _end_game(self):  # , process_rounds_to_end=False):
        """Template method (final)"""
        if not self._is_in_progress:
            return

        # self.logging.debug("G temp (_end_game) process_rounds_to_end: %s", process_rounds_to_end)
        # (Should be false to disable all player actions and enable showing and mucking cards, etc)
        self._is_showing_winners = True  # todo add unittests
        self._is_in_progress = False

        self._find_game_winners(self._on_end_game)

    # Override
    def _find_game_winners(self, on_complete=None):
        """Place where we find the winner and give award (use send_player_wins())"""
        # (Default)
        if self.room_model.show_game_winner_delay_sec > 0:
            self._show_game_winner_timer.restart(on_complete, self.room_model.show_game_winner_delay_sec)
        else:
            on_complete()

    def _on_end_game(self):
        # Check enough money_in_play to continue
        for player in self.player_list:
            if player.money_in_play <= 0:
                self._player_no_money_in_play(player)

        self._is_showing_winners = False  # todo add unittests

        # Try to start new game
        is_new_game_started = self._check_start_game()

        # (Reset on game finish while waiting for new game)
        if not is_new_game_started and self.game_config_model.is_reset_on_game_finish:
            self._reset_game()

    def _return_bets(self):
        """Return all pots to the bidders to terminate the game urgently"""
        pass

    # Send

    def send_player_wins(self, player, money_win, is_win_tournament=False):
        if is_win_tournament:
            self.room.send_player_wins_the_tournament(player.place_index, money_win)
        else:
            self.room.send_player_wins(player.place_index, money_win, player.money_in_play)

    def _player_no_money_in_play(self, player):
        # Then rejoin the play with money added
        player.protocol.show_cashbox_dialog()

        rebuying_timer = self.create_timer(self.rebuy_timeout, self.room_model.rebuying_sec)
        rebuying_timer.args = [rebuying_timer, player]
        self._rebuying_timers.append(rebuying_timer)
        rebuying_timer.start()

    # Start show_game_winner_timer to free place on timeout
    def rebuy_timeout(self, rebuying_timer, player):
        # Leave the game
        if player.money_in_play <= 0:
            self.remove_player(player)
        self._rebuying_timers.remove(rebuying_timer)

    def get_player_info(self, asking_player, place_index):
        # ? Which behavior is better?
        # player = self._player_by_place_index[place_index] if place_index in self._player_by_place_index else None
        # asking_player.protocol.player_info(place_index, player.export_public_data() if player else None)
        #
        # if place_index in self._player_by_place_index:
        #     player = self._player_by_place_index[place_index]
        #     asking_player.protocol.player_info(place_index, player.export_public_data() if player else None)
        #
        if place_index in range(self.max_player_count):
            player = self._player_by_place_index[place_index] if place_index in self._player_by_place_index else None
            asking_player.protocol.player_info(place_index, player.export_public_data() if player else None)

    def get_all_player_info(self, asking_player):
        for place_index, player in enumerate(self._player_by_place_index_list):
            # ? if player != asking_player:
            asking_player.protocol.player_info(place_index, player.export_public_data() if player else None)

    def action1(self, params_list):
        # Reserved
        pass

    def action2(self, params_list):
        # Reserved
        pass

    def process_raw_binary_action(self, raw_binary):
        # Reserved
        pass

    # Utility

    def create_timer(self, callback=None, delay_sec=0, args=None, name=None):
        timer = self.house_config.timer_class(callback, delay_sec, 1, args, name=name) if self.house_config else None
        return timer
