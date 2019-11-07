#!/usr/bin/python
import time
from .stl_general_test import CStlGeneral_Test, CTRexScenario
from trex.common.services.trex_service_icmp import ServiceICMP 
from trex.pybird.bird_cfg_creator import *
from trex.pybird.bird_zmq_client import *

class STLBird_Test(CStlGeneral_Test):
    """Tests for Bird Routing Daemon """
    
    def setUp(self):
        CStlGeneral_Test.setUp(self)
        # if not self.is_linux_stack:
        #     self.skip("We need linux stack for this tests to work")

        self.stl_trex.reset()
        self.stl_trex.set_service_mode()
        self._conf_router_int()
        self._conf_router_bgp()
        self.pybird = PyBirdClient(ip = 'localhost', port = 4509)
        self.pybird.connect()
        self.pybird.acquire(force = True)

    def tearDown(self):
        # remove all ?
        # return interfaces ?
        self.pybird.release()
        self.pybird.disconnect()

    def _conf_router_int(self):
        CTRexScenario.router.load_clean_config()
        CTRexScenario.router.configure_basic_interfaces()
        
    def _conf_router_bgp(self):
        CTRexScenario.router.configure_bgp()

    def _add_simple_bgp(self, cfg_creator):
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
        cfg_creator.add_protocol(protocol = "bgp", name = "my_bgp1", data = bgp_data1)
        cfg_creator.add_protocol(protocol = "bgp", name = "my_bgp2", data = bgp_data2)

    def _check_how_many_routes(self, protocol = ""):
        lines = CTRexScenario.router.get_routing_stats(protocol).splitlines()
        protocol_line = [line for line in lines if line.startswith(protocol)][0].strip()
        return int(protocol_line[len(protocol):].split()[1])  # second column

    def test_bird_ping(self):
        if True:
            return
        c = self.stl_trex
        MAC = "00:00:00:01:00:06"

        try:

            # add bird node
            c.set_bird_node(node_port = 0, mac = MAC, ipv4 = "1.1.1.3", ipv4_subnet = 24)
            
            # ping to veth
            r = c.ping_ip(0, '1.1.1.3')

            assert len(r) == 5, 'should be 5 responses'
            assert r[0].state == ServiceICMP.PINGRecord.SUCCESS

            c.set_port_attr(promiscuous = True, multicast = True)
            # ping to router
            r = c.ping_ip(0, '1.1.1.1')

            assert len(r) == 5, 'should be 5 responses'
            assert r[0].state == ServiceICMP.PINGRecord.SUCCESS
        
        finally:
            c.set_port_attr(promiscuous = False, multicast = False)
            c.namespace_remove_all()  

    def test_bird_small_routes(self):
        c = self.stl_trex
        MAC = "00:00:00:01:00:06"

        try:
            # add bird node
            c.set_bird_node(node_port = 0, mac = MAC, ipv4 = "1.1.1.3", ipv4_subnet = 24)
            c.set_bird_node(node_port = 1, mac = MAC, ipv4 = "1.1.2.3", ipv4_subnet = 24)
            
            # make conf file
            cfg_creator = BirdCFGCreator()
            self._add_simple_bgp(cfg_creator)
            cfg_creator.add_many_routes("10.10.10.0", total_routes = 2, next_hop = "1.1.1.3")

            # push conf file
            self.pybird.set_config(new_cfg = cfg_creator.build_config())

            # assert config reached bird
            assert self.pybird.check_protocols_up(["my_bgp1", "my_bpg2"], verbose = True)

            # get current routing from DUT
            routes = CTRexScenario.router.get_routing_table("bgp").splitlines()
            bgp_routes = [line for line in routes if line.startswith(" * i")]
            # assert len(bgp_routes) == 2
            assert [bgp for bgp in bgp_routes if "10.10.10.0/32" in bgp]
            assert [bgp for bgp in bgp_routes if "10.10.10.1/32" in bgp]

        finally:
            c.set_port_attr(promiscuous = False, multicast = False)
            c.namespace_remove_all()

    def test_bird_many_routes(self):
        # NEED TO FIX MBUF ON NEXT COMMIT
        pass
        # c = self.stl_trex
        # MAC = "00:00:00:01:00:06"

        # try:
        #     # add bird node
        #     c.set_bird_node(node_port = 0, mac = MAC, ipv4 = "1.1.1.3", ipv4_subnet = 24)
        #     c.set_bird_node(node_port = 1, mac = MAC, ipv4 = "1.1.2.3", ipv4_subnet = 24)

        #     # take 1M conf file
        #     with open('stateless_tests/bird_profiles/1m_routes.conf', 'r') as f:
        #         one_m_routes_conf = f.read()

        #     # push conf file
        #     self.pybird.set_config(one_m_routes_conf)

        #     # assert config reached bird
        #     assert self.pybird.check_protocols_up(["my_bgp1", "my_bpg2"], verbose = True)

        #     # get 1M routes got to DUT
        #     for _ in range(5):
        #         routes = self._check_how_many_routes("bgp 65000")
        #         print("Dut got %s routes" % routes)
        #         time.sleep(10)
        #         if routes >= 1e6:
        #             return
        #     assert routes >= 1e6, "Not all 1M routes got to dut"

        # finally:
        #     c.set_port_attr(promiscuous = False, multicast = False)
        #     c.namespace_remove_all()

    def test_route_from_router(self):
        # add static route in the router see if bird learn it
        pass


    # OSPF Tests