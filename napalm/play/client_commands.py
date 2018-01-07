# Commands to manage a client

# Lobby
AUTHORIZE = 1  # todo change
UPDATE_SELF_USER_INFO = 4
GET_LOBBY_INFO_LIST = 5
# CHANGE_LOBBY = 7
GET_ROOMS_LIST = 8
FIND_FREE_ROOM = 10
GET_ROOM_INFO = 11
CREATE_PRIVATE_ROOM = 13
EDIT_PRIVATE_ROOM = 14
DELETE_PRIVATE_ROOM = 15
# Room
GET_GAME_INFO = 20
GET_PLAYER_INFO = 22
JOIN_THE_ROOM = 24
JOIN_THE_GAME = 27
LEAVE_THE_GAME = 29
LEAVE_THE_ROOM = 31
INVITE_FRIENDS_TO_ROOM = 34
SEND_MESSAGE = 36
# Game
RESET_GAME = 40  # ??
ACTION1 = 50
ACTION2 = 51
RAW_BINARY_ACTION = 55

DESCRIPTION_BY_CODE = dict()
DESCRIPTION_BY_CODE[AUTHORIZE] = "AUTHORIZE"
DESCRIPTION_BY_CODE[UPDATE_SELF_USER_INFO] = "UPDATE_SELF_USER_INFO"
DESCRIPTION_BY_CODE[GET_LOBBY_INFO_LIST] = "GET_LOBBY_INFO_LIST"
# DESCRIPTION_BY_CODE[CHANGE_LOBBY] = "CHANGE_LOBBY"
DESCRIPTION_BY_CODE[GET_ROOMS_LIST] = "GET_ROOMS_LIST"
DESCRIPTION_BY_CODE[FIND_FREE_ROOM] = "FIND_FREE_ROOM"
DESCRIPTION_BY_CODE[GET_ROOM_INFO] = "GET_ROOM_INFO"
DESCRIPTION_BY_CODE[CREATE_PRIVATE_ROOM] = "CREATE_PRIVATE_ROOM"
DESCRIPTION_BY_CODE[EDIT_PRIVATE_ROOM] = "EDIT_PRIVATE_ROOM"
DESCRIPTION_BY_CODE[DELETE_PRIVATE_ROOM] = "DELETE_PRIVATE_ROOM"

DESCRIPTION_BY_CODE[GET_GAME_INFO] = "GET_GAME_INFO"
DESCRIPTION_BY_CODE[GET_PLAYER_INFO] = "GET_PLAYER_INFO"
DESCRIPTION_BY_CODE[JOIN_THE_ROOM] = "JOIN_THE_ROOM"
DESCRIPTION_BY_CODE[JOIN_THE_GAME] = "JOIN_THE_GAME"
DESCRIPTION_BY_CODE[LEAVE_THE_GAME] = "LEAVE_THE_GAME"
DESCRIPTION_BY_CODE[LEAVE_THE_ROOM] = "LEAVE_THE_ROOM"
DESCRIPTION_BY_CODE[INVITE_FRIENDS_TO_ROOM] = "INVITE_FRIENDS_TO_ROOM"
DESCRIPTION_BY_CODE[SEND_MESSAGE] = "SEND_MESSAGE"

DESCRIPTION_BY_CODE[RESET_GAME] = "RESET_GAME"
DESCRIPTION_BY_CODE[ACTION1] = "ACTION1"
DESCRIPTION_BY_CODE[ACTION2] = "ACTION2"
DESCRIPTION_BY_CODE[RAW_BINARY_ACTION] = "RAW_BINARY_ACTION"