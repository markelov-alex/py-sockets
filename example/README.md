# Example of real Poker socket server application

Note: Current application cannot be downloaded and launched on your computer because the code concerning Poker functionality can not be published. 

This tiny example intended to demonstrate how small the application based on current framework could be. 

Here we can see that application's models and socket engines are separated and we can choose which to be used by CLI params. Here we have PokerLobbyModel, which does the poker game logic, and few ways to process sockets: using Twisted library (TwistedTCPServer) or using built-in python libraries (ThreadedTCPServer, NonBlockingTCPServer). Both, model and server engine, combined in SocketGameApplication instance.

All models and engines set up by external JSON files (see './server_data').
