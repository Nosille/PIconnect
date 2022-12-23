#!/usr/bin/env python
# -*- coding: utf-8 -*-

import PIconnect as PI

with PI.PIServer(server="pub-datac-pi01.erdc-pub.dren.mil", 
            domain="erdc-pub", 
            username="rpitlcce",  
            password="!QAZ2wsx#EDC4rfv" ) as server:

    with PI.PIAFDatabase(server="PUB-DATAC-PI01", 
                        domain="erdc-pub", 
                        username="rpitlcce", 
                        password="!QAZ2wsx#EDC4rfv",
                        database="SmartGate") as database:
        print(database.server_name)
        print(database.database_name)

    with PI.PIAFDatabase(server="PUB-DATAC-PI01", 
                        domain="erdc-pub", 
                        username="rpitlcce", 
                        password="!QAZ2wsx#EDC4rfv",
                        database="SmartGate") as database:


        site = database.children["The Dalles"]
        print(site.name)
        chamber = site.children["Main Chamber"]
        print(chamber.name)
        conditions = chamber.children["Chamber Conditions"]
        print(conditions.name)
        sensor = conditions.children["Downstream Water Level"]
        print(sensor.name)
        attribute = sensor.attributes["Raw Value"]
        print(attribute.name)
        data = attribute.recorded_values("*-10d", "*-9d")
        print(data)
            