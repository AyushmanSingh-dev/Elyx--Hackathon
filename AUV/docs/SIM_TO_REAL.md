# Sim-to-real design contract

## Non-negotiable rule

Changing from Gazebo to real sensors/actuators must not require mission-node business-logic edits. Hardware differences are expressed through `/auv/*` topic contracts, remapping, launch files and parameter YAML.

## Simulation

`Gazebo -> auv_description/launch/bridge.launch.py -> /auv/* -> mission nodes -> sim_params.yaml`

The only code allowed to contain `/model/auv_box/*` names is the Gazebo model/bridge layer.

## Real hardware

`camera/DVL/IMU/thruster drivers -> /auv/* -> same mission nodes -> real_params.yaml`

`mission.launch.py` accepts an optional hardware-driver launch file.

## Gate perception contract

YOLO class `0` is the complete gate. One frame produces at most one gate detection:

`[detected, cx, cy, width, height, confidence, compatibility_flag]`

The stereo localizer samples disparity around the **YOLO bbox centre** and publishes:

`[x_fwd, y_left, z_up, confidence]`

No pole reconstruction or gate orientation is required.

## Mapping contract

Repeated gate detections are clustered. The mapper displays a thin cuboid centred on the clustered gate position instead of many crosses, avoiding the false impression that every noisy detection is a separate gate.

## Real-hardware values to measure

- Stereo baseline
- Camera forward/left/up mounting offsets
- Fixed localization frame (`odom` or the final TF frame)
- Real camera/DVL/IMU/thruster driver topic contracts
- Onboard YOLO compute device

## Known external artifact

`gate_detector_v2.pt` is not committed by this migration because the binary model was not available in the accessible workspace. Place it at `src/auv_vision/weights/gate_detector_v2.pt` or change `model_relative_path` in YAML.
