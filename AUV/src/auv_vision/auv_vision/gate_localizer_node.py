#!/usr/bin/env python3
"""Production 2D -> 3D gate-centre localizer.

YOLO detects the whole gate as one object. This node uses the YOLO bbox
centre and robust stereo disparity sampling around that centre. It does not
infer poles or gate orientation.

Coordinates use body-aligned axes but remain referenced to the camera origin;
the navigator/mapper apply the parameterized camera-to-AUV translation.
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
        if self.stereo_baseline_m <= 0 or self.patch_radius_px < 0 or self.min_valid_disparity_pixels < 1:
            raise ValueError('invalid stereo sampling parameters')
        if self.center_search_radius_px < 0 or self.center_search_step_px < 1:
            raise ValueError('invalid centre search parameters')
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError('confidence_threshold must be in [0,1]')
        if self.min_depth_m <= 0 or self.max_depth_m <= self.min_depth_m:
            raise ValueError('invalid depth limits')

        self.bridge = CvBridge()
        self.latest_detection = None
        self.latest_detection_time = None
        self.last_log_time = 0.0
        self.pos_pub = self.create_publisher(Float32MultiArray, self.output_topic, 10)
        self.create_subscription(Float32MultiArray, self.detection_topic, self.detection_callback, 10)
        disp_sub = message_filters.Subscriber(self, DisparityImage, self.disparity_topic)
        info_sub = message_filters.Subscriber(self, CameraInfo, self.camera_info_topic)
        self.ts = message_filters.ApproximateTimeSynchronizer([disp_sub, info_sub], queue_size=10, slop=0.10)
        self.ts.registerCallback(self.sync_callback)

    def detection_callback(self, msg):
        if len(msg.data) < 6:
            return
        data = tuple(float(v) for v in msg.data[:6])
        if all(math.isfinite(v) for v in data):
            self.latest_detection = data
            self.latest_detection_time = time.monotonic()

    def _patch_median(self, disparity, px, py):
        h, w = disparity.shape[:2]
        x, y = int(round(px)), int(round(py))
        x0, x1 = max(0, x-self.patch_radius_px), min(w, x+self.patch_radius_px+1)
        y0, y1 = max(0, y-self.patch_radius_px), min(h, y+self.patch_radius_px+1)
        patch = np.asarray(disparity[y0:y1, x0:x1], dtype=np.float32)
        values = patch[np.isfinite(patch) & (patch >= self.disparity_min)]
        if values.size < self.min_valid_disparity_pixels:
            return None
        return float(np.median(values))

    def _robust_center_disparity(self, disparity, cx, cy, bw, bh):
        rx = min(float(self.center_search_radius_px), max(1.0, 0.20*bw))
        ry = min(float(self.center_search_radius_px), max(1.0, 0.20*bh))
        h, w = disparity.shape[:2]
        vals = []
        for dx in range(-int(rx), int(rx)+1, self.center_search_step_px):
            for dy in range(-int(ry), int(ry)+1, self.center_search_step_px):
                px, py = cx+dx, cy+dy
                if 0 <= px < w and 0 <= py < h:
                    d = self._patch_median(disparity, px, py)
                    if d is not None and math.isfinite(d):
                        vals.append(d)
        if not vals:
            return None
        v = np.asarray(vals, dtype=np.float32)
        med = float(np.median(v))
        mad = float(np.median(np.abs(v-med)))
        tol = max(3.0*mad, 0.10*max(abs(med),1.0)) if mad > 1e-6 else 0.10*max(abs(med),1.0)
        keep = v[np.abs(v-med) <= tol]
        return float(np.median(keep)) if keep.size else med

    def sync_callback(self, disp_msg, info_msg):
        if self.latest_detection is None or self.latest_detection_time is None:
            return
        if time.monotonic() - self.latest_detection_time > self.detection_timeout_s:
            return
        detected, cx, cy, bw, bh, confidence = self.latest_detection
        if detected <= 0 or confidence < self.confidence_threshold or bw <= 1 or bh <= 1:
            return
        try:
            disparity = np.asarray(self.bridge.imgmsg_to_cv2(disp_msg.image, desired_encoding='passthrough'))
        except Exception as exc:
            self._warn(f'CV Bridge conversion failed: {exc}')
            return
        if disparity.ndim != 2:
            return
        fx, ccx, ccy = float(info_msg.k[0]), float(info_msg.k[2]), float(info_msg.k[5])
        if fx <= 0 or not all(math.isfinite(v) for v in (fx, ccx, ccy)):
            return
        d = self._robust_center_disparity(disparity, cx, cy, bw, bh)
        if d is None:
            self._warn('No reliable disparity around gate centre.')
            return
        depth = fx * self.stereo_baseline_m / d
        if not self.min_depth_m <= depth <= self.max_depth_m:
            return
        x_right = (cx-ccx)*depth/fx
        y_down = (cy-ccy)*depth/fx
        out = Float32MultiArray()
        out.data = [float(depth), float(-x_right), float(-y_down), float(confidence)]
        self.pos_pub.publish(out)

    def _warn(self, text):
        now = time.monotonic()
        if now-self.last_log_time >= self.log_throttle_s:
            self.get_logger().warn(text)
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
