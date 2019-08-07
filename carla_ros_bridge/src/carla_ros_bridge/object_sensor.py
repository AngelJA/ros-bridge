#!/usr/bin/env python
#
# Copyright (c) 2019 Intel Corporation
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.
#
"""
handle a object sensor
"""

from derived_object_msgs.msg import ObjectArray
from carla_ros_bridge.vehicle import Vehicle

from modules.perception.proto.perception_obstacle_pb2 import PerceptionObstacles

def get_filtered_objectarray(parent, filtered_id):
    """
    Get a ObjectArray for all available actors, except the one with the filtered_id

    """
    ros_objectlist = ObjectArray()
    ros_objectlist.header = parent.get_msg_header()
    for actor_id, child in parent.child_actors.iteritems():
        # currently only Vehicles are added to the object array
        if filtered_id is not actor_id and isinstance(child, Vehicle):
            ros_objectlist.objects.append(child.get_ros_object_msg())
    return ros_objectlist

def get_filtered_obstaclearray(parent, filtered_id):
    """
    Get a PerceptionObstacles msg for all vehicle actors, except the one with the filtered_id

    """
    obstacles = PerceptionObstacles()
    obstacles.header.CopyFrom(parent.get_cyber_header())
    for actor_id, child in parent.child_actors.iteritems():
        if filtered_id is not actor_id and isinstance(child, Vehicle):
            if child.carla_actor.attributes.get('role_name') not in parent.get_param('ego_vehicle').get('role_name'):
                obstacles.perception_obstacle.append(child.get_cyber_obstacle_msg())
    return obstacles
