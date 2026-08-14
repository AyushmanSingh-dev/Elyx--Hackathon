from setuptools import find_packages, setup

package_name = 'auv_telemetry'
setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    entry_points={'console_scripts': [
        'trail_mapper_node = auv_telemetry.trail_mapper_node:main',
        'mission_logger_node = auv_telemetry.mission_logger_node:main',
        'mission_monitor_node = auv_telemetry.mission_monitor_node:main',
    ]},
)
