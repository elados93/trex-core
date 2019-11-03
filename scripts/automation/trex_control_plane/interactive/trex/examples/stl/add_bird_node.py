import stl_path
from trex.stl.api import *
from trex.pybird.bird_cfg_creator import *
from trex.pybird.bird_zmq_client import *

"""
Topology::
                                          +------------------------------+
                                          |                              |
                                          |   TRex         bird namespace|
                                          |        (veth) +--------------+
+------------+               (PHY PORT 0) |       1.1.1.3 |              |
|            |    1.1.1.1       1.1.1.2   |      <--------+              |
|            | <------------><----------->+               |              |
|            |                            |               | Bird Process |
|    DUT     |                            |        (veth) |              |
|            |    1.1.2.1       1.1.2.1   |       1.1.2.3 |              |
|            | <------------><----------->+      <--------+              |
|            |               (PHY PORT 1) |               |              |
+------------+                            |               +--------------+
                                          |                              |
                                          +------------------------------+
"""

c = STLClient()
my_ports = [0, 1]
c.connect()
c.acquire(ports = my_ports)
c.set_service_mode(ports = my_ports, enabled = True)

pybird_c = PyBirdClient(ip='localhost', port=4509)
pybird_c.connect()
pybird_c.acquire()

# c.set_namespace(0, method='add_node', mac="00:00:00:01:00:07", shared_ns = "ns")
# c.set_namespace(0, method='set_ipv4', mac="00:00:00:01:00:07", 
#                                         ipv4 = "1.1.1.3", subnet = 24, shared_ns = True)

# c.set_namespace(0, method='set_dg', dg="1.1.1.4", shared_ns = "ns")
# c.set_namespace(0, method='set_dg', dg="1.1.1.5", shared_ns = "ns")
# c.set_namespace(0, method='set_dg', dg="1.1.1.6", shared_ns = "ns")

# c.set_namespace(0, method='set_dg', shared_ns = "ns", dg = "0.0.0.0")

bird_cfg = BirdCFGCreator()
bgp_data1 = """
    local 1.1.1.3 as 65000;
    neighbor 1.1.1.1 as 65000;
    ipv4 {
            import all;
            export all;
    };
"""
bgp_data2 = """
    local 1.1.2.3 as 65000;
    neighbor 1.1.2.1 as 65000;
    ipv4 {
            import all;
            export all;
    };
"""

bird_cfg.add_protocol(protocol = "bgp", name = "my_bgp1", data = bgp_data1)
bird_cfg.add_protocol(protocol = "bgp", name = "my_bgp2", data = bgp_data2)
bird_cfg.add_route(dst_cidr = "42.42.42.42/32", next_hop = "1.1.1.3")
bird_cfg.add_route(dst_cidr = "42.42.42.43/32", next_hop = "1.1.2.3")
pybird_c.set_config(new_cfg = bird_cfg.build_config())  # sending our new config

# create 2 veth's in bird namespace
c.set_bird_node(node_port      = 0,
                mac            = "00:00:00:01:00:07",
                ipv4           = "1.1.1.3",
                ipv4_subnet    = 24,
                ipv6_enabled   = True,
                ipv6_subnet    = 124,
                vlans          = [22],
                tpid           = [0x8100])

c.set_bird_node(node_port      = 1,
                mac            = "00:00:00:01:00:08",
                ipv4           = "1.1.2.3",
                ipv4_subnet    = 24,
                ipv6_enabled   = True,
                ipv6_subnet    = 124)

pybird_c.check_protocols_up(['my_bgp1, my_bgp2'])
c.set_namespace(0, method='get_nodes_info', macs_list=["00:00:00:01:00:07"])
c.set_namespace(1, method='get_nodes_info', macs_list=["00:00:00:01:00:08"])
pybird_c.release()
pybird_c.disconnect()
c.disconnect()
