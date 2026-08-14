# auv_sensors

Final architecture placeholder for sensor abstraction.

Simulation and real hardware must expose the same `/auv/*` sensor contracts. Implement sensor-specific drivers/wrappers here without putting Gazebo-specific topic names into mission logic.

Planned inputs include stereo camera, IMU, depth and DVL/odometry.
