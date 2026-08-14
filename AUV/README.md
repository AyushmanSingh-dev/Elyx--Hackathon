# AUV Production Stack

Production-oriented ROS 2 AUV software stack prepared for simulation-to-real deployment.

## Core rule

Gazebo-specific interfaces are isolated to the bridge layer. Mission nodes consume only `/auv/*` topics, and simulation-vs-real differences are configuration/launch differences rather than business-logic changes.

## Packages

- `auv_bringup` — simulation and real bringup, parameter YAMLs
- `auv_description` — simulation bridge/model resources
- `auv_vision` — YOLO gate detection and stereo 3D gate localization
- `auv_planner` — gate approach/crossing state machine
- `auv_telemetry` — trail mapping, mission logging, mission monitoring

## Gate perception contract

YOLO detects the **whole gate as one object**. The detector publishes the bounding-box centre and dimensions. The localizer uses that centre as the gate centre; it does not infer two poles as two independent YOLO objects.

## Sim-to-real

Simulation:

`Gazebo -> bridge.launch.py -> /auv/* -> mission nodes -> sim_params.yaml`

Real hardware:

`camera/DVL/IMU/thruster drivers -> /auv/* -> same mission nodes -> real_params.yaml`

Before real deployment, replace the physical stereo baseline and camera mounting offsets in `real_params.yaml`, and provide the real hardware launch file that exposes the `/auv/*` contracts.
