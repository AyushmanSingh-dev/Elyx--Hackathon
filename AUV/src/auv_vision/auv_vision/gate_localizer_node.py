#!/usr/bin/env python3
"""Production 2D -> 3D gate-centre localizer.

YOLO supplies one bounding box for the whole gate. This node uses the YOLO
bbox centre and robust stereo disparity sampling around that centre. It does
not infer poles or gate orientation.
"""

import math
import time

import message_filters
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo
from stereo_msgs.msg import DisparityImage
from std_msgs.msg import Float32MultiArray


class GateLocalizerNode(Node):
    def __init__(self):
        super().__init__('gate_localizer_node')

        self.detection_topic = self.declare_parameter('detection_topic', '/auv/gate_detection_2d').value
        self.disparity_topic = self.declare_parameter('disparity_topic', '/auv/disparity').value
        self.camera_info_topic = self.declare_parameter('camera_info_topic', '/auv/camera_info').value
        self.output_topic = self.declare_parameter('output_topic', '/auv/gate_position_3d').value

        self.stereo_baseline_m = float(self.declare_parameter('stereo_baseline_m', 0.12).value)
        self.camera_offset_fwd_m = float(self.declare_parameter('camera_offset_fwd_m', 0.30).value)
        self.camera_offset_left_m = float(self.declare_parameter('camera_offset_left_m', 0.06).value)
        self.camera_offset_up_m = float(self.declare_parameter('camera_offset_up_m', 0.00).value)

        self.confidence_threshold = float(self.declare_parameter('confidence_threshold', 0.30).value)
        self.detection_timeout_s = float(self.declare_parameter('detection_timeout_s', 0.50).value)
        self.patch_radius_px = int(self.declare_parameter('disparity_patch_radius_px', 4).value)
        self.min_valid_disparity_pixels = int(self.declare_parameter('min_valid_disparity_pixels', 5).value)
        self.disparity_min = float(self.declare_parameter('disparity_min_px', 0.5).value)
        self.center_search_radius_px = int(self.declare_parameter('center_search_radius_px', 12).value)
        self.center_search_step_px = int(self.declare_parameter('center_search_step_px', 4).value)
        self.min_depth_m = float(self.declare_parameter('min_depth_m', 0.30).value)
        self.max_depth_m = float(self.declare_parameter('max_depth_m', 30.0).value)
        self.log_throttle_s = float(self.declare_parameter('log_throttle_s', 1.0).value)

        if self.stereo_baseline_m <= 0.0:
            raise ValueError('stereo_baseline_m must be > 0')
        if self.patch_radius_px < 0:
            raise ValueError('disparity_patch_radius_px must be >= 0')
        if self.min_valid_disparity_pixels < 1:
            raise ValueError('min_valid_disparity_pixels must be >= 1')
        if self.center_search_radius_px < 0:
            raise ValueError('center_search_radius_px must be >= 0')
        if self.center_search_step_px < 1:
            raise ValueError('center_search_step_px must be >= 1')
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError('confidence_threshold must be in [0, 1]')
        if self.min_depth_m <= 0.0 or self.max_depth_m <= self.min_depth_m:
            raise ValueError('invalid depth limits')

        self.bridge = CvBridge()
        self.latest_detection = None
        self.latest_detection_time = None
        self.last_log_time = 0.0

        self.pos_pub = self.create_publisher(Float32MultiArray, self.output_topic, 10)
        self.det_sub = self.create_subscription(Float32MultiArray, self.detection_topic, self.detection_callback, 10)
        self.disp_sub = message_filters.Subscriber(self, DisparityImage, self.disparity_topic)
        self.info_sub = message_filters.Subscriber(self, CameraInfo, self.camera_info_topic)
        self.ts = message_filters.ApproximateTimeSynchronizer(
            [self.disp_sub, self.info_sub], queue_size=10, slop=0.10
        )
        self.ts.registerCallback(self.sync_callback)

        self.get_logger().info(
            f'Gate Localizer started | detection={self.detection_topic} | '
            f'disparity={self.disparity_topic} | camera_info={self.camera_info_topic} | '
            f'output={self.output_topic}'
        )

    def detection_callback(self, msg):
        if len(msg.data) < 6:
            self._warn_throttled('Gate detection message has fewer than 6 values.')
            return
        data = tuple(float(v) for v in msg.data[:6])
        if not all(math.isfinite(v) for v in data):
            self._warn_throttled('Gate detection contains non-finite values.')
            return
        self.latest_detection = data
        self.latest_detection_time = time.monotonic()

    def _extract_patch_median(self, disparity, px, py):
        h, w = disparity.shape[:2]
        x, y = int(round(px)), int(round(py))
        x0, x1 = max(0, x - self.patch_radius_px), min(w, x + self.patch_radius_px + 1)
        y0, y1 = max(0, y - self.patch_radius_px), min(h, y + self.patch_radius_px + 1)
        if x0 >= x1 or y0 >= y1:
            return None
        patch = np.asarray(disparity[y0:y1, x0:x1], dtype=np.float32)
        valid = np.isfinite(patch) & (patch >= self.disparity_min)
        values = patch[valid]
        if values.size < self.min_valid_disparity_pixels:
            return None
        return float(np.median(values))

    def _collect_center_disparities(self, disparity, cx, cy, bbox_width, bbox_height):
        h, w = disparity.shape[:2]
        radius_x = min(float(self.center_search_radius_px), max(1.0, 0.20 * bbox_width))
        radius_y = min(float(self.center_search_radius_px), max(1.0, 0.20 * bbox_height))
        values = []
        for dx in range(-int(radius_x), int(radius_x) + 1, self.center_search_step_px):
            for dy in range(-int(radius_y), int(radius_y) + 1, self.center_search_step_px):
                px, py = cx + dx, cy + dy
                if not (0 <= px < w and 0 <= py < h):
                    continue
                d = self._extract_patch_median(disparity, px, py)
                if d is not None and math.isfinite(d):
                    values.append(d)
        return values

    def _robust_center_disparity(self, disparity, cx, cy, bbox_width, bbox_height):
        candidates = self._collect_center_disparities(disparity, cx, cy, bbox_width, bbox_height)
        if not candidates:
            return None
        values = np.asarray(candidates, dtype=np.float32)
        median = float(np.median(values))
        mad = float(np.median(np.abs(values - median)))
        tolerance = max(3.0 * mad, 0.10 * max(abs(median), 1.0)) if mad > 1e-6 else 0.10 * max(abs(median), 1.0)
        filtered = values[np.abs(values - median) <= tolerance]
        return float(np.median(filtered)) if filtered.size else median

    def _disparity_to_body(self, px_x, px_y, disparity_value, fx, cx_camera, cy_camera):
        if not math.isfinite(disparity_value) or disparity_value < self.disparity_min or fx <= 0.0:
            return None
        depth = fx * self.stereo_baseline_m / disparity_value
        if not math.isfinite(depth) or not self.min_depth_m <= depth <= self.max_depth_m:
            return None
        x_right = (px_x - cx_camera) * depth / fx
        y_down = (px_y - cy_camera) * depth / fx
        # Camera: Z forward, X right, Y down -> body: X forward, Y left, Z up.
        # Camera mounting offsets are parameters so the same logic can be
        # used on the real AUV after measurement.
        return (
            float(depth + self.camera_offset_fwd_m),
            float(-x_right + self.camera_offset_left_m),
            float(-y_down + self.camera_offset_up_m),
        )

    def sync_callback(self, disp_msg, info_msg):
        if self.latest_detection is None or self.latest_detection_time is None:
            return
        age = time.monotonic() - self.latest_detection_time
        if age > self.detection_timeout_s:
            self._warn_throttled(f'Gate detection is stale ({age:.2f}s).')
            return

        detected, cx, cy, bbox_w, bbox_h, confidence = self.latest_detection
        if detected <= 0.0 or confidence < self.confidence_threshold:
            return
        if bbox_w <= 1.0 or bbox_h <= 1.0:
            return

        try:
            disparity = self.bridge.imgmsg_to_cv2(disp_msg.image, desired_encoding='passthrough')
        except Exception as exc:
            self._warn_throttled(f'CV Bridge conversion failed: {exc}')
            return
        disparity = np.asarray(disparity)
        if disparity.ndim != 2:
            return

        fx = float(info_msg.k[0])
        camera_cx = float(info_msg.k[2])
        camera_cy = float(info_msg.k[5])
        if not all(math.isfinite(v) for v in (fx, camera_cx, camera_cy)) or fx <= 0.0:
            return

        robust_disparity = self._robust_center_disparity(disparity, cx, cy, bbox_w, bbox_h)
        if robust_disparity is None:
            self._warn_throttled('No reliable disparity around gate centre.')
            return

        point = self._disparity_to_body(cx, cy, robust_disparity, fx, camera_cx, camera_cy)
        if point is None:
            return

        output = Float32MultiArray()
        output.data = [point[0], point[1], point[2], confidence]
        self.pos_pub.publish(output)
        self._info_throttled(
            f'Gate centre 3D -> X:{point[0]:.2f}m Y:{point[1]:.2f}m Z:{point[2]:.2f}m '
            f'conf:{confidence:.2f} disp:{robust_disparity:.2f}px'
        )

    def _warn_throttled(self, message):
        now = time.monotonic()
        if now - self.last_log_time >= self.log_throttle_s:
            self.get_logger().warn(message)
            self.last_log_time = now

    def _info_throttled(self, message):
        now = time.monotonic()
        if now - self.last_log_time >= self.log_throttle_s:
            self.get_logger().info(message)
            self.last_log_time = now


def main(args=None):
    rclpy.init(args=args)
    node = GateLocalizerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
