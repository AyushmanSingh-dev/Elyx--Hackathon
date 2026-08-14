#!/usr/bin/env python3
"""Production YOLO bin detector.

The trained AUV model uses class 1 for the bin. This node intentionally has
its own output topic so gate and bin detections remain independent. It publishes
only the highest-confidence valid bin in the current frame.

Temporary message format (until auv_msgs migration):
    [detected, center_x, center_y, width, height, confidence]
"""

import os
import time

import cv2
import rclpy
from ament_index_python.packages import get_package_share_directory
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Float32MultiArray
from ultralytics import YOLO


class BinDetectorNode(Node):
    def __init__(self):
        super().__init__('bin_detector_node')

        self.model_relative_path = self.declare_parameter(
            'model_relative_path', 'weights/gate_detector_v2.pt'
        ).value
        self.image_topic = self.declare_parameter(
            'image_topic', '/auv/camera/left/image_raw'
        ).value
        self.detection_topic = self.declare_parameter(
            'detection_topic', '/auv/bin_detection_2d'
        ).value
        self.bin_class_ids = [
            int(v) for v in self.declare_parameter('bin_class_ids', [1]).value
        ]
        self.confidence_threshold = float(
            self.declare_parameter('confidence_threshold', 0.30).value
        )
        self.iou_threshold = float(
            self.declare_parameter('iou_threshold', 0.70).value
        )
        self.image_size = int(
            self.declare_parameter('image_size', 640).value
        )
        self.device = self.declare_parameter('device', '0').value
        self.debug_enabled = bool(
            self.declare_parameter('debug_enabled', True).value
        )
        self.debug_directory = os.path.expanduser(
            self.declare_parameter(
                'debug_directory', '~/auv_ws/debug/yolo'
            ).value
        )
        self.log_detection_period_s = float(
            self.declare_parameter('log_detection_period_s', 1.0).value
        )

        if not self.bin_class_ids:
            raise ValueError('bin_class_ids cannot be empty')
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError('confidence_threshold must be in [0, 1]')
        if not 0.0 <= self.iou_threshold <= 1.0:
            raise ValueError('iou_threshold must be in [0, 1]')
        if self.image_size <= 0:
            raise ValueError('image_size must be > 0')

        package_share = get_package_share_directory('auv_vision')
        self.weights_path = os.path.join(package_share, self.model_relative_path)
        if not os.path.isfile(self.weights_path):
            raise FileNotFoundError(f'YOLO weights not found: {self.weights_path}')

        self.get_logger().info(f'Loading YOLO model: {self.weights_path}')
        self.model = YOLO(self.weights_path)

        if self.debug_enabled:
            try:
                os.makedirs(self.debug_directory, exist_ok=True)
            except OSError as exc:
                self.get_logger().error(
                    f'Could not create debug directory: {exc}'
                )
                self.debug_enabled = False

        self.cv_bridge = CvBridge()
        self.detection_pub = self.create_publisher(
            Float32MultiArray, self.detection_topic, 10
        )
        self.image_sub = self.create_subscription(
            Image, self.image_topic, self.image_callback, 10
        )
        self._last_log_time = 0.0

        self.get_logger().info(
            f'Bin Detector started | image={self.image_topic} | '
            f'output={self.detection_topic} | classes={self.bin_class_ids} | '
            f'conf={self.confidence_threshold:.2f}'
        )

    def _publish_no_detection(self):
        msg = Float32MultiArray()
        msg.data = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.detection_pub.publish(msg)

    def _log_throttled(self, level, text):
        if self.log_detection_period_s == 0.0:
            getattr(self.get_logger(), level)(text)
            return

        now = time.monotonic()
        if now - self._last_log_time >= self.log_detection_period_s:
            getattr(self.get_logger(), level)(text)
            self._last_log_time = now

    def image_callback(self, msg: Image):
        try:
            cv_image = self.cv_bridge.imgmsg_to_cv2(
                msg, desired_encoding='bgr8'
            )
        except Exception as exc:
            self._log_throttled(
                'error', f'Failed to convert camera image: {exc}'
            )
            self._publish_no_detection()
            return

        if cv_image is None or cv_image.size == 0:
            self._publish_no_detection()
            return

        try:
            results = self.model.predict(
                source=cv_image,
                verbose=False,
                conf=self.confidence_threshold,
                iou=self.iou_threshold,
                imgsz=self.image_size,
                device=self.device,
            )
        except Exception as exc:
            self._log_throttled(
                'error', f'YOLO inference failed: {exc}'
            )
            self._publish_no_detection()
            return

        if not results:
            self._publish_no_detection()
            return

        result = results[0]

        if self.debug_enabled:
            try:
                debug_path = os.path.join(
                    self.debug_directory, 'latest_bin_detection.jpg'
                )
                cv2.imwrite(debug_path, result.plot())
            except Exception as exc:
                self._log_throttled(
                    'warn', f'Failed to save bin debug image: {exc}'
                )

        best = None
        boxes = getattr(result, 'boxes', None)
        if boxes is not None:
            for box in boxes:
                try:
                    class_id = int(box.cls[0])
                    confidence = float(box.conf[0])

                    if (
                        class_id not in self.bin_class_ids
                        or confidence < self.confidence_threshold
                    ):
                        continue

                    cx, cy, width, height = [
                        float(v) for v in box.xywh[0].tolist()
                    ]

                    if width <= 0.0 or height <= 0.0:
                        continue

                    candidate = (
                        confidence,
                        cx,
                        cy,
                        width,
                        height,
                        class_id,
                    )

                    if best is None or confidence > best[0]:
                        best = candidate

                except (TypeError, ValueError, IndexError):
                    continue

        if best is None:
            self._publish_no_detection()
            return

        confidence, cx, cy, width, height, class_id = best

        msg_out = Float32MultiArray()
        msg_out.data = [
            1.0,
            cx,
            cy,
            width,
            height,
            confidence,
        ]
        self.detection_pub.publish(msg_out)

        self._log_throttled(
            'info',
            f'Bin detected | center=({cx:.1f},{cy:.1f}) | '
            f'bbox={width:.0f}x{height:.0f} | conf={confidence:.2f}'
        )


def main(args=None):
    rclpy.init(args=args)
    node = BinDetectorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
