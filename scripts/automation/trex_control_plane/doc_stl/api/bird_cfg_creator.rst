
Bird CFG Creator
=======================

More on "Bird" you can find at `Bird documentation <https://bird.network.cz/?get_doc&f=bird.html&v=20>`_ or more focused at `Bird configuration <https://bird.network.cz/?get_doc&v=20&f=bird-3.html>`_.

Using this API the user can create his own custom bird configuration file, adding/removing routes and routing protocols. When the final config file is read to send, you can use PyBirdClient to do so.
The working flow is simple as:
1. Create BirdCFGCreator object, passing current bird configuration as a string.
2. Manipulate the future config: add/remove routes and routing protocols.
3. Create the final bird.conf content as a string.

The following snippet create 2 bird nodes with ipv4 and ipv6 ::

    bird_cfg = BirdCFGCreator()

    # defining protocols data as strings
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

    # adding protocols
    bird_cfg.add_protocol(protocol = "bgp", name = "my_bgp1", data = bgp_data1)
    bird_cfg.add_protocol(protocol = "bgp", name = "my_bgp2", data = bgp_data2)
    
    # adding routes
    bird_cfg.add_route(dst_cidr = "42.42.42.42/32", next_hop = "1.1.1.3")
    bird_cfg.add_route(dst_cidr = "42.42.42.43/32", next_hop = "1.1.2.3")
    
    # build combined configuration
    cfg = bird_cfg.build_config()

BirdCFGCreator Class
--------------------

.. autoclass:: trex.pybird.bird_cfg_creator.BirdCFGCreator
    :members: 
    :inherited-members:
    :member-order: bysource