# AUV System Architecture

The repository uses a fixed final package architecture while implementation is incremental.

```text
auv_sensors -> auv_vision -> auv_planner -> auv_controls -> auv_propulsion
      |              |              |              |
      +--------------+--------------+--------------+--> auv_telemetry

auv_msgs defines stable interfaces between packages.
auv_description owns simulation assets and the Gazebo bridge.
auv_bringup owns simulation/real launch composition and parameter files.
auv_teleop provides a manual command path through the same abstract command interface.
```

## Current implementation

Implemented and being validated:
- `auv_bringup`
- `auv_description`
- `auv_vision`
- `auv_planner`
- `auv_telemetry`

Architecture skeleton added for gradual implementation:
- `auv_msgs`
- `auv_sensors`
- `auv_controls`
- `auv_propulsion`
- `auv_teleop`

## Development rule

Do not add simulation-only logic to business nodes. Gazebo-specific topic names belong only in the bridge/launch layer. Hardware changes should be handled by parameters, remaps, or sensor/actuator backend packages.
