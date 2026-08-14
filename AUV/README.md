# AUV Software — Production Stack

Production-oriented ROS 2 AUV mission stack prepared for simulation-to-real deployment.

## Core rule

Gazebo-specific interfaces are isolated to the bridge layer. Mission nodes consume only `/auv/*` topics, and simulation-vs-real differences are configuration/launch differences rather than business-logic changes.

## Packages

- `auv_bringup` — simulation/real launch and parameter YAML
- `auv_description` — Gazebo model, world and bridge
- `auv_vision` — YOLO gate detection and stereo gate-centre localization
- `auv_planner` — center-only gate approach/crossing state machine
- `auv_telemetry` — clustered trail/object mapping, logging and monitoring

## Build

```bash
cd AUV
source /opt/ros/<distro>/setup.bash
colcon build --symlink-install
source install/setup.bash
```

## Simulation

```bash
ros2 launch auv_bringup sim_mission.launch.py
```

## Real hardware

Use the same mission nodes and supply the selected real sensor/actuator launch file:

```bash
ros2 launch auv_bringup mission.launch.py hardware_launch_file:=/path/to/hardware.launch.py
```

The hardware launch must expose the `/auv/*` contracts such as `/auv/odom`, stereo images/camera info, disparity and `/auv/cmd_vel`.

## Gate perception contract

YOLO class `0` represents the **whole gate**. The detector publishes at most one gate detection per frame:

`[detected, center_x_px, center_y_px, bbox_width_px, bbox_height_px, confidence, compatibility_flag]`

The localizer samples stereo disparity around the **YOLO bbox centre** and publishes:

`[x_fwd, y_left, z_up, confidence]`

No pole reconstruction or gate-orientation estimate is required.

## Mapping

Repeated detections are clustered into one gate marker. The mapper displays a thin cuboid around the estimated gate region rather than drawing a cross for every noisy frame.

See `docs/SIM_TO_REAL.md` for the complete transition contract.
