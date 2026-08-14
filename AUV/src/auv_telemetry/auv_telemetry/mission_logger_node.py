#!/usr/bin/env python3
"""Read-only production CSV mission logger."""

import csv
import math
import os
from datetime import datetime

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray, String


class MissionLoggerNode(Node):
    def __init__(self):
        super().__init__('mission_logger_node')
        self.state_topic = self.declare_parameter('state_topic', '/auv/mission_state').value
        self.odom_topic = self.declare_parameter('odom_topic', '/auv/odom').value
        self.gate_2d_topic = self.declare_parameter('gate_2d_topic', '/auv/gate_detection_2d').value
        self.gate_3d_topic = self.declare_parameter('gate_3d_topic', '/auv/gate_position_3d').value
        self.navigator_debug_topic = self.declare_parameter('navigator_debug_topic', '/auv/navigator_debug').value
        self.cmd_vel_topic = self.declare_parameter('cmd_vel_topic', '/auv/cmd_vel').value
        self.log_directory = os.path.expanduser(self.declare_parameter('log_directory', '~/auv_ws/mission_logs').value)
        self.logging_hz = float(self.declare_parameter('logging_hz', 1.0).value)
        self.flush_every_row = bool(self.declare_parameter('flush_every_row', True).value)
        self.log_state_transition_immediately = bool(self.declare_parameter('log_state_transition_immediately', True).value)
        if self.logging_hz <= 0.0:
            raise ValueError('logging_hz must be > 0')

        os.makedirs(self.log_directory, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_filepath = os.path.join(self.log_directory, f'mission_run_{stamp}.csv')
        self.csv_file = open(self.log_filepath, 'w', newline='', encoding='utf-8')
        self.writer = csv.writer(self.csv_file)
        self.writer.writerow([
            'wall_time','sim_time_sec','mission_state','odom_x','odom_y','odom_yaw_deg',
            'odom_vel_x','odom_vel_yaw','dist_from_start','gate_2d_detected','gate_2d_px_x',
            'gate_2d_px_y','gate_2d_w_px','gate_2d_h_px','gate_2d_conf','gate_3d_x','gate_3d_y',
            'gate_3d_z','gate_3d_age_sec','nav_gate_odom_x','nav_gate_odom_y','nav_gate_approach_yaw_deg',
            'nav_distance_m','nav_bearing_err_deg','nav_commit_ticks','nav_align_ticks','nav_yolo_fresh',
            'nav_yolo_age_sec','nav_source','cmd_linear_x','cmd_angular_z'
        ])
        self.start_time = self.get_clock().now()
        self.state = 'UNKNOWN'; self.prev_state = None
        self.odom = [None] * 5; self.start_xy = None
        self.gate2d = None; self.gate3d = None; self.gate3d_time = None; self.nav = None
        self.cmd_x = self.cmd_yaw = None

        self.create_subscription(String, self.state_topic, self.state_cb, 10)
        self.create_subscription(Odometry, self.odom_topic, self.odom_cb, 10)
        self.create_subscription(Float32MultiArray, self.gate_2d_topic, lambda m: setattr(self, 'gate2d', list(m.data)), 10)
        self.create_subscription(Float32MultiArray, self.gate_3d_topic, self.gate3d_cb, 10)
        self.create_subscription(Float32MultiArray, self.navigator_debug_topic, lambda m: setattr(self, 'nav', list(m.data) if len(m.data) >= 10 else self.nav), 10)
        self.create_subscription(Twist, self.cmd_vel_topic, self.cmd_cb, 10)
        self.create_timer(1.0 / self.logging_hz, self.log_tick)

    def state_cb(self, msg):
        changed = msg.data != self.prev_state
        self.state = msg.data; self.prev_state = msg.data
        if changed and self.log_state_transition_immediately:
            self.log_tick()

    def odom_cb(self, msg):
        p = msg.pose.pose.position; q = msg.pose.pose.orientation
        yaw = math.atan2(2.0*(q.w*q.z + q.x*q.y), 1.0 - 2.0*(q.y*q.y + q.z*q.z))
        self.odom = [float(p.x), float(p.y), yaw, float(msg.twist.twist.linear.x), float(msg.twist.twist.angular.z)]
        if self.start_xy is None: self.start_xy = self.odom[:2]

    def gate3d_cb(self, msg):
        if len(msg.data) < 3: return
        vals = [float(v) for v in msg.data[:3]]
        if all(math.isfinite(v) for v in vals):
            self.gate3d = vals; self.gate3d_time = self.get_clock().now()

    def cmd_cb(self, msg):
        self.cmd_x = float(msg.linear.x); self.cmd_yaw = float(msg.angular.z)

    @staticmethod
    def f(v, d=4):
        if v is None: return ''
        try: x = float(v)
        except (TypeError, ValueError): return str(v)
        if math.isnan(x): return 'nan'
        if math.isinf(x): return 'inf' if x > 0 else '-inf'
        return f'{x:.{d}f}'

    def log_tick(self):
        if self.csv_file.closed: return
        now = self.get_clock().now()
        sim_time = (now - self.start_time).nanoseconds / 1e9
        dist = None
        if self.start_xy and self.odom[0] is not None:
            dist = math.hypot(self.odom[0]-self.start_xy[0], self.odom[1]-self.start_xy[1])
        d2 = self.gate2d if self.gate2d and len(self.gate2d) >= 6 else [None]*6
        g3_age = None
        if self.gate3d_time is not None: g3_age = max(0.0, (now-self.gate3d_time).nanoseconds/1e9)
        nd = self.nav if self.nav and len(self.nav) >= 10 else [None]*10
        row = [
            datetime.now().isoformat(), self.f(sim_time,2), self.state,
            self.f(self.odom[0]), self.f(self.odom[1]), self.f(math.degrees(self.odom[2]) if self.odom[2] is not None else None,2),
            self.f(self.odom[3]), self.f(self.odom[4]), self.f(dist),
            *[self.f(v,3 if i == 5 else 1) for i,v in enumerate(d2)],
            *[self.f(v) for v in (self.gate3d or [None,None,None])], self.f(g3_age,2),
            *[self.f(v) for v in nd], self.f(self.cmd_x,3), self.f(self.cmd_yaw,4)
        ]
        self.writer.writerow(row)
        if self.flush_every_row: self.csv_file.flush()

    def destroy_node(self):
        try: self.csv_file.close()
        except Exception: pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args); node = MissionLoggerNode()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally: node.destroy_node(); rclpy.try_shutdown()


if __name__ == '__main__': main()
