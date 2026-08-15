#!/usr/bin/env python3
"""YOLO bin detector using class 1 of the shared trained model."""

import os
import time
import cv2
import torch
import rclpy
from ament_index_python.packages import get_package_share_directory
from auv_msgs.msg import BinDetection2D
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image
from ultralytics import YOLO


class BinDetectorNode(Node):
    def __init__(self):
        super().__init__('bin_detector_node')
        self.model_relative_path = self.declare_parameter('model_relative_path', 'weights/yolo26n.pt').value
        self.image_topic = self.declare_parameter('image_topic', '/auv/camera/left/image_raw').value
        self.detection_topic = self.declare_parameter('detection_topic', '/auv/bin_detection_2d').value
        self.bin_class_ids = [int(v) for v in self.declare_parameter('bin_class_ids', [1]).value]
        self.confidence_threshold = float(self.declare_parameter('confidence_threshold', 0.30).value)
        self.iou_threshold = float(self.declare_parameter('iou_threshold', 0.70).value)
        self.image_size = int(self.declare_parameter('image_size', 640).value)
        requested_device = str(self.declare_parameter('device', 'cpu').value)
        self.device = self._resolve_device(requested_device)
        self.debug_enabled = bool(self.declare_parameter('debug_enabled', True).value)
        self.debug_directory = os.path.expanduser(
            self.declare_parameter('debug_directory', '~/auv_ws/debug/yolo').value
        )
        self.log_detection_period_s = float(self.declare_parameter('log_detection_period_s', 1.0).value)

        package_share = get_package_share_directory('auv_vision')
        self.weights_path = os.path.join(package_share, self.model_relative_path)
        self.model = None
        if os.path.isfile(self.weights_path):
            try:
                self.get_logger().info(
                    f'Loading YOLO model: {self.weights_path} | device={self.device}'
                )
                self.model = YOLO(self.weights_path)
            except Exception as exc:
                self.get_logger().error(
                    f'Could not load YOLO weights; bin detector will idle: {exc}'
                )
        else:
            self.get_logger().warn(
                f'YOLO weights not found: {self.weights_path}. '
                'Bin perception will remain idle.'
            )

        if self.debug_enabled:
            try:
                os.makedirs(self.debug_directory, exist_ok=True)
            except OSError:
                self.debug_enabled = False

        self.cv_bridge = CvBridge()
        self._last_log_time = 0.0
        self.detection_pub = self.create_publisher(BinDetection2D, self.detection_topic, 10)
        self.image_sub = self.create_subscription(Image, self.image_topic, self.image_callback, 10)

    def _resolve_device(self, requested_device):
        normalized = requested_device.strip().lower()
        if normalized in {'cpu', 'mps'}:
            return normalized
        if normalized.isdigit() and not torch.cuda.is_available():
            self.get_logger().warn(
                f'Requested CUDA device {requested_device}, but CUDA is unavailable; using CPU.'
            )
            return 'cpu'
        return requested_device

    def _publish_no_detection(self):
        self.detection_pub.publish(BinDetection2D(detected=False))

    def _log(self, level, text):
        now = time.monotonic()
        if self.log_detection_period_s == 0 or now - self._last_log_time >= self.log_detection_period_s:
            getattr(self.get_logger(), level)(text)
            self._last_log_time = now

    def image_callback(self, msg):
        if self.model is None:
            self._publish_no_detection()
            return
        try:
            image = self.cv_bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception as exc:
            self._log('error', f'Image conversion failed: {exc}')
            self._publish_no_detection()
            return

        try:
            results = self.model.predict(
                source=image,
                verbose=False,
                conf=self.confidence_threshold,
                iou=self.iou_threshold,
                imgsz=self.image_size,
                device=self.device,
            )
        except Exception as exc:
            self._log('error', f'YOLO inference failed: {exc}')
            self._publish_no_detection()
            return

        if not results:
            self._publish_no_detection()
            return

        result = results[0]
        best = None
        boxes = getattr(result, 'boxes', None)
        if self.debug_enabled:
            try:
                cv2.imwrite(
                    os.path.join(self.debug_directory, 'latest_bin_detection.jpg'),
                    result.plot(),
                )
            except Exception:
                pass

        if boxes is not None:
            for box in boxes:
                try:
                    cid = int(box.cls[0])
                    conf = float(box.conf[0])
                    if cid not in self.bin_class_ids or conf < self.confidence_threshold:
                        continue
                    cx, cy, w, h = [float(v) for v in box.xywh[0].tolist()]
                    if w > 0 and h > 0 and (best is None or conf > best[0]):
                        best = (conf, cx, cy, w, h)
                except (TypeError, ValueError, IndexError):
                    pass

        if best is None:
            self._publish_no_detection()
            return

        conf, cx, cy, w, h = best
        out = BinDetection2D(
            detected=True,
            center_x_px=cx,
            center_y_px=cy,
            width_px=w,
            height_px=h,
            confidence=conf,
        )
        self.detection_pub.publish(out)
        self._log('info', f'Bin detected | center=({cx:.1f},{cy:.1f}) | conf={conf:.2f}')


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
