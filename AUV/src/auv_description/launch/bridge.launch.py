#!/usr/bin/env python3
"""Gazebo-only hardware abstraction bridge.

Gazebo-specific /model/auv_box/* names are deliberately confined here.
Mission nodes consume only /auv/* interfaces.
"""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    image_bridge = Node(
        package='ros_gz_image',
        executable='image_bridge',
        arguments=[
            '/model/auv_box/stereo_front/left/image_raw',
            '/model/auv_box/stereo_front/right/image_raw',
        ],
        remappings=[
            ('/model/auv_box/stereo_front/left/image_raw', '/auv/camera/left/image_raw'),
            ('/model/auv_box/stereo_front/right/image_raw', '/auv/camera/right/image_raw'),
        ],
        output='screen',
    )

    parameter_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        remappings=[
            ('/model/auv_box/cmd_vel', '/auv/cmd_vel'),
            ('/model/auv_box/odometry', '/auv/odom'),
            ('/model/auv_box/stereo_front/left/camera_info', '/auv/camera/left/camera_info'),
            ('/model/auv_box/stereo_front/right/camera_info', '/auv/camera/right/camera_info'),
        ],
        arguments=[
            '/model/auv_box/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist',
            '/model/auv_box/odometry@nav_msgs/msg/Odometry[gz.msgs.Odometry',
            '/model/auv_box/stereo_front/left/camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo',
            '/model/auv_box/stereo_front/right/camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo',
        ],
        output='screen',
    )

    return LaunchDescription([image_bridge, parameter_bridge])


if __name__ == '__main__':
    generate_launch_description()
