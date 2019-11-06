import sys
import zmq
import json
import time
import hashlib
import random as rand
from argparse import *
from trex.pybird.bird_cfg_creator import *
from pprint import pprint

class ConnectionException(Exception): pass
class ConfigurationException(Exception): pass

def rand_32_bit():
    return rand.randint(0, 0xFFFFFFFF)


class PyBirdClient():

    CLIENT_VERSION = "1.0"  # need to sync with bird zmq sever

    def __init__(self, ip = 'localhost', port = 4509):
        self.ip = ip
        self.socket = None
        self.context = None
        self.port = port
        self.handler = None  # represent non connected client
        self.is_connected = False 

    def __del__(self):
        self._close_conn()
        
    def _close_conn(self):
        if self.handler is not None:
            self.release()
        if self.socket is not None:
            self.socket.close()
        if self.context is not None:
            self.context.destroy()    

    def _get_response(self, id):
        while True:
            message = self.socket.recv()
            message = message.decode()
            try:
                message_parsed = json.loads(message)
            except:
                print('"Error in parsing response! got: "%s"' % message)
                break
            if type(message_parsed) is not dict:
                print('Error in message: "%s"' % message)
                raise Exception('Got from server "{}" type instead of dictionary! content: {}'.format(type(message_parsed), message_parsed))
            if 'error' in message_parsed.keys():
                print('Error in message: "%s"' % message)
                raise Exception('Got exception from server! message: {message}'.format(message_parsed['error']))
            if 'id' not in message_parsed.keys():
                print("Got response with no id, waiting for another one")
            elif message_parsed['id'] != id:
                print("Got response with different id, waiting for another one")
            else:
                break  # found the wanted response
        if 'result' in message_parsed.keys():
            return message_parsed['result']
        raise Exception(message_parsed['error'])

    def _call_method(self, method_name, method_params):
        rand_id = rand_32_bit()  # generate 32 bit random id for request
        if type(method_params) != list:
            method_params = list(method_params)
        json_rpc_req = { "jsonrpc": "2.0", "method": method_name , "params": method_params, "id": rand_id}
        request = json.dumps(json_rpc_req)
        self.socket.send(request.encode('utf-8'))
        return self._get_response(rand_id)
    
    def connect(self):
        ''' 
            Connect client to PyBird server. Only check versions and open the socket to bird.
        '''
        if not self.is_connected:
            self.context = zmq.Context()
            self.socket = self.context.socket(zmq.REQ)
            self.socket.connect("tcp://"+str(self.ip)+":"+str(self.port))
            result = self._call_method('connect', [PyBirdClient.CLIENT_VERSION])
            if result:
                self.is_connected = True
            return result
        else:
            raise Exception("PyBird Client is already connected!")

    def acquire(self, force=False):
        ''' 
            Acquire unique "handler" for client. PyBird Server can only acquire 1 client at a time.

            :parameters:

                force: bool
                force acquire, will disconnect connected clients. False by default
            
            :raises:
                + :exc:`ConnectionException` in case of error

        '''
        if self.is_connected or force:
            result = self._call_method('acquire', [force])
            self.handler = result
            self.is_connected = True
        else:
            raise ConnectionException("Cannot acquire before connect!")
        return result

    def get_config(self):
        '''
            Query, Return the current bird configuration.    
        '''
        if not self.is_connected:
            raise ConnectionException("Cannot get config when client is not connected!")
        return self._call_method('get_config', [])

    def get_protocols_info(self):
        if not self.is_connected:
            raise ConnectionException("Cannot get protocols information when client is not connected!")
        return self._call_method('get_protocols_info', [])

    def check_protocols_up(self, protocols_list, timeout=60, poll_rate=1):
        '''
            Query, waiting for all the bird protocols in 'protocols' list. In case bird protocols are still
            down after 'timeout' seconds, an exception will be raised. 

            usage example::

                wait_for_protocols(['bgp1', 'rip1', 'rip2'])

            :parameters:

                protocols: list 
                    list of all protocols names the new bird node will be followed by.
                    notice the names should be exactly as they appear in bird configuration

                timeout: int
                    total time waiting for bird protocols

                poll_rate: int
                    polling rate for bird protocols check
            
            :raises:
                + :exc:`Exception` in case of any error
        '''
        protocols_list = [p.lower() for p in protocols_list]
        for _ in range(int(timeout / poll_rate)):
            down_protocols = []
            info = self.get_protocols_info()
            info = [str(l.lower().strip()) for l in info.splitlines()]
            for line in info:
                split_line = line.split()
                for protocol in protocols_list:
                    if protocol in split_line[0] and 'up' not in split_line[3]:
                        down_protocols.append(protocol)
            if not down_protocols:
                return
            else:
                time.sleep(poll_rate)
        raise Exception('timeout passed, protocols "%s" still down in bird' % down_protocols)
        
    def set_empty_config(self):
        '''
            Command, setting the minimal bird configuration with no routes and no routing protocols.
        '''
        return self._call_method('set_empty_config', [self.handler])

    def set_config(self, new_cfg):
        '''
            Command, set the given config string as the new bird configuration.

            :parameters:

                new_cfg: string
                    valid bird cfg as a string 

            :raises:
                + :exc:`ConnectionError` in case client is not connected
        '''
        if self.handler:
            return self._upload_fragmented('set_config', new_cfg)
        else:
            raise ConnectionError("Client is not connected to server, please run connect first")

    def release(self):
        '''
            Release current handler from server in order to let another client acquire.
            :raises:
            + :exe: 'ConnectionException' in case of error
        '''
        if self.handler is not None:
            res = self._call_method('release', [self.handler])
            self.handler = None
            return res
        else:
            raise ConnectionException("Cannot release, client is not acquired")

    def disconnect(self):
        '''
            Disconnect client from server and close the socket. Must be called after releasing client.
            :raises:
            + :exe: 'ConnectionException' in case of error
        '''
        if self.handler is not None:
            raise Exception('Client is acquired! run "release" first')
        if self.is_connected:
            return self._call_method('disconnect', [])
        else:
            raise ConnectionException("Cannot disconnect, client is not connected")
        self._close_conn()

    def _upload_fragmented(self, rpc_cmd, upload_string):
        index_start = 0
        fragment_length = 1000  # first fragment is small, we compare hash before sending the rest
        while len(upload_string) > index_start:
            index_end = index_start + fragment_length
            params = {
                'handler': self.handler,
                'fragment': upload_string[index_start:index_end],
                }
            if index_start == 0:
                params['frag_first'] = True
            if index_end >= len(upload_string):
                params['frag_last'] = True
            if params.get('frag_first') and not params.get('frag_last'):
                params['md5'] = hashlib.md5(upload_string.encode()).hexdigest()

            # send the fragment
            json_rpc_req = { "jsonrpc":"2.0","method": rpc_cmd ,"params": params, "id": rand_32_bit()}
            request = json.dumps(json_rpc_req)
            self.socket.send(request.encode('utf-8'))

            # wait for server response
            respond = self._get_response(json_rpc_req['id'])
            if respond != 'send_another_frag':
                return respond
            index_start = index_end
            fragment_length = 50000
            
        raise ConfigurationException("Sent all the fragments, but did not get the configuration response")


