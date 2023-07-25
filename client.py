import socket
import time
import re
import select
import sys
import random


## This code is run once at start up to determine client properties
argc = len(sys.argv)

if(argc < 2):
    # Request IP of server and segments to send
    server_ip = input("Please enter server IP address (default: 127.0.0.1): ")
    if not server_ip:
        server_ip = "127.0.0.1"
if(argc < 3):
    num_segs = input("Enter number of segments to send (default: 10000000): ")
    if not num_segs:
        num_segs = "10000000"
    if(argc == 2):
        server_ip = sys.argv[1]
if(argc < 4):
    pac_loss = input("Enter probability of packet loss as a decimal (default: 0.0): ")
    if not pac_loss:
        pac_loss = "0.0"
    if(argc == 3):
        server_ip = sys.argv[1]
        num_segs = sys.argv[2]
else:
    server_ip = sys.argv[1]
    num_segs = sys.argv[2]
    pac_loss = sys.argv[3]
########################################################################################

# Server configuration
SERVER_IP   = server_ip # Change to the server's IP address
SERVER_PORT = 12345     # Change to the desired server port
MAX_SEQ_NUM = 2**16     # Maximum sequence number
WINDOW_SIZE = 1         # Initial sliding window size
RECV_TIMEOUT    = .1    # Timeout value in seconds
PACK_TIMEOUT    = 2     # Timeout of packet
MAX_SEGMENTS    = int(num_segs) # Number of segments to send
SEGMENT_SIZE    = 1     # Size of the segments
PAC_LOSS_PROBABILITY = float(pac_loss)
random.seed(int(time.time()))


### Generates a random seed using the current time, then determines
### if a packet is dropped by the packet loss constant
def packet_drop():
    if(random.random() > PAC_LOSS_PROBABILITY):
        return True
    else:
        return False
    
### Creates the packet and sends it depending on loss probability
def send_segment(seq, data, socket):
    segment = str(seq) + ":" + str(data) + ";"
    if(packet_drop()):
        socket.send(segment.encode('UTF-8'))


### Finds the greatest acknowledgement in the recv buffer
def find_last_ack(ack_seg):
    # Split recieved ack string by colons and semicolons
    ack_list = re.split(':|;', ack_seg)
    # Filter out any blank values added to the list
    ack_list = list(filter(None, ack_list))
    # Check to see if first number of list is numeral or "ACK"
    if(ack_list[0].isnumeric()):
        # Take out every ACK
        ack_list = ack_list[::2]
    else:
        # Take out every ACK
        ack_list = ack_list[1::2]
    
    # Get largest ACK
    largest_ack = int(ack_list.pop(0))
    while ack_list:
        next_ack =  int(ack_list.pop(0))
        if largest_ack < next_ack:
            largest_ack = next_ack
     
    # Return largest ACK
    return largest_ack


# Increments the sequence number to next segment
def incr_seq_num(seq_num):
    # Increase sequence number to next byte of next segment
    seq_num = seq_num + SEGMENT_SIZE
    # Check for sequence number wrap around
    if seq_num >= MAX_SEQ_NUM:
        seq_num = 0
    # Return the next sequence number
    return seq_num


def client():
    # Create client socket
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((SERVER_IP, SERVER_PORT))
    print('Connected to server at', SERVER_IP, 'on port', SERVER_PORT)

    # Send initial string to server
    initial_string = 'network'
    client_socket.send(initial_string.encode())

    # Receive connection setup success message
    ready = select.select([client_socket], [], [], RECV_TIMEOUT)
    # Block if no success signal comes
    while not ready[0]:
        ready = select.select([client_socket], [], [], RECV_TIMEOUT)    
    success_message = client_socket.recv(1024).decode()
    print('Received connection setup success message:', success_message)

    # Send TCP sequence numbers to server
    next_seq_num = 0
    ack_seq_num = 0
    send_base = 0
    sliding_window = WINDOW_SIZE
    dropped_packet = 0
    segment_timer = {}
    total_recieved_segments = 0

    while total_recieved_segments < MAX_SEGMENTS:
        ready = select.select([client_socket], [client_socket], [], RECV_TIMEOUT)
        if next_seq_num < (send_base + sliding_window) and next_seq_num < MAX_SEGMENTS and ready[1]:
            # Send the next segment
            # print("Sending SEQ: " + str(next_seq_num))
            send_segment(next_seq_num, "Valuable Payload goes here", client_socket)
            # Add a timer to the sent packet
            segment_timer[next_seq_num] = time.time()
            # Increment the next sequence number
            next_seq_num = incr_seq_num(next_seq_num)
        else:
            # Wait for ACK or timeout to occur
            if ready[0]:
                ack_seg = client_socket.recv(1024).decode('UTF-8')
                ack_seq_num = find_last_ack(ack_seg)
                # print("HIGHEST SEQUENCE NUMBER: " + str(ack_seq_num))
                if ack_seq_num > send_base or (send_base + 1) == MAX_SEQ_NUM:
                    # ACK received, adjust sliding window
                    print(f"ACK {ack_seq_num} Received.")
                    if not dropped_packet:
                        sliding_window *= 2
                    else:
                        sliding_window += 1
                    
                    # Check to make sure sliding window does not exceed max size
                    if(sliding_window > MAX_SEQ_NUM):
                        sliding_window = MAX_SEQ_NUM
                    if(send_base > ack_seq_num):
                        send_base = 0
                    total_recieved_segments += (ack_seq_num - send_base)
                    send_base = ack_seq_num
                    
                    # print("NEW SLIDING WINDOW: " + str(window))
            # Check for timeout on the base segment
            if send_base < next_seq_num and time.time() - segment_timer[send_base] >= PACK_TIMEOUT:
                print("TIMEOUT OCCURRED")
                # Timeout occurred, retransmit oldest unacknowledged segment
                send_segment(send_base, "Junk Data", client_socket)
                segment_timer[send_base] = time.time()
                if sliding_window > 1:
                    sliding_window //= 2
                dropped_packet = 1

    # Close the connection
    client_socket.close()
    print('Connection closed')

if __name__ == '__main__':
    client()
