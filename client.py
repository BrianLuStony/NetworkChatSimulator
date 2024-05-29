'''
This module defines the behaviour of a client in your Chat Application
'''
import queue
import signal
import sys
import getopt
import socket
import random
from threading import Thread
import os
import threading
import time
import util


'''
Write your code inside this class. 
In the start() function, you will read user-input and act accordingly.
receive_handler() function is running another thread and you have to listen 
for incoming messages in this function.
'''

class Client:
    '''
    This is the main Client Class. 
    '''
    def __init__(self, username, dest, port, window_size):
        self.server_addr = dest
        self.server_port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(None)
        self.sock.bind(('', random.randint(10000, 40000)))
        self.name = username
        self.stop_event = threading.Event()
        self.ack_queue = queue.Queue()
        self.message_chunks = {}

    
    
    def start(self):
        '''
        Main Loop is here
        Start by sending the server a JOIN message. 
        Use make_message() and make_util() functions from util.py to make your first join packet
        Waits for userinput and then process it
        '''
        start_seq_num = random.randint(1, 1000)
        start_packet = util.make_packet("start", start_seq_num, "")
        self.sock.sendto(start_packet.encode(), (self.server_addr, self.server_port))

        ack_received = False
        while not ack_received:
            try:
                ack = self.ack_queue.get(timeout=util.TIME_OUT)  # Convert to seconds
                if ack == start_seq_num:
                    ack_received = True
            except queue.Empty:
                # Handle timeout by retransmitting the START packet
                self.sock.sendto(start_packet.encode(), (self.server_addr, self.server_port))


        seq_num = start_seq_num + 1
        join_message = util.make_message("join", 1, self.name)
        packet = util.make_packet("data",seq_num,join_message)
        ack_received = False
        retries = 0
        while not ack_received and retries < 3:  # Retry up to 3 times
            try:
                ack = self.ack_queue.get(timeout=util.TIME_OUT)
                if ack == seq_num:
                    ack_received = True
            except queue.Empty:
                # Handle timeout by retransmitting the packet
                self.sock.sendto(packet.encode(), (self.server_addr, self.server_port))
                retries += 1
        if not ack_received:
            print(f"Failed to receive ACK for packet {seq_num}. Retries exhausted.")

        # Send end packet
        end_packet = util.make_packet("end", seq_num + 1, join_message)
        self.sock.sendto(end_packet.encode(), (self.server_addr, self.server_port))

        ack_received = False
        while not ack_received:
            try:
                ack = self.ack_queue.get(timeout=util.TIME_OUT)  # Convert to seconds
                if ack == seq_num+1:
                    ack_received = True
            except queue.Empty:
                self.sock.sendto(end_packet.encode(), (self.server_addr, self.server_port))
        # Send the join message to the server
        
        try:
          while True:
                user_input = input("")

                if user_input.lower().startswith("msg"):
                    self.send_message(user_input)

                elif user_input.lower() == "list":
                    self.list_users()

                elif user_input.lower() == "help":
                    self.print_help()

                elif user_input.lower() == "quit":
                    disconnect_message = util.make_message("disconnect", 1, self.name)
                    start_seq_num = random.randint(1, 1000)  # Generate a random sequence number
                    start_packet = util.make_packet("start", start_seq_num, "")
                    self.sock.sendto(start_packet.encode(), (self.server_addr, self.server_port))

                    ack_received = False
                    while not ack_received:
                        try:
                            ack = self.ack_queue.get(timeout=util.TIME_OUT)  # Convert to seconds
                            if ack == start_seq_num:
                                ack_received = True
                        except queue.Empty:
                            # Handle timeout by retransmitting the START packet
                            self.sock.sendto(start_packet.encode(), (self.server_addr, self.server_port))

                    # Send disconnect message packet
                    seq_num = start_seq_num + 1
                    packet = util.make_packet("data", seq_num, disconnect_message)
                    self.sock.sendto(packet.encode(), (self.server_addr, self.server_port))

                    # Wait for ACK or handle retransmission
                    ack_received = False
                    retries = 0
                    while not ack_received and retries < 3:  # Retry up to 3 times
                        try:
                            # Get the ACK from the queue with a timeout
                            ack = self.ack_queue.get(timeout=util.TIME_OUT)
                            if ack == seq_num:
                                ack_received = True
                        except queue.Empty:
                            # Handle timeout by retransmitting the packet
                            self.sock.sendto(packet.encode(), (self.server_addr, self.server_port))
                            retries += 1
                    if not ack_received:
                        print(f"Failed to receive ACK for packet {seq_num}. Retries exhausted.")

                    # Send end packet
                    end_packet = util.make_packet("end", seq_num + 1, packet)
                    self.sock.sendto(end_packet.encode(), (self.server_addr, self.server_port))

                    ack_received = False
                    while not ack_received:
                        try:
                            ack = self.ack_queue.get(timeout=util.TIME_OUT)  # Convert to seconds
                            if ack == seq_num+1:
                                ack_received = True
                        except queue.Empty:
                            self.sock.sendto(end_packet.encode(), (self.server_addr, self.server_port))

                    print("quitting")
                    self.stop_event.set()  # Set the stop event before closing the socket
                    self.sock.close()
                    break
                else:
                    print("incorrect userinput format")

        except KeyboardInterrupt:
            # Send an empty message to the server to indicate disconnection
            self.sock.sendto(b"", (self.server_addr, self.server_port))
            print("Client disconnected.")
        finally:
            self.sock.close()

    def receive_handler(self):
        '''
        Waits for a message from server and process it accordingly
        '''
        while not self.stop_event.is_set():
            try:
                # Receive messages from the server
                data, server_address = self.sock.recvfrom(2048)
                if not data:
                    break
                #print(f"Received data from {server_address}: {data.decode()}")
                decoded_data = data.decode()
                typeofP, seqno, data, checksum = util.parse_packet(decoded_data)
                if typeofP == "ack":
                    # Put the received ACK into the queue
                    self.ack_queue.put(int(seqno))
                elif typeofP == "start":
                    ack_packet = util.make_packet("ack", int(seqno), "")
                    self.sock.sendto(ack_packet.encode(), (self.server_addr, self.server_port))
                elif typeofP == "end":
                    if(parts[0]== "forward_message"):
                        for sender, chunks in self.message_chunks.items():
                            concatenated_message = ''.join(chunks)
                            print(f"msg: {sender}: {concatenated_message}")
                    self.message_chunks.clear()
                    ack_packet = util.make_packet("ack", int(seqno), "")
                    self.sock.sendto(ack_packet.encode(), (self.server_addr, self.server_port))
                elif typeofP == "data":
                    parts = data.split()
                    if len(parts) >= 2:
                        msg_type = parts[0]
                        msg_len = int(parts[1])

                        if msg_type == "response_users_list":
                            ack_packet = util.make_packet("ack", int(seqno), "")
                            self.sock.sendto(ack_packet.encode(), (self.server_addr, self.server_port))
                            usernames = ' '.join(parts[4:])
                            print("list:", usernames)
                        elif msg_type == "forward_message":
                            sender_username = parts[2]
                            message_chunk = ' '.join(parts[3:])

                            # Add the message chunk to the dictionary
                            if sender_username in self.message_chunks:
                                self.message_chunks[sender_username].append(message_chunk)
                            else:
                                self.message_chunks[sender_username] = [message_chunk]

                            # print(f"Received chunk from {sender_username}: {message_chunk}")
                            ack_packet = util.make_packet("ack", int(seqno), "")
                            self.sock.sendto(ack_packet.encode(), (self.server_addr, self.server_port))
                        elif msg_type == "ERR_SERVER_FULL":
                            print("Server is full, please try again later.")
                        elif msg_type == "ERR_USERNAME_UNAVAILABLE":
                            print("Username is not available, please choose a different one.")
            except socket.timeout:
                # Handle timeout (if needed)
                pass
            except OSError as e:
                if e.errno == 9:  # Bad file descriptor
                    break


    def send_message(self, message):
        parts = message.split()
        recipients_count = int(parts[1])
        recipients = parts[2:2 + recipients_count]
        message_content = ' '.join(parts[2 + recipients_count:])
        message_chunks = [message_content[i:i+util.CHUNK_SIZE]
                      for i in range(0, len(message_content), util.CHUNK_SIZE)]

        start_seq_num = random.randint(1, 1000)  # Generate a random sequence number
        start_packet = util.make_packet("start", start_seq_num, "")
        self.sock.sendto(start_packet.encode(), (self.server_addr, self.server_port))

        ack_received = False
        while not ack_received:
            try:
                ack = self.ack_queue.get(timeout=util.TIME_OUT)  # Convert to seconds
                if ack == start_seq_num:
                    ack_received = True
            except queue.Empty:
                # Handle timeout by retransmitting the START packet
                self.sock.sendto(start_packet.encode(), (self.server_addr, self.server_port))

        # Send message chunks
        seq_num = start_seq_num + 1
        for chunk in message_chunks:

            chunk_with_recipients_info = f"msg {recipients_count} {' '.join(recipients)} " + chunk
            # Create the message
            msg = util.make_message("send_message", 4, chunk_with_recipients_info)
            packet = util.make_packet("data", seq_num, msg)
            self.sock.sendto(packet.encode(), (self.server_addr, self.server_port))

            # Increment sequence number
            seq_num += 1

            # Wait for ACK or handle retransmission
            ack_received = False
            retries = 0
            while not ack_received and retries < 3:  # Retry up to 3 times
                try:
                    # Get the ACK from the queue with a timeout
                    ack = self.ack_queue.get(timeout=util.TIME_OUT) 
                    if ack == seq_num-1:
                        ack_received = True
                except queue.Empty:
                    # Handle timeout by retransmitting the packet
                    self.sock.sendto(packet.encode(), (self.server_addr, self.server_port))
                    retries += 1
            if not ack_received:
                print(f"Failed to receive ACK for packet {seq_num - 1}. Retries exhausted.")
                break

            
        end_packet = util.make_packet("end", seq_num, msg)
        self.sock.sendto(end_packet.encode(), (self.server_addr, self.server_port))

        ack_received = False
        while not ack_received:
            try:
                ack = self.ack_queue.get(timeout=util.TIME_OUT)  # Convert to seconds
                if ack == seq_num:
                    ack_received = True
            except queue.Empty:
                self.sock.sendto(end_packet.encode(), (self.server_addr, self.server_port))
            


    def print_help(self):
        print("API Functions:")
        print("1) Message: msg <number_of_users> <username1> <username2> … <message>")
        print("2) Available Users: list")
        print("3) Help: help")
        print("4) Quit: quit")

    def list_users(self):
        # Send start packet
        start_seq_num = random.randint(1, 1000)  # Generate a random sequence number
        start_packet = util.make_packet("start", start_seq_num, "")
        self.sock.sendto(start_packet.encode(), (self.server_addr, self.server_port))

        ack_received = False
        while not ack_received:
            try:
                ack = self.ack_queue.get(timeout=util.TIME_OUT)  # Convert to seconds
                if ack == start_seq_num:
                    ack_received = True
            except queue.Empty:
                # Handle timeout by retransmitting the START packet
                self.sock.sendto(start_packet.encode(), (self.server_addr, self.server_port))

        # Send list request packet
        seq_num = start_seq_num + 1
        list_packet = util.make_message("request_users_list", 2)
        packet = util.make_packet("data", seq_num, list_packet)
        self.sock.sendto(packet.encode(), (self.server_addr, self.server_port))

        # Wait for ACK or handle retransmission
        ack_received = False
        retries = 0
        while not ack_received and retries < 3:  # Retry up to 3 times
            try:
                # Get the ACK from the queue with a timeout
                ack = self.ack_queue.get(timeout=util.TIME_OUT)
                if ack == seq_num:
                    ack_received = True
            except queue.Empty:
                # Handle timeout by retransmitting the packet
                self.sock.sendto(packet.encode(), (self.server_addr, self.server_port))
                retries += 1
        if not ack_received:
            print(f"Failed to receive ACK for packet {seq_num}. Retries exhausted.")

        # Send end packet
        end_packet = util.make_packet("end", seq_num + 1,list_packet)
        self.sock.sendto(end_packet.encode(), (self.server_addr, self.server_port))

        ack_received = False
        while not ack_received:
            try:
                ack = self.ack_queue.get(timeout=util.TIME_OUT)  # Convert to seconds
                if ack == seq_num + 1:
                    ack_received = True
            except queue.Empty:
                self.sock.sendto(end_packet.encode(), (self.server_addr, self.server_port))


