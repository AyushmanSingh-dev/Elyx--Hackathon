#!/usr/bin/env python3
"""Production simulation bringup.

Gazebo-specific knowledge is restricted to the description bridge/model layer.
Mission nodes consume only /auv/* topics and all node tuning comes from YAML.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription, LogInfo, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    bringup_share = get_package_share_directory('auv_bringup')
    desc_share = get_package_share_directory('auv_description')
    stereo_share = get_package_share_directory('stereo_image_proc')

    params_file = os.path.join(bringup_share, 'config', 'sim_params.yaml')
    world_default = os.path.join(desc_share, 'worlds', 'camera_test.sdf')
    model_sdf = os.path.join(desc_share, 'models', 'auv_box', 'model.sdf')
    bridge_launch = os.path.join(desc_share, 'launch', 'bridge.launch.py')

    world_arg = DeclareLaunchArgument('world', default_value=world_default)
    spawn_x_arg = DeclareLaunchArgument('spawn_x', default_value='-5.0')
    spawn_y_arg = DeclareLaunchArgument('spawn_y', default_value='-4.0')
    spawn_z_arg = DeclareLaunchArgument('spawn_z', default_value='0.15')
    spawn_yaw_arg = DeclareLaunchArgument('spawn_yaw', default_value='2.7')

    gazebo = ExecuteProcess(
        cmd=['gz', 'sim', '-r', LaunchConfiguration('world')],
        output='screen', name='gazebo'
    )

    spawn = TimerAction(period=8.0, actions=[
        LogInfo(msg='[sim_mission] Spawning AUV...'),
        ExecuteProcess(
            cmd=[
                'ros2', 'run', 'ros_gz_sim', 'create',
                '-world', 'camera_world', '-file', model_sdf,
                '-name', 'auv_box',
                '-x', LaunchConfiguration('spawn_x'),
                '-y', LaunchConfiguration('spawn_y'),
                '-z', LaunchConfiguration('spawn_z'),
                '-Y', LaunchConfiguration('spawn_yaw'),
            ], output='screen', name='spawn_auv'
        )
    ])

    bridge = TimerAction(period=10.0, actions=[
        IncludeLaunchDescription(PythonLaunchDescriptionSource(bridge_launch))
    ])

    stereo = TimerAction(period=12.0, actions=[
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(stereo_share, 'launch', 'stereo_image_proc.launch.py')
            ),
            launch_arguments={
                'left_namespace': '/auv/camera/left',
                'right_namespace': '/auv/camera/right',
            }.items(),
        )
    ])

    nodes = TimerAction(period=14.0, actions=[
        LogInfo(msg='[sim_mission] Starting mission nodes...'),
        Node(package='auv_vision', executable='gate_detector_node', name='gate_detector_node', output='screen', parameters=[params_file]),
        Node(package='auv_vision', executable='gate_localizer_node', name='gate_localizer_node', output='screen', parameters=[params_file]),
        Node(package='auv_telemetry', executable='mission_logger_node', name='mission_logger_node', output='screen', parameters=[params_file]),
        Node(package='auv_telemetry', executable='trail_mapper_node', name='trail_mapper_node', output='screen', parameters=[params_file]),
        Node(package='auv_planner', executable='gate_navigator_node', name='gate_navigator_node', output='screen', parameters=[params_file]),
        Node(package='auv_telemetry', executable='mission_monitor_node', name='mission_monitor_node', output='screen', parameters=[params_file]),
        Node(package='image_view', executable='image_view', name='camera_view', output='screen', remappings=[('image', '/auv/camera/left/image_raw')]),
    ])

    return LaunchDescription([
        world_arg, spawn_x_arg, spawn_y_arg, spawn_z_arg, spawn_yaw_arg,
        gazebo, spawn, bridge, stereo, nodes,
    ])


if __name__ == '__main__':
    generate_launch_description()
