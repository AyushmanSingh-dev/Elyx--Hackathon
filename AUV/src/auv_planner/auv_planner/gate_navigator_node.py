#!/usr/bin/env python3
"""Production center-only gate navigator.

The perception stack deliberately detects the whole gate as one YOLO object.
Therefore this node navigates using the 3D gate centre and the bearing to that
centre. Gate-plane orientation is not inferred from pole geometry.
"""

import math
from collections import deque

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray, String


class GateNavigatorNode(Node):
    def __init__(self):
        super().__init__('gate_navigator_node')

        self.gate_position_topic = self.declare_parameter('gate_position_topic', '/auv/gate_position_3d').value
        self.odom_topic = self.declare_parameter('odom_topic', '/auv/odom').value
        self.cmd_vel_topic = self.declare_parameter('cmd_vel_topic', '/auv/cmd_vel').value
        self.mission_state_topic = self.declare_parameter('mission_state_topic', '/auv/mission_state').value
        self.debug_topic = self.declare_parameter('debug_topic', '/auv/navigator_debug').value

        self.confidence_threshold = float(self.declare_parameter('confidence_threshold', 0.30).value)
        self.detection_timeout_s = float(self.declare_parameter('detection_timeout_s', 1.5).value)
        self.commit_distance_m = float(self.declare_parameter('commit_distance_m', 5.5).value)
        self.commit_ticks_required = int(self.declare_parameter('commit_ticks_required', 5).value)
        self.smoothing_window = int(self.declare_parameter('smoothing_window', 5).value)
        self.min_center_samples = int(self.declare_parameter('min_center_samples', 3).value)
        self.max_gate_jump_m = float(self.declare_parameter('max_gate_jump_m', 1.0).value)

        # The localizer reports coordinates relative to the camera origin,
        # with body-aligned axes. These translations convert camera origin to
        # the AUV body origin when transforming the point into odometry.
        self.camera_offset_fwd_m = float(self.declare_parameter('camera_offset_fwd_m', 0.30).value)
        self.camera_offset_left_m = float(self.declare_parameter('camera_offset_left_m', 0.06).value)
        self.camera_offset_up_m = float(self.declare_parameter('camera_offset_up_m', 0.00).value)

        self.track_speed_mps = float(self.declare_parameter('track_speed_mps', 0.15).value)
        self.cross_speed_mps = float(self.declare_parameter('cross_speed_mps', 0.20).value)
        self.max_yaw_rate_radps = float(self.declare_parameter('max_yaw_rate_radps', 0.30).value)
        self.track_yaw_kp = float(self.declare_parameter('track_yaw_kp', 1.5).value)
        self.final_yaw_kp = float(self.declare_parameter('final_yaw_kp', 4.0).value)
        self.cross_yaw_kp = float(self.declare_parameter('cross_yaw_kp', 2.0).value)

        self.align_threshold_rad = float(self.declare_parameter('align_threshold_rad', 0.027).value)
        self.align_ticks_required = int(self.declare_parameter('align_ticks_required', 10).value)
        self.heave_kp = float(self.declare_parameter('heave_kp', 1.2).value)
        self.heave_max_mps = float(self.declare_parameter('heave_max_mps', 0.15).value)
        self.heave_align_threshold_m = float(self.declare_parameter('heave_align_threshold_m', 0.05).value)
        self.cross_heave_max_mps = float(self.declare_parameter('cross_heave_max_mps', 0.08).value)
        self.standoff_distance_m = float(self.declare_parameter('standoff_distance_m', 2.0).value)
        self.standoff_reach_threshold_m = float(self.declare_parameter('standoff_reach_threshold_m', 0.15).value)
        self.cross_overshoot_m = float(self.declare_parameter('cross_overshoot_m', 2.5).value)
        self.stop_pause_ticks = int(self.declare_parameter('stop_pause_ticks', 20).value)
        self.control_period_s = float(self.declare_parameter('control_period_s', 0.10).value)
        self.log_every_ticks = int(self.declare_parameter('log_every_ticks', 10).value)

        if self.smoothing_window < 1 or self.min_center_samples < 1:
            raise ValueError('smoothing_window and min_center_samples must be >= 1')
        if self.min_center_samples > self.smoothing_window:
            raise ValueError('min_center_samples cannot exceed smoothing_window')
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError('confidence_threshold must be in [0,1]')
        if self.detection_timeout_s <= 0.0 or self.control_period_s <= 0.0:
            raise ValueError('timeouts/control_period must be > 0')

        self.state = 'SEARCH'
        self.current_x = self.current_y = self.current_z = self.current_yaw = None
        self.latest_gate_time = None
        self.last_gate_confidence = 0.0
        self.gate_center_odom = None
        self.center_buf = deque(maxlen=self.smoothing_window)
        self.target_yaw = None
        self.standoff_point = None
        self.forward_dist_travelled = 0.0
        self.cross_target_distance = 0.0
        self.return_dist_remaining = 0.0
        self.last_track_x = self.last_track_y = None
        self.cross_start_x = self.cross_start_y = None
        self.commit_tick_count = 0
        self.aligned_tick_count = 0
        self.stop_pause_tick = 0
        self.log_tick = 0
        self.done_logged = False
        self._dbg_distance = 0.0
        self._dbg_bearing_error = 0.0
        self._dbg_nav_source = 0.0

        self.create_subscription(Float32MultiArray, self.gate_position_topic, self.gate_position_callback, 10)
        self.create_subscription(Odometry, self.odom_topic, self.odom_callback, 10)
        self.cmd_pub = self.create_publisher(Twist, self.cmd_vel_topic, 10)
        self.mission_pub = self.create_publisher(String, self.mission_state_topic, 10)
        self.debug_pub = self.create_publisher(Float32MultiArray, self.debug_topic, 10)
        self.create_timer(self.control_period_s, self.control_loop)

        self.get_logger().info(
            f'Gate Navigator started | gate={self.gate_position_topic} | odom={self.odom_topic} | '
            f'cmd={self.cmd_vel_topic} | standoff={self.standoff_distance_m:.2f}m'
        )

    @staticmethod
    def normalize_angle(angle):
        return math.atan2(math.sin(angle), math.cos(angle))

    def _body_to_odom(self, x_camera, y_camera, z_camera):
        if None in (self.current_x, self.current_y, self.current_z, self.current_yaw):
            return None
        # Gate localizer coordinates use body-aligned axes but camera origin.
        x_body = x_camera - self.camera_offset_fwd_m
        y_body = y_camera - self.camera_offset_left_m
        z_body = z_camera - self.camera_offset_up_m
        c, s = math.cos(self.current_yaw), math.sin(self.current_yaw)
        return (
            self.current_x + x_body * c - y_body * s,
            self.current_y + x_body * s + y_body * c,
            self.current_z + z_body,
        )

    def _smoothed_center(self):
        if not self.center_buf:
            return None
        n = float(len(self.center_buf))
        return tuple(sum(p[i] for p in self.center_buf) / n for i in range(3))

    def _track_distance(self):
        if self.last_track_x is None:
            self.last_track_x, self.last_track_y = self.current_x, self.current_y
            return
        self.forward_dist_travelled += math.hypot(self.current_x - self.last_track_x, self.current_y - self.last_track_y)
        self.last_track_x, self.last_track_y = self.current_x, self.current_y

    def _fresh(self):
        if self.latest_gate_time is None:
            return False
        age = (self.get_clock().now() - self.latest_gate_time).nanoseconds / 1e9
        return age <= self.detection_timeout_s

    def _set_target_from_gate(self):
        if self.gate_center_odom is None or self.current_x is None:
            return False
        gx, gy, _ = self.gate_center_odom
        dx, dy = gx - self.current_x, gy - self.current_y
        d = math.hypot(dx, dy)
        if d < 1e-3:
            return False
        self.target_yaw = math.atan2(dy, dx)
        ux, uy = dx / d, dy / d
        stand = min(self.standoff_distance_m, max(0.0, d - 0.25))
        self.standoff_point = (gx - ux * stand, gy - uy * stand)
        return True

    def odom_callback(self, msg):
        self.current_x = float(msg.pose.pose.position.x)
        self.current_y = float(msg.pose.pose.position.y)
        self.current_z = float(msg.pose.pose.position.z)
        q = msg.pose.pose.orientation
        self.current_yaw = math.atan2(2.0 * (q.w*q.z + q.x*q.y), 1.0 - 2.0*(q.y*q.y + q.z*q.z))

    def gate_position_callback(self, msg):
        if len(msg.data) < 4:
            return
        x, y, z, confidence = [float(v) for v in msg.data[:4]]
        if not all(math.isfinite(v) for v in (x, y, z, confidence)) or confidence < self.confidence_threshold:
            return
        point = self._body_to_odom(x, y, z)
        if point is None:
            return

        # Freeze an established close-range target; bbox centres become less
        # stable when the gate fills most of the image.
        if self.gate_center_odom is not None and abs(x) < self.standoff_distance_m * 3.0:
            self.latest_gate_time = self.get_clock().now()
            self.last_gate_confidence = confidence
            return

        if self.gate_center_odom is not None:
            jump = math.sqrt(sum((point[i] - self.gate_center_odom[i]) ** 2 for i in range(3)))
            if jump > self.max_gate_jump_m:
                self.get_logger().warn(f'Ignoring gate centre jump {jump:.2f}m > {self.max_gate_jump_m:.2f}m')
                return

        self.center_buf.append(point)
        self.gate_center_odom = self._smoothed_center()
        self.latest_gate_time = self.get_clock().now()
        self.last_gate_confidence = confidence

    def control_loop(self):
        if None in (self.current_x, self.current_y, self.current_z, self.current_yaw):
            return

        self.log_tick += 1
        fresh = self._fresh()
        cmd = Twist()
        next_state = self.state

        if self.state == 'SEARCH':
            self.commit_tick_count = 0
            self.aligned_tick_count = 0
            cmd.angular.z = 0.15
            if fresh and self.gate_center_odom is not None and len(self.center_buf) >= self.min_center_samples:
                self.forward_dist_travelled = 0.0
                self.last_track_x, self.last_track_y = self.current_x, self.current_y
                next_state = 'TRACK'

        elif self.state == 'TRACK':
            self._track_distance()
            if self.gate_center_odom is None:
                next_state = 'SEARCH'
            else:
                gx, gy, gz = self.gate_center_odom
                dx, dy = gx - self.current_x, gy - self.current_y
                distance = math.hypot(dx, dy)
                bearing_error = 0.0 if distance < 1e-3 else self.normalize_angle(math.atan2(dy, dx) - self.current_yaw)
                cmd.linear.x = self.track_speed_mps
                cmd.angular.z = max(-self.max_yaw_rate_radps, min(self.max_yaw_rate_radps, self.track_yaw_kp * bearing_error))
                cmd.linear.z = max(-self.heave_max_mps, min(self.heave_max_mps, self.heave_kp * (gz - self.current_z)))
                self._dbg_distance, self._dbg_bearing_error, self._dbg_nav_source = distance, bearing_error, 1.0 if fresh else 2.0
                if distance <= self.commit_distance_m and len(self.center_buf) >= self.min_center_samples:
                    self.commit_tick_count += 1
                    if self.commit_tick_count >= self.commit_ticks_required and self._set_target_from_gate():
                        next_state = 'APPROACH_STANDOFF'
                else:
                    self.commit_tick_count = 0

        elif self.state == 'APPROACH_STANDOFF':
            self._track_distance()
            if self.gate_center_odom is None:
                next_state = 'SEARCH'
            elif not self._set_target_from_gate():
                next_state = 'TRACK'
            else:
                sx, sy = self.standoff_point
                dx, dy = sx - self.current_x, sy - self.current_y
                distance = math.hypot(dx, dy)
                bearing_error = 0.0 if distance < 1e-3 else self.normalize_angle(math.atan2(dy, dx) - self.current_yaw)
                self._dbg_distance, self._dbg_bearing_error, self._dbg_nav_source = distance, bearing_error, 1.0 if fresh else 2.0
                if distance <= self.standoff_reach_threshold_m:
                    self.aligned_tick_count = 0
                    next_state = 'FINAL_ALIGN'
                else:
                    cmd.linear.x = self.track_speed_mps
                    cmd.angular.z = max(-self.max_yaw_rate_radps, min(self.max_yaw_rate_radps, self.track_yaw_kp * bearing_error))
                    cmd.linear.z = max(-self.heave_max_mps, min(self.heave_max_mps, self.heave_kp * (self.gate_center_odom[2] - self.current_z)))

        elif self.state == 'FINAL_ALIGN':
            if self.gate_center_odom is None:
                next_state = 'TRACK'
            else:
                gx, gy, gz = self.gate_center_odom
                self.target_yaw = math.atan2(gy - self.current_y, gx - self.current_x)
                yaw_error = self.normalize_angle(self.target_yaw - self.current_yaw)
                heave_error = gz - self.current_z
                if abs(yaw_error) <= self.align_threshold_rad and abs(heave_error) <= self.heave_align_threshold_m:
                    self.aligned_tick_count += 1
                else:
                    self.aligned_tick_count = 0
                if self.aligned_tick_count >= self.align_ticks_required:
                    self.cross_start_x, self.cross_start_y = self.current_x, self.current_y
                    self.cross_target_distance = math.hypot(gx - self.current_x, gy - self.current_y) + self.cross_overshoot_m
                    next_state = 'CROSS'
                else:
                    cmd.angular.z = max(-self.max_yaw_rate_radps, min(self.max_yaw_rate_radps, self.final_yaw_kp * yaw_error))
                    cmd.linear.z = max(-self.heave_max_mps, min(self.heave_max_mps, self.heave_kp * heave_error))
                self._dbg_bearing_error = yaw_error

        elif self.state == 'CROSS':
            if self.cross_start_x is None:
                next_state = 'STOP'
            else:
                travelled = math.hypot(self.current_x - self.cross_start_x, self.current_y - self.cross_start_y)
                remaining = self.cross_target_distance - travelled
                self._dbg_distance = max(0.0, remaining)
                if remaining <= 0.0:
                    next_state = 'STOP'
                else:
                    cmd.linear.x = self.cross_speed_mps
                    if self.target_yaw is not None:
                        err = self.normalize_angle(self.target_yaw - self.current_yaw)
                        limit = self.max_yaw_rate_radps / 3.0
                        cmd.angular.z = max(-limit, min(limit, self.cross_yaw_kp * err))
                    if self.gate_center_odom is not None:
                        cmd.linear.z = max(-self.cross_heave_max_mps, min(self.cross_heave_max_mps, self.heave_kp * (self.gate_center_odom[2] - self.current_z)))

        elif self.state == 'STOP':
            self.stop_pause_tick += 1
            if self.stop_pause_tick >= self.stop_pause_ticks and self.target_yaw is not None:
                self.target_yaw = self.normalize_angle(self.target_yaw + math.pi)
                self.return_dist_remaining = self.forward_dist_travelled
                self.last_track_x, self.last_track_y = self.current_x, self.current_y
                self.stop_pause_tick = 0
                self.aligned_tick_count = 0
                next_state = 'RETURN_ALIGN'

        elif self.state == 'RETURN_ALIGN':
            if self.target_yaw is None:
                next_state = 'STOP'
            else:
                err = self.normalize_angle(self.target_yaw - self.current_yaw)
                if abs(err) <= self.align_threshold_rad:
                    self.aligned_tick_count += 1
                    if self.aligned_tick_count >= self.align_ticks_required:
                        self.aligned_tick_count = 0
                        self.last_track_x, self.last_track_y = self.current_x, self.current_y
                        next_state = 'RETURN_CROSS'
                else:
                    self.aligned_tick_count = 0
                    cmd.angular.z = max(-self.max_yaw_rate_radps, min(self.max_yaw_rate_radps, self.final_yaw_kp * err))
                self._dbg_distance = self.return_dist_remaining
                self._dbg_bearing_error = err

        elif self.state == 'RETURN_CROSS':
            if self.last_track_x is not None:
                self.return_dist_remaining -= math.hypot(self.current_x - self.last_track_x, self.current_y - self.last_track_y)
            self.last_track_x, self.last_track_y = self.current_x, self.current_y
            if self.return_dist_remaining <= 0.0:
                next_state = 'DONE'
            else:
                cmd.linear.x = self.cross_speed_mps
                if self.target_yaw is not None:
                    err = self.normalize_angle(self.target_yaw - self.current_yaw)
                    limit = self.max_yaw_rate_radps / 3.0
                    cmd.angular.z = max(-limit, min(limit, self.cross_yaw_kp * err))

        elif self.state == 'DONE':
            cmd = Twist()
            if not self.done_logged:
                self.get_logger().info('ROUND TRIP COMPLETE.')
                self.done_logged = True

        if self.state != next_state:
            self.get_logger().info(f'[STATE] {self.state} -> {next_state}')

        state_msg = String(); state_msg.data = next_state
        self.mission_pub.publish(state_msg)
        self.cmd_pub.publish(cmd)

        nan = float('nan')
        gx, gy, gz = self.gate_center_odom if self.gate_center_odom is not None else (nan, nan, nan)
        debug = Float32MultiArray()
        debug.data = [float(gx), float(gy), float(gz), float(self._dbg_distance), float(math.degrees(self._dbg_bearing_error)), float(self.commit_tick_count), float(self.aligned_tick_count), 1.0 if fresh else 0.0, float(self.last_gate_confidence), float(self._dbg_nav_source)]
        self.debug_pub.publish(debug)
        self.state = next_state


def main(args=None):
    rclpy.init(args=args)
    node = GateNavigatorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
