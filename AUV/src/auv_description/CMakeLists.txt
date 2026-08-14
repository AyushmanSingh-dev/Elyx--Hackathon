cmake_minimum_required(VERSION 3.8)
project(auv_description)

find_package(ament_cmake REQUIRED)

# Install all simulation assets used by sim_mission.launch.py.
install(
  DIRECTORY launch models rviz worlds
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
