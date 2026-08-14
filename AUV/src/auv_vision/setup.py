from setuptools import find_packages, setup
from glob import glob
import os

package_name = 'auv_vision'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'weights'), glob('weights/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    entry_points={
        'console_scripts': [
            'gate_detector_node = auv_vision.gate_detector_node:main',
            'gate_localizer_node = auv_vision.gate_localizer_node:main',
            'bin_detector_node = auv_vision.bin_detector_node:main',
        ],
    },
)
