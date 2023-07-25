import socket
import random
import select
import sys
import re
import time

## This code is run once on server start up to determine the server properties
argc = len(sys.argv)

if(argc < 2):
    ack_loss = input("Enter probability of ACK loss as a decimal (default: 0.0): ")
    if not ack_loss:
        ack_loss = "0.0"
else:
    ack_loss = sys.argv[1]
################################################################################

# Server configuration
SERVER_IP = '0.0.0.0'  # Change to the server's IP address
SERVER_PORT = 12345     # Change to the desired server port
MAX_SEQ_NUM = 2**16     # Maximum sequence number
RECV_TIMEOUT    = .1    # Timeout value in seconds

# Probability of ACK loss
ACK_LOSS_PROBABILITY = float(ack_loss)
random.seed(int(time.time()))

### Generates a random seed using the current time, then determines
### if an ack packet is dropped by the ack loss constant
def ack_drop():
    if(random.random() >= ACK_LOSS_PROBABILITY):
        return True
    else:
        return False


def incr_ack_num(expected_ack):
    expected_ack += 1
    if expected_ack >= MAX_SEQ_NUM:
        expected_ack = 0
    return expected_ack


def server():
    # Create server socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((SERVER_IP, SERVER_PORT))
    server_socket.listen(1)
    print('Server started and listening for connections...')

    # Accept client connection
    client_socket, client_address = server_socket.accept()
    print('Connection established with', client_address)

    # Receive initial string from client
    initial_string = client_socket.recv(1024).decode()
    print('Received initial string from client:', initial_string)

    # Send connection setup success message
    success_message = 'success'
    client_socket.send(success_message.encode())

      # Send TCP sequence numbers to server
    expected_seq_num_counter = 0
    received_segments = 0
    missing_segments = 0
    total_received_segments = 0
    total_sent_segments_counter = 0
    num_periods = 0
    buffer = []
    prev_sliced_num = ""
    sliced_seq_num = ""

    while True:
        ready = select.select([client_socket], [], [], RECV_TIMEOUT)
        if ready[0]:
            seq_num = client_socket.recv(1024).decode()
            if not seq_num:
                break
            
            # Recovers from a partial sequence number being sliced
            seq_num = sliced_seq_num + seq_num
            sliced_seq_num = ""

            index = len(seq_num) - 1
            while seq_num[index] != ';':
                sliced_seq_num = seq_num[index] + sliced_seq_num
                index -= 1
            seq_num = seq_num[:index]

            segs = re.split(":|;", seq_num) # Turn the data stream into an array
            segs = list(filter(None, segs)) # Filter out any empty strings that populate the array

            if(segs[0].isnumeric()):        # Test to see if the first string in the array is an # or data
                segs = segs[::2]            # Parse out data
            else:
                segs = segs[1::2]           # Parse out data
            
            buffer.extend(segs)             # Add Seq #'s to buffer
        
        while buffer:
            seq_num = int(buffer.pop(0))    # Get next seq #
            received_segments += 1  # Add seq number to recieved segments
            total_sent_segments_counter += 1
                
            # If the sequence number is the next expected sequence number increment expected number
            if seq_num == expected_seq_num_counter:
                expected_seq_num_counter = incr_ack_num(expected_seq_num_counter)
                total_received_segments += 1    # Increment total recieved segments
            # Else packet was recieved but not the correct/expected packet
            else:
                print("Expect Seg: " + expected_seq_num_counter)
                print("Recieved Seg:" + seq_num)
                # Missing sequence number, add to missing_segments set
                missing_segments += 1

            # No matter what seq # recieved, request the expected sequence number 
            ack_segment = "ACK:" + str(expected_seq_num_counter) + ";"
            if ack_drop():
                client_socket.send(ack_segment.encode('UTF-8'))

            # Calculate good-put and report average periodically
            if total_sent_segments_counter % 1000 == 0:
                good_put = total_received_segments / total_sent_segments_counter
                num_periods += 1
                print('Received segments:', received_segments)
                print('Missing segments:', missing_segments)
                print('Good-put after every 1000 segments:', good_put)
                received_segments = 0
                missing_segments = 0

    # Calculate final average good-put
    if total_sent_segments_counter > 0:
        final_good_put = total_received_segments / total_sent_segments_counter
        print('Final Average Good-put:', final_good_put)

    # Close the connection
    client_socket.close()
    server_socket.close()
    print('Connection closed')

if __name__ == '__main__':
    server()