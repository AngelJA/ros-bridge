#!/usr/bin/env python

#
# Copyright (c) 2018-2019 Intel Corporation
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.
#
"""
Classes to handle Carla vehicles
"""
import math

import rospy

from nav_msgs.msg import Odometry
from std_msgs.msg import ColorRGBA
from std_msgs.msg import Bool

import tf
import pyproj
from cyber_py import cyber, cyber_time
from modules.localization.proto.localization_pb2 import LocalizationEstimate
from modules.localization.proto.gps_pb2 import Gps
from modules.canbus.proto.chassis_pb2 import Chassis
from modules.control.proto.control_cmd_pb2 import ControlCommand
from modules.planning.proto.planning_pb2 import ADCTrajectory

from carla import VehicleControl, Vector3D

from carla_ros_bridge.vehicle import Vehicle
from carla_ros_bridge_msgs.msg import CarlaEgoVehicleInfo  # pylint: disable=no-name-in-module,import-error
from carla_ros_bridge_msgs.msg import CarlaEgoVehicleInfoWheel  # pylint: disable=no-name-in-module,import-error
from carla_ros_bridge_msgs.msg import CarlaEgoVehicleControl  # pylint: disable=no-name-in-module,import-error
from carla_ros_bridge_msgs.msg import CarlaEgoVehicleStatus  # pylint: disable=no-name-in-module,import-error


