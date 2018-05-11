# Commands to manage a server

# Lobby
AUTHORIZE_RESULT = 2
GOTO_LOBBY = 3  # needed to reset client back to lobby after server restart (without save)
UPDATE_SELF_USER_INFO = 4
LOBBY_INFO_LIST = 6
ROOMS_LIST = 9
ROOM_INFO = 12
# Room
GAME_INFO = 21
PLAYER_INFO = 23
CONFIRM_JOINED_THE_ROOM = 25
PLAYER_JOINED_THE_ROOM = 26
PLAYER_JOINED_THE_GAME = 28
PLAYER_LEFT_THE_GAME = 30
CONFIRM_LEFT_THE_ROOM = 32
PLAYER_LEFT_THE_ROOM = 33
ROOM_INVITATION_RECEIVED = 35
MESSAGE = 37
SHOW_MESSAGE_DIALOG = 38
LOG = 39
# Game
READY_TO_START = "40a"
RESET_GAME = 40
CHANGE_PLAYER_TURN = 41
SHOW_CASHBOX_DIALOG = 42
PLAYER_WINS = 43
PLAYER_WINS_THE_TOURNAMENT = 44
UPDATE1 = 52  # todo update_public
UPDATE2 = 53  # todo update_private
RAW_BINARY_UPDATE = 53

DESCRIPTION_BY_CODE = dict()
DESCRIPTION_BY_CODE[AUTHORIZE_RESULT] = "AUTHORIZE_RESULT"
DESCRIPTION_BY_CODE[GOTO_LOBBY] = "GOTO_LOBBY"
DESCRIPTION_BY_CODE[UPDATE_SELF_USER_INFO] = "UPDATE_SELF_USER_INFO"
DESCRIPTION_BY_CODE[LOBBY_INFO_LIST] = "LOBBY_INFO_LIST"
DESCRIPTION_BY_CODE[ROOMS_LIST] = "ROOMS_LIST"
DESCRIPTION_BY_CODE[ROOM_INFO] = "ROOM_INFO"

DESCRIPTION_BY_CODE[GAME_INFO] = "GAME_INFO"
DESCRIPTION_BY_CODE[PLAYER_INFO] = "PLAYER_INFO"
DESCRIPTION_BY_CODE[CONFIRM_JOINED_THE_ROOM] = "CONFIRM_JOINED_THE_ROOM"
DESCRIPTION_BY_CODE[PLAYER_JOINED_THE_ROOM] = "PLAYER_JOINED_THE_ROOM"
DESCRIPTION_BY_CODE[PLAYER_JOINED_THE_GAME] = "PLAYER_JOINED_THE_GAME"
DESCRIPTION_BY_CODE[PLAYER_LEFT_THE_GAME] = "PLAYER_LEFT_THE_GAME"
DESCRIPTION_BY_CODE[CONFIRM_LEFT_THE_ROOM] = "CONFIRM_LEFT_THE_ROOM"
DESCRIPTION_BY_CODE[PLAYER_LEFT_THE_ROOM] = "PLAYER_LEFT_THE_ROOM"
DESCRIPTION_BY_CODE[ROOM_INVITATION_RECEIVED] = "ROOM_INVITATION_RECEIVED"
DESCRIPTION_BY_CODE[MESSAGE] = "MESSAGE"
DESCRIPTION_BY_CODE[SHOW_MESSAGE_DIALOG] = "SHOW_MESSAGE_DIALOG"
DESCRIPTION_BY_CODE[LOG] = "LOG"

# TODO add to flash-client: READY_TO_START
DESCRIPTION_BY_CODE[READY_TO_START] = "READY_TO_START"
DESCRIPTION_BY_CODE[RESET_GAME] = "RESET_GAME"
DESCRIPTION_BY_CODE[CHANGE_PLAYER_TURN] = "CHANGE_PLAYER_TURN"
DESCRIPTION_BY_CODE[SHOW_CASHBOX_DIALOG] = "SHOW_CASHBOX_DIALOG"
DESCRIPTION_BY_CODE[PLAYER_WINS] = "PLAYER_WINS"
DESCRIPTION_BY_CODE[PLAYER_WINS_THE_TOURNAMENT] = "PLAYER_WINS_THE_TOURNAMENT"
DESCRIPTION_BY_CODE[UPDATE1] = "UPDATE1"
DESCRIPTION_BY_CODE[UPDATE2] = "UPDATE2"
DESCRIPTION_BY_CODE[RAW_BINARY_UPDATE] = "RAW_BINARY_UPDATE"
