#!/usr/bin/env python3
"""Real-hardware mission bringup.

The same mission executables used in simulation are started here. A selected
hardware-driver launch may be supplied to provide the /auv/* sensor/actuator
contracts. No Gazebo topic names are present in this file.
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, LogInfo, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _optional_hardware_launch(context):
    path = LaunchConfiguration('hardware_launch_file').perform(context).strip()
    if not path:
        return []
    return [IncludeLaunchDescription(PythonLaunchDescriptionSource(path))]


def generate_launch_description():
    bringup_share = get_package_share_directory('auv_bringup')
    default_params = os.path.join(bringup_share, 'config', 'real_params.yaml')
    params_arg = DeclareLaunchArgument('params_file', default_value=default_params)
    hardware_arg = DeclareLaunchArgument(
        'hardware_launch_file', default_value='',
        description='Optional launch file for real camera/DVL/IMU/thruster drivers.'
    )
    params_file = LaunchConfiguration('params_file')

    return LaunchDescription([
        params_arg, hardware_arg,
        OpaqueFunction(function=_optional_hardware_launch),
        LogInfo(msg='[mission] Starting production mission nodes (REAL)...'),
        Node(package='auv_vision', executable='gate_detector_node', name='gate_detector_node', output='screen', parameters=[params_file]),
        Node(package='auv_vision', executable='gate_localizer_node', name='gate_localizer_node', output='screen', parameters=[params_file]),
        Node(package='auv_telemetry', executable='mission_logger_node', name='mission_logger_node', output='screen', parameters=[params_file]),
        Node(package='auv_telemetry', executable='trail_mapper_node', name='trail_mapper_node', output='screen', parameters=[params_file]),
        Node(package='auv_planner', executable='gate_navigator_node', name='gate_navigator_node', output='screen', parameters=[params_file]),
        Node(package='auv_telemetry', executable='mission_monitor_node', name='mission_monitor_node', output='screen', parameters=[params_file]),
    ])


if __name__ == '__main__':
    generate_launch_description()