def generate_ips(start, end):
    import socket, struct
    start = struct.unpack('>I', socket.inet_aton(start))[0]
    for i in range(start, start + int(end)):
        s = '%s/32via1.1.2.3;' % socket.inet_ntoa(struct.pack('>I', i))
        yield s.split('via')

def send_many_routes(b, total_routes):

    bird_cfg = BirdCFGCreator()

    for dst, from_str in generate_ips("1.1.2.1", total_routes): # generate many routes
        bird_cfg.add_route(dst, from_str)

    print('Sending {:,} routes...'.format(total_routes))
    import time
    start = time.time()

    print("Server response: %s" % b.set_config(bird_cfg.build_config()))

    end = time.time()
    print("Took: {} seconds".format(end - start))


if __name__=='__main__':
    parser = ArgumentParser(description='Example of client module for Bird server ')
    parser.add_argument('-p','--dest-bird-port',type=int, default = 4509, dest='port',
                        help='Select port to which this Bird Server client will send to.\n default is 4509\n',action='store')
    parser.add_argument('-s','--server',type=str, default = 'localhost', dest='ip',
                        help='Remote server IP address .\n default is localhost\n',action='store')

    args = parser.parse_args()

    # simple usage
    b = PyBirdClient(args.ip, args.port)

    print("connect: \n%s" % b.connect())
    print("acquire: \n%s" % b.acquire(True))
        
    print("get_config: \n%s" % b.get_config())
    print("get_protocols_info: \n%s" % b.get_protocols_info())

    send_many_routes(b, rand.randint(1e6, 1e6 + 1))
    print('-' * 50)
    print("release: %s" % b.release() )
    print("disconnect: %s" % b.disconnect() )