# Do not change below part of code
if __name__ == "__main__":
    def helper():
        '''
        This function is just for the sake of our Client module completion
        '''
        print("Client")
        print("-u username | --user=username The username of Client")
        print("-p PORT | --port=PORT The server port, defaults to 15000")
        print("-a ADDRESS | --address=ADDRESS The server ip or hostname, defaults to localhost")
        print("-w WINDOW_SIZE | --window=WINDOW_SIZE The window_size, defaults to 3")
        print("-h | --help Print this help")
    try:
        OPTS, ARGS = getopt.getopt(sys.argv[1:],
                                   "u:p:a:w", ["user=", "port=", "address=","window="])
    except getopt.error:
        helper()
        exit(1)
    PORT = 15000
    DEST = "localhost"
    USER_NAME = None
    WINDOW_SIZE = 3
    for o, a in OPTS:
        if o in ("-u", "--user="):
            USER_NAME = a
        elif o in ("-p", "--port="):
            PORT = int(a)
        elif o in ("-a", "--address="):
            DEST = a
        elif o in ("-w", "--window="):
            WINDOW_SIZE = a

    if USER_NAME is None:
        print("Missing Username.")
        helper()
        exit(1)

    S = Client(USER_NAME, DEST, PORT, WINDOW_SIZE)
    try:
        # Start receiving Messages
        T = Thread(target=S.receive_handler)
        #T.daemon = True
        T.start()
        # Start Client
        S.start()
    except (KeyboardInterrupt, SystemExit):
        sys.exit()