class EgoVehicle(Vehicle):

    """
    Vehicle implementation details for the ego vehicle
    """

    @staticmethod
    def create_actor(carla_actor, parent):
        """
        Static factory method to create ego vehicle actors

        :param carla_actor: carla vehicle actor object
        :type carla_actor: carla.Vehicle
        :param parent: the parent of the new traffic actor
        :type parent: carla_ros_bridge.Parent
        :return: the created vehicle actor
        :rtype: carla_ros_bridge.Vehicle or derived type
        """
        return EgoVehicle(carla_actor=carla_actor, parent=parent)

    def __init__(self, carla_actor, parent):
        """
        Constructor

        :param carla_actor: carla actor object
        :type carla_actor: carla.Actor
        :param parent: the parent of this
        :type parent: carla_ros_bridge.Parent
        """
        super(EgoVehicle, self).__init__(carla_actor=carla_actor,
                                         parent=parent,
                                         topic_prefix=carla_actor.attributes.get('role_name'),
                                         append_role_name_topic_postfix=False)

        self.vehicle_info_published = False
        self.planned_trajectory = None

        self.control_subscriber = rospy.Subscriber(
            self.topic_name() + "/vehicle_control_cmd",
            CarlaEgoVehicleControl, self.control_command_updated)

        self.enable_autopilot_subscriber = rospy.Subscriber(
            self.topic_name() + "/enable_autopilot",
            Bool, self.enable_autopilot_updated)

        cyber.init()
        self.cyber_node = cyber.Node('carla_ego_node')
        self.cyber_node.create_reader('/apollo/control', ControlCommand, self.cyber_control_command_updated)
        self.cyber_node.create_reader('/apollo/planning', ADCTrajectory, self.planning_callback)

    def get_marker_color(self):
        """
        Function (override) to return the color for marker messages.

        The ego vehicle uses a different marker color than other vehicles.

        :return: the color used by a ego vehicle marker
        :rtpye : std_msgs.msg.ColorRGBA
        """
        color = ColorRGBA()
        color.r = 0
        color.g = 255
        color.b = 0
        return color

    def planning_callback(self, msg):
        self.planned_trajectory = ADCTrajectory()
        self.planned_trajectory.CopyFrom(msg)

    def send_vehicle_msgs(self):
        """
        Function (override) to send odometry message of the ego vehicle
        instead of an object message.

        The ego vehicle doesn't send its information as part of the object list.
        A nav_msgs.msg.Odometry is prepared to be published via '/carla/ego_vehicle'

        :return:
        """
        vehicle_status = CarlaEgoVehicleStatus()
        vehicle_status.header.stamp = self.get_current_ros_time()
        vehicle_status.velocity = self.get_vehicle_speed_abs(self.carla_actor)
        vehicle_status.acceleration = self.get_vehicle_acceleration_abs(self.carla_actor)
        vehicle_status.orientation = self.get_current_ros_pose().orientation
        vehicle_status.control.throttle = self.carla_actor.get_control().throttle
        vehicle_status.control.steer = self.carla_actor.get_control().steer
        vehicle_status.control.brake = self.carla_actor.get_control().brake
        vehicle_status.control.hand_brake = self.carla_actor.get_control().hand_brake
        vehicle_status.control.reverse = self.carla_actor.get_control().reverse
        vehicle_status.control.gear = self.carla_actor.get_control().gear
        vehicle_status.control.manual_gear_shift = self.carla_actor.get_control().manual_gear_shift
        self.publish_ros_message(self.topic_name() + "/vehicle_status", vehicle_status)

        chassis_msg = Chassis()
        chassis_msg.engine_started = True
        chassis_msg.speed_mps = self.get_vehicle_speed_abs(self.carla_actor)
        chassis_msg.throttle_percentage = self.carla_actor.get_control().throttle * 100.0
        chassis_msg.brake_percentage = self.carla_actor.get_control().brake * 100.0
        chassis_msg.steering_percentage = self.carla_actor.get_control().steer * 100.0
        chassis_msg.parking_brake = self.carla_actor.get_control().hand_brake
        chassis_msg.header.CopyFrom(self.get_cyber_header())
        chassis_msg.driving_mode = Chassis.DrivingMode.COMPLETE_AUTO_DRIVE
        self.write_cyber_message('/apollo/canbus/chassis', chassis_msg)

        if not self.vehicle_info_published:
            self.vehicle_info_published = True
            vehicle_info = CarlaEgoVehicleInfo()
            vehicle_info.type = self.carla_actor.type_id
            vehicle_info.rolename = self.carla_actor.attributes.get('role_name')
            vehicle_physics = self.carla_actor.get_physics_control()

            for wheel in vehicle_physics.wheels:
                wheel_info = CarlaEgoVehicleInfoWheel()
                wheel_info.tire_friction = wheel.tire_friction
                wheel_info.damping_rate = wheel.damping_rate
                wheel_info.steer_angle = math.radians(wheel.steer_angle)
                wheel_info.disable_steering = wheel.disable_steering
                vehicle_info.wheels.append(wheel_info)

            vehicle_info.max_rpm = vehicle_physics.max_rpm
            vehicle_info.max_rpm = vehicle_physics.max_rpm
            vehicle_info.moi = vehicle_physics.moi
            vehicle_info.damping_rate_full_throttle = vehicle_physics.damping_rate_full_throttle
            vehicle_info.damping_rate_zero_throttle_clutch_engaged = \
                vehicle_physics.damping_rate_zero_throttle_clutch_engaged
            vehicle_info.damping_rate_zero_throttle_clutch_disengaged = \
                vehicle_physics.damping_rate_zero_throttle_clutch_disengaged
            vehicle_info.use_gear_autobox = vehicle_physics.use_gear_autobox
            vehicle_info.gear_switch_time = vehicle_physics.gear_switch_time
            vehicle_info.clutch_strength = vehicle_physics.clutch_strength
            vehicle_info.mass = vehicle_physics.mass
            vehicle_info.drag_coefficient = vehicle_physics.drag_coefficient
            vehicle_info.center_of_mass.x = vehicle_physics.center_of_mass.x
            vehicle_info.center_of_mass.y = vehicle_physics.center_of_mass.y
            vehicle_info.center_of_mass.z = vehicle_physics.center_of_mass.z

            self.publish_ros_message(self.topic_name() + "/vehicle_info", vehicle_info, True)

        # @todo: do we still need this?
        if not self.parent.get_param("challenge_mode"):
            odometry = Odometry(header=self.get_msg_header())
            odometry.child_frame_id = self.get_frame_id()
            odometry.pose.pose = self.get_current_ros_pose()
            odometry.twist.twist = self.get_current_ros_twist()

            self.publish_ros_message(self.topic_name() + "/odometry", odometry)
            q = [odometry.pose.pose.orientation.x, \
                    odometry.pose.pose.orientation.y, \
                    odometry.pose.pose.orientation.z, \
                    odometry.pose.pose.orientation.w]
            localization_msg = LocalizationEstimate()
            localization_msg.header.timestamp_sec = cyber_time.Time.now().to_sec()
            localization_msg.header.frame_id = 'novatel'
            localization_msg.pose.position.x = odometry.pose.pose.position.x
            localization_msg.pose.position.y = odometry.pose.pose.position.y
            localization_msg.pose.position.z = 0
            localization_msg.pose.linear_velocity.x = odometry.twist.twist.linear.x
            localization_msg.pose.linear_velocity.y = odometry.twist.twist.linear.y
            localization_msg.pose.linear_velocity.z = odometry.twist.twist.linear.z
            localization_msg.pose.angular_velocity_vrf.x = odometry.twist.twist.angular.x 
            localization_msg.pose.angular_velocity_vrf.y = odometry.twist.twist.angular.y 
            localization_msg.pose.angular_velocity_vrf.z = odometry.twist.twist.angular.z 
            # TODO: fix this
            localization_msg.pose.linear_acceleration_vrf.x = 0
            localization_msg.pose.linear_acceleration_vrf.y = 0
            localization_msg.pose.linear_acceleration_vrf.z = 0
            _, _, localization_msg.pose.heading = tf.transformations.euler_from_quaternion(q)
            self.write_cyber_message('/apollo/localization/pose', localization_msg)

    def update(self):
        """
        Function (override) to update this object.

        On update ego vehicle calculates and sends the new values for VehicleControl()

        :return:
        """
        objects = super(EgoVehicle, self).get_filtered_objectarray(self.carla_actor.id)
        self.publish_ros_message(self.topic_name() + '/objects', objects)
        self.send_vehicle_msgs()
        self.set_pose()
        super(EgoVehicle, self).update()

    def set_pose(self):
        if self.planned_trajectory is None:
            return
        timestamp = cyber_time.Time.now().to_sec()
        transform = self.carla_actor.get_transform()
        dt = timestamp - self.planned_trajectory.header.timestamp_sec
        for tp in self.planned_trajectory.trajectory_point:
            if dt < tp.relative_time:
                #TODO: linear interpolation here
                transform.location.x = tp.path_point.x
                transform.location.y = -tp.path_point.y
                transform.rotation.yaw = -math.degrees(tp.path_point.theta)
                self.carla_actor.set_transform(transform)
                self.carla_actor.set_velocity(transform.rotation.get_forward_vector() * tp.v)
                return

    def destroy(self):
        """
        Function (override) to destroy this object.

        Terminate ROS subscription on CarlaEgoVehicleControl commands.
        Finally forward call to super class.

        :return:
        """
        rospy.logdebug("Destroy Vehicle(id={})".format(self.get_id()))
        self.control_subscriber.unregister()
        self.control_subscriber = None
        self.enable_autopilot_subscriber.unregister()
        self.enable_autopilot_subscriber = None
        self.cyber_node = None
        cyber.shutdown()
        super(EgoVehicle, self).destroy()

    def control_command_updated(self, ros_vehicle_control):
        """
        Receive a CarlaEgoVehicleControl msg and send to CARLA

        This function gets called whenever a ROS message is received via
        '/carla/ego_vehicle/vehicle_control_cmd' topic.
        The received ROS message is converted into carla.VehicleControl command and
        sent to CARLA.
        This bridge is not responsible for any restrictions on velocity or steering.
        It's just forwarding the ROS input to CARLA

        :param ros_vehicle_control: current vehicle control input received via ROS
        :type ros_vehicle_control: carla_ros_bridge_msgs.msg.CarlaEgoVehicleControl
        :return:
        """
        vehicle_control = VehicleControl()
        vehicle_control.hand_brake = ros_vehicle_control.hand_brake
        vehicle_control.brake = ros_vehicle_control.brake
        vehicle_control.steer = ros_vehicle_control.steer
        vehicle_control.throttle = ros_vehicle_control.throttle
        vehicle_control.reverse = ros_vehicle_control.reverse
        self.carla_actor.apply_control(vehicle_control)

    def cyber_control_command_updated(self, cyber_vehicle_control):
        vehicle_control = VehicleControl()
        vehicle_control.hand_brake = cyber_vehicle_control.parking_brake
        vehicle_control.brake = cyber_vehicle_control.brake / 100.0
        vehicle_control.steer = -cyber_vehicle_control.steering_target / 100.0
        vehicle_control.throttle = cyber_vehicle_control.throttle / 100.0
        vehicle_control.reverse = cyber_vehicle_control.gear_location == Chassis.GearPosition.GEAR_REVERSE
        self.carla_actor.apply_control(vehicle_control)

    def enable_autopilot_updated(self, enable_auto_pilot):
        """
        Enable/disable auto pilot

        :param enable_auto_pilot: should the autopilot be enabled?
        :type enable_auto_pilot: std_msgs.Bool
        :return:
        """
        rospy.logdebug("Ego vehicle: Set autopilot to {}".format(enable_auto_pilot.data))
        self.carla_actor.set_autopilot(enable_auto_pilot.data)

    @staticmethod
    def get_vector_length_squared(carla_vector):
        """
        Calculate the squared length of a carla_vector
        :param carla_vector: the carla vector
        :type carla_vector: carla.Vector3D
        :return: squared vector length
        :rtype: float64
        """
        return carla_vector.x * carla_vector.x + \
            carla_vector.y * carla_vector.y + \
            carla_vector.z * carla_vector.z

    @staticmethod
    def get_vehicle_speed_squared(carla_vehicle):
        """
        Get the squared speed of a carla vehicle
        :param carla_vehicle: the carla vehicle
        :type carla_vehicle: carla.Vehicle
        :return: squared speed of a carla vehicle [(m/s)^2]
        :rtype: float64
        """
        return EgoVehicle.get_vector_length_squared(carla_vehicle.get_velocity())

    @staticmethod
    def get_vehicle_speed_abs(carla_vehicle):
        """
        Get the absolute speed of a carla vehicle
        :param carla_vehicle: the carla vehicle
        :type carla_vehicle: carla.Vehicle
        :return: speed of a carla vehicle [m/s >= 0]
        :rtype: float64
        """
        speed = math.sqrt(EgoVehicle.get_vehicle_speed_squared(carla_vehicle))
        return speed

    @staticmethod
    def get_vehicle_acceleration_abs(carla_vehicle):
        """
        Get the absolute acceleration of a carla vehicle
        :param carla_vehicle: the carla vehicle
        :type carla_vehicle: carla.Vehicle
        :return: vehicle acceleration value [m/s^2 >=0]
        :rtype: float64
        """
        return math.sqrt(EgoVehicle.get_vector_length_squared(carla_vehicle.get_acceleration()))
