# NetworkChatSimulator

NetworkChatSimulator is a network chatting system simulation that initially starts with a basic UDP connection and later transitions to a TCP connection to ensure reliable communication.

## Features

- **UDP Connection**: Basic implementation without acknowledgment numbers, sequence numbers, or retransmissions.
- **TCP Connection**: Enhanced implementation to ensure all packets are received reliably.

## Commands

- `msg <user_count> <user1> <user2> ... <message>`: Send a message to specified users.
  - Example: `msg 2 Brian Kevin Hello World`
    - This command will send "Hello World" to both Brian and Kevin.

- `list`: Display all the users currently connected to the server.

- `help`: Display a list of all available commands.

- `quit`: Exit the application.

## Usage

1. **Send a Message**: 
   - Use the `msg` command followed by the number of users, the usernames of the recipients, and the message.
   - Example: `msg 2 Brian Kevin Hello World`

2. **List Users**:
   - Use the `list` command to see all connected users.

3. **Get Help**:
   - Use the `help` command to display all available commands.

4. **Quit**:
   - Use the `quit` command to exit the application.

## Getting Started

To start using NetworkChatSimulator, simply run the application and use the commands as described above to interact with the system and other users.
