# Socket server framework for games

This is my first project on Python and was made just for practise.

Current public version exposed only for demonstration purposes as a part of portfolio. Some code in methods of play/lobby.py was cut off.

This framework intended to be a substrate for game socket server of any kind: gambling, chess, match3, board and cards games, rendzu, go, etc. You just need to extend classes from package 'play', copying file names, and add there code specific for your game.

The base functionality and protocol, which is common for all kind of such games, have been already written. That includes lobby, room and user management, joining and quiting the room and a game. All the logic after joining the game is to be written.

The code of each game also can be extracted to own separate library. As a result the custom application could contain only few line of code combining right libraries to working application. All game configs should be in external JSON files placed in 'server_data/' directory.

Email: alex.panoptik [at] gmail.com
