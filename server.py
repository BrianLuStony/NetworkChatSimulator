import queue
import random
import sys
import getopt
import socket
import util
import threading
class Server:
    def __init__(self, dest, port, window):
        self.server_addr = dest
        self.server_port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.settimeout(None)
        self.sock.bind((self.server_addr, self.server_port))

        self.username_to_address = {}
        self.address_to_username = {}
        self.connection_state = {} 
        self.stop_event = threading.Event()
        self.ack_queue = queue.Queue()

    def start(self):
        while True:
            data, client_address = self.sock.recvfrom(2048)
            decoded_data = data.decode()
            typeofP, seqno, info, checksum = util.parse_packet(decoded_data)
            parts = info.split()
            if typeofP == "start":
                if util.validate_checksum(decoded_data):
                    self.connection_state[client_address] = {"expected_seq_num": int(seqno) + 1, "message_chunks": [],"ack_queue": queue.Queue()}
                    ack_packet = util.make_packet("ack", int(seqno), "")
                    self.sock.sendto(ack_packet.encode(), client_address)
            elif typeofP == "data":
                try:
                    msg_type = parts[0]
                    msg_len = int(parts[1])
                except IndexError:
                    print("Index error part is", parts)
                if util.validate_checksum(decoded_data):
                    if msg_type == "join":
                        username = parts[2]
                        if len(self.username_to_address) >= util.MAX_NUM_CLIENTS:
                            msg = util.make_message("ERR_SERVER_FULL", 1, username)
                            packet = util.make_packet("ack", int(seqno), msg)
                            self.sock.sendto(packet.encode(), client_address)
                            print("Disconnected: server full")
                        elif username in self.username_to_address:
                            msg = util.make_message("ERR_USERNAME_UNAVAILABLE", 1, username)
                            packet = util.make_packet("ack", int(seqno), msg)
                            self.sock.sendto(packet.encode(), client_address)
                            print("Disconnected: username not available")
                        else:
                            ack_packet = util.make_packet("ack", int(seqno), "")
                            self.sock.sendto(ack_packet.encode(), client_address)
                            self.username_to_address[username] = client_address
                            self.address_to_username[client_address] = username
                            # self.connection_state[client_address] = {"ack_queue": queue.Queue()}
                            print(f"join: {username}")
                    elif msg_type == "disconnect":
                        ack_packet = util.make_packet("ack", int(seqno), "")
                        self.sock.sendto(ack_packet.encode(), client_address)
                        username = self.address_to_username.get(client_address, "Unknown")
                        del self.address_to_username[client_address]
                        del self.username_to_address[username]
                        print(f"disconnected: {username}")
                    elif msg_type == "request_users_list":
                        usernames = ' '.join(sorted(self.username_to_address.keys()))
                        msg = util.make_message("response_users_list", 3, usernames)
                        client_thread = threading.Thread(target=self.handle_request_users_list, args=(client_address, msg , int(seqno)))  # Pass ack_queue
                        client_thread.start()
                        print(f"request_users_list: {self.address_to_username.get(client_address, 'Unknown')}")
                        ack_packet = util.make_packet("ack", int(seqno), "")
                        self.sock.sendto(ack_packet.encode(), client_address)
                    elif msg_type == "send_message":
                        sender_name = self.address_to_username[client_address]
                        print(f"msg: {sender_name}")
                        recipients_count = int(parts[3])
                        recipients = parts[4:4 + recipients_count]
                        message_content = ' '.join(parts[4 + recipients_count:])
                        connection_state = self.connection_state.get(client_address)
                        if connection_state:
                            expected_seq_num = connection_state["expected_seq_num"]
                            if int(seqno) == expected_seq_num:
                                connection_state["message_chunks"].append((sender_name, message_content))
                                connection_state["expected_seq_num"] += 1
                                ack_packet = util.make_packet("ack", int(seqno), "")
                                self.sock.sendto(ack_packet.encode(), client_address)
                            continue
                        else:
                            print("Packet dropped: Checksum mismatch")
            elif typeofP == "end":
                if util.validate_checksum(decoded_data):
                    if parts[0] == "send_message":
                        ack_packet = util.make_packet("ack", int(seqno), "")
                        self.sock.sendto(ack_packet.encode(), client_address)
                        connection_state = self.connection_state.get(client_address)
                        if connection_state:
                            connection_state["end_packet_received"] = True
                            if connection_state.get("message_chunks"):
                                # Forward the message chunks
                                sender_name = self.address_to_username[client_address]
                                recipient_chunks = []
                                for recipient in recipients:
                                    recipient_address = self.username_to_address.get(recipient)
                                    if recipient_address:
                                        recipient_chunks.append((recipient, recipient_address))
                                    else:
                                        print(f"msg: {sender_name} to non-existent user {recipient}")

                                # Spawn a thread for each recipient to forward the message chunks
                                for recipient, recipient_address in recipient_chunks:
                                    client_thread = threading.Thread(target=self.forward_message_chunks, args=(connection_state["message_chunks"], recipient_address))
                                    client_thread.start()
                    else:
                        error_packet = util.make_packet("ack", int(seqno), "")
                        self.sock.sendto(error_packet.encode(), client_address)
            elif typeofP == "ack":
                self.handle_ack(client_address, int(seqno))
    
    def forward_message_chunks(self, message_chunks, recipient_address):
        connection_state = self.connection_state[recipient_address]
        ack_queue = connection_state.get("ack_queue")

        if not ack_queue:
            print(f"No ack_queue found for client {recipient_address}")
            return
        
        # Send start packet
        start_seq_num = random.randint(1, 1000)
        start_packet = util.make_packet("start", start_seq_num, "")
        self.sock.sendto(start_packet.encode(), recipient_address)

        # Wait for acknowledgment for the start packet
        ack_received = False
        retries = 0
        while not ack_received and retries < 3:
            try:
                ack = ack_queue.get(timeout=util.TIME_OUT)
                if ack == start_seq_num:
                    ack_received = True
            except queue.Empty:
                # Handle timeout by retransmitting the packet
                self.sock.sendto(start_packet.encode(), recipient_address)
                retries += 1
        if not ack_received:
            print(f"Failed to receive ACK for start packet {start_seq_num}. Retries exhausted.")

        seq_num = start_seq_num
        # Iterate through each chunk and forward them
        for sender, chunk in message_chunks:
            seq_num = seq_num + 1
            msg = util.make_message("forward_message", 4, sender + " " + chunk)
            packet = util.make_packet("data", seq_num, msg)
            self.sock.sendto(packet.encode(), recipient_address)

            # Wait for ACK
            ack_received = False
            retries = 0
            while not ack_received and retries < 3:
                try:
                    ack = ack_queue.get(timeout=util.TIME_OUT)
                    if ack == seq_num:
                        ack_received = True
                except queue.Empty:
                    # Handle timeout by retransmitting the packet
                    self.sock.sendto(packet.encode(), recipient_address)
                    retries += 1

            if not ack_received:
                print(f"Failed to receive ACK for packet {seq_num}. Retries exhausted.")

        end_packet = util.make_packet("end", seq_num, msg)
        self.sock.sendto(end_packet.encode(), recipient_address)

        # Wait for acknowledgment for the start packet
        ack_received = False
        retries = 0
        while not ack_received and retries < 3:
            try:
                ack = ack_queue.get(timeout=util.TIME_OUT)
                if ack == seq_num:
                    ack_received = True
            except queue.Empty:
                # Handle timeout by retransmitting the packet
                self.sock.sendto(end_packet.encode(), recipient_address)
                retries += 1
        if not ack_received:
            print(f"Failed to receive ACK for start packet {start_seq_num}. Retries exhausted.")

    def handle_request_users_list(self, client_address, msg, seqno):
        # Update connection state with ack_queue
        if client_address not in self.connection_state:
            print(f"No connection state found for client {client_address}")
            return

        # Update connection state with ack_queue
        connection_state = self.connection_state[client_address]
        ack_queue = connection_state.get("ack_queue")

        if not ack_queue:
            print(f"No ack_queue found for client {client_address}")
            return
        
        # Send start packet
        start_seq_num = random.randint(1, 1000)
        start_packet = util.make_packet("start", start_seq_num, "")
        self.sock.sendto(start_packet.encode(), client_address)

        ack_received = False
        while not ack_received:
            try:
                ack = ack_queue.get(timeout=util.TIME_OUT)  # Convert to seconds
                if ack == start_seq_num:
                    ack_received = True
            except queue.Empty:
                # Handle timeout by retransmitting the START packet
                self.sock.sendto(start_packet.encode(), (self.server_addr, self.server_port))

        seq_num = start_seq_num + 1
        msg = util.make_message("response_users_list", 3, msg)
        packet = util.make_packet("data", seq_num, msg)
        self.sock.sendto(packet.encode(), client_address)

        ack_received = False
        retries = 0
        while not ack_received and retries < 3:
            try:
                ack = ack_queue.get(timeout=util.TIME_OUT)
                # print("Im waiting for ack for after sending the data for these tow", ack, seq_num)
                if ack == seq_num:
                    ack_received = True
            except queue.Empty:
                # Handle timeout by retransmitting the packet
                self.sock.sendto(packet.encode(), client_address)
                retries += 1


        end_packet = util.make_packet("end", seq_num+1, "")
        self.sock.sendto(end_packet.encode(), client_address)

        ack_received = False
        while not ack_received:
            try:
                ack = ack_queue.get(timeout=util.TIME_OUT)  # Convert to seconds
                if ack == seq_num+1:
                    ack_received = True
            except queue.Empty:
                # Handle timeout by retransmitting the START packet
                self.sock.sendto(end_packet.encode(), (self.server_addr, self.server_port))

        if not ack_received:
            print(f"Failed to receive ACK for packet {seq_num+1}. Retries exhausted.")

    def handle_ack(self, sender_address, ack_seq_num):
        sender_connection = self.connection_state.get(sender_address)
        if sender_connection:
            ack_queue = sender_connection.get("ack_queue")  # Retrieve ack_queue from connection_state
            if ack_queue:
                ack_queue.put(ack_seq_num)



if __name__ == "__main__":
    def helper():
        print("Server")
        print("-p PORT | --port=PORT The server port, defaults to 15000")
        print("-a ADDRESS | --address=ADDRESS The server ip or hostname, defaults to localhost")
        print("-w WINDOW | --window=WINDOW The window size, default is 3")
        print("-h | --help Print this help")

    try:
        OPTS, ARGS = getopt.getopt(sys.argv[1:],
                                   "p:a:w", ["port=", "address=","window="])
    except getopt.GetoptError:
        helper()
        exit()

    PORT = 15000
    DEST = "localhost"
    WINDOW = 3

    for o, a in OPTS:
        if o in ("-p", "--port="):
            PORT = int(a)
        elif o in ("-a", "--address="):
            DEST = a
        elif o in ("-w", "--window="):
            WINDOW = a

    SERVER = Server(DEST, PORT,WINDOW)
    try:
        
        SERVER.start()
    except (KeyboardInterrupt, SystemExit):
        exit()
