#!/usr/bin/env python3
"""Production AUV trail/object mapper.

Repeated gate detections are clustered into one marker. A gate is rendered as
a thin cuboid around its estimated centre; no false pole/orientation geometry
is invented from centre-only perception.
"""

import csv
import math
import os
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import rclpy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry, Path
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray
from visualization_msgs.msg import Marker, MarkerArray

try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


class TrailMapperNode(Node):
    def __init__(self):
        super().__init__('trail_mapper_node')
        self.odom_topic = self.declare_parameter('odom_topic', '/auv/odom').value
        self.gate_topic = self.declare_parameter('gate_topic', '/auv/gate_position_3d').value
        self.bin_topic = self.declare_parameter('bin_topic', '/auv/bin_position_3d').value
        self.trail_topic = self.declare_parameter('trail_topic', '/auv/trail_map').value
        self.marker_topic = self.declare_parameter('marker_topic', '/auv/object_markers').value
        self.odom_frame = self.declare_parameter('odom_frame', 'map').value
        self.min_trail_distance_m = float(self.declare_parameter('min_trail_distance_m', 0.10).value)
        self.publish_hz = float(self.declare_parameter('publish_hz', 1.0).value)
        self.confidence_threshold = float(self.declare_parameter('confidence_threshold', 0.30).value)
        self.cluster_distance_m = float(self.declare_parameter('cluster_distance_m', 0.75).value)
        self.cluster_update_alpha = float(self.declare_parameter('cluster_update_alpha', 0.25).value)
        self.max_marker_count = int(self.declare_parameter('max_marker_count', 20).value)
        self.camera_offset_fwd_m = float(self.declare_parameter('camera_offset_fwd_m', 0.30).value)
        self.camera_offset_left_m = float(self.declare_parameter('camera_offset_left_m', 0.06).value)
        self.camera_offset_up_m = float(self.declare_parameter('camera_offset_up_m', 0.00).value)
        self.gate_width_m = float(self.declare_parameter('gate_width_m', 1.524).value)
        self.gate_height_m = float(self.declare_parameter('gate_height_m', 1.524).value)
        self.gate_thickness_m = float(self.declare_parameter('gate_thickness_m', 0.05).value)
        self.gate_visual_yaw_rad = float(self.declare_parameter('gate_visual_yaw_rad', 0.0).value)
        self.gate_marker_alpha = float(self.declare_parameter('gate_marker_alpha', 0.55).value)
        self.bin_marker_size_m = float(self.declare_parameter('bin_marker_size_m', 0.30).value)
        self.log_directory = os.path.expanduser(self.declare_parameter('log_directory', '~/auv_ws/mission_logs').value)
        self.create_3d_html = bool(self.declare_parameter('create_3d_html', True).value)
        self.map_dpi = int(self.declare_parameter('map_dpi', 200).value)
        self.log_every_trail_points = int(self.declare_parameter('log_every_trail_points', 20).value)

        os.makedirs(self.log_directory, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.csv_path = os.path.join(self.log_directory, f'trail_{stamp}.csv')
        self.markers_path = os.path.join(self.log_directory, f'markers_{stamp}.csv')
        self.map_path = os.path.join(self.log_directory, f'map_{stamp}.png')
        self.html_path = os.path.join(self.log_directory, f'map_3d_{stamp}.html')
        self.csv_file = open(self.csv_path, 'w', newline='', encoding='utf-8')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(['index', 'x_m', 'y_m', 'z_m', 'dist_from_prev_m', 'total_dist_m'])
        self.marker_file = open(self.markers_path, 'w', newline='', encoding='utf-8')
        self.marker_writer = csv.writer(self.marker_file)
        self.marker_writer.writerow(['class', 'x_m', 'y_m', 'z_m', 'hits', 'confidence'])

        self.trail = []
        self.gates = []
        self.bins = []
        self.current = None
        self.total_dist = 0.0
        self.last_trail = None

        self.create_subscription(Odometry, self.odom_topic, self.odom_callback, 10)
        self.create_subscription(Float32MultiArray, self.gate_topic, self.gate_callback, 10)
        self.create_subscription(Float32MultiArray, self.bin_topic, self.bin_callback, 10)
        self.path_pub = self.create_publisher(Path, self.trail_topic, 10)
        self.marker_pub = self.create_publisher(MarkerArray, self.marker_topic, 10)
        self.create_timer(1.0 / self.publish_hz, self.publish)

    @staticmethod
    def _yaw_from_q(q):
        return math.atan2(2.0*(q.w*q.z + q.x*q.y), 1.0 - 2.0*(q.y*q.y + q.z*q.z))

    def _sensor_to_odom(self, x, y, z):
        if self.current is None:
            return None
        px, py, pz, yaw = self.current
        xb = x - self.camera_offset_fwd_m
        yb = y - self.camera_offset_left_m
        zb = z - self.camera_offset_up_m
        c, s = math.cos(yaw), math.sin(yaw)
        return (px + xb*c - yb*s, py + xb*s + yb*c, pz + zb)

    def odom_callback(self, msg):
        p = msg.pose.pose.position
        self.current = (float(p.x), float(p.y), float(p.z), self._yaw_from_q(msg.pose.pose.orientation))
        if self.last_trail is None or math.dist(self.current[:3], self.last_trail) >= self.min_trail_distance_m:
            if self.last_trail is not None:
                d = math.dist(self.current[:3], self.last_trail)
                self.total_dist += d
            self.last_trail = self.current[:3]
            self.trail.append(self.current[:3])
            i = len(self.trail)
            self.csv_writer.writerow([i, *self.current[:3], 0.0 if i == 1 else d, self.total_dist])
            if i % max(1, self.log_every_trail_points) == 0:
                self.csv_file.flush()

    def _add_detection(self, collection, point, confidence):
        if point is None or confidence < self.confidence_threshold:
            return
        nearest = None
        nearest_d = float('inf')
        for marker in collection:
            d = math.dist(point, marker['p'])
            if d < nearest_d:
                nearest, nearest_d = marker, d
        if nearest is not None and nearest_d <= self.cluster_distance_m:
            a = self.cluster_update_alpha
            nearest['p'] = tuple((1.0-a)*nearest['p'][i] + a*point[i] for i in range(3))
            nearest['confidence'] = max(nearest['confidence'], confidence)
            nearest['hits'] += 1
        elif len(collection) < self.max_marker_count:
            collection.append({'p': point, 'confidence': confidence, 'hits': 1})

    def gate_callback(self, msg):
        if len(msg.data) < 4 or self.current is None:
            return
        try:
            x, y, z, c = [float(v) for v in msg.data[:4]]
            point = self._sensor_to_odom(x, y, z)
            self._add_detection(self.gates, point, c)
        except (TypeError, ValueError):
            return

    def bin_callback(self, msg):
        if len(msg.data) < 4 or self.current is None:
            return
        try:
            x, y, z, c = [float(v) for v in msg.data[:4]]
            self._add_detection(self.bins, self._sensor_to_odom(x, y, z), c)
        except (TypeError, ValueError):
            return

    def publish(self):
        path = Path()
        path.header.frame_id = self.odom_frame
        path.header.stamp = self.get_clock().now().to_msg()
        for x, y, z in self.trail:
            pose = PoseStamped()
            pose.header = path.header
            pose.pose.position.x, pose.pose.position.y, pose.pose.position.z = x, y, z
            pose.pose.orientation.w = 1.0
            path.poses.append(pose)
        self.path_pub.publish(path)

        markers = MarkerArray()
        stamp = self.get_clock().now().to_msg()
        for i, m in enumerate(self.gates):
            markers.markers.append(self._gate_marker(i, m['p'], stamp))
        for i, m in enumerate(self.bins):
            markers.markers.append(self._bin_marker(i, m['p'], stamp))
        if markers.markers:
            self.marker_pub.publish(markers)

    def _gate_marker(self, i, p, stamp):
        m = Marker(); m.header.frame_id = self.odom_frame; m.header.stamp = stamp
        m.ns = 'gate_markers'; m.id = i; m.type = Marker.CUBE; m.action = Marker.ADD
        m.pose.position.x, m.pose.position.y, m.pose.position.z = p
        h = self.gate_visual_yaw_rad / 2.0
        m.pose.orientation.z, m.pose.orientation.w = math.sin(h), math.cos(h)
        m.scale.x, m.scale.y, m.scale.z = self.gate_width_m, self.gate_thickness_m, self.gate_height_m
        m.color.r, m.color.g, m.color.b, m.color.a = 1.0, 0.0, 0.0, self.gate_marker_alpha
        return m

    def _bin_marker(self, i, p, stamp):
        m = Marker(); m.header.frame_id = self.odom_frame; m.header.stamp = stamp
        m.ns = 'bin_markers'; m.id = i; m.type = Marker.SPHERE; m.action = Marker.ADD
        m.pose.position.x, m.pose.position.y, m.pose.position.z = p; m.pose.orientation.w = 1.0
        m.scale.x = m.scale.y = m.scale.z = self.bin_marker_size_m
        m.color.r, m.color.g, m.color.b, m.color.a = 0.0, 0.3, 1.0, 1.0
        return m

    def destroy_node(self):
        try:
            self._export_maps()
        except Exception as exc:
            self.get_logger().error(f'Map export failed: {exc}')
        for f in (self.csv_file, self.marker_file):
            try:
                f.close()
            except Exception:
                pass
        super().destroy_node()

    def _export_maps(self):
        fig, ax = plt.subplots(figsize=(10, 8))
        if self.trail:
            xs, ys = zip(*[(p[0], p[1]) for p in self.trail]); ax.plot(xs, ys, '-', label='AUV trail')
            ax.plot(xs[0], ys[0], 'o', label='Start'); ax.plot(xs[-1], ys[-1], 's', label='End')
        if self.gates:
            ax.scatter([m['p'][0] for m in self.gates], [m['p'][1] for m in self.gates], marker='s', s=180, facecolors='none', linewidths=2.5, label='Gate')
        if self.bins:
            ax.scatter([m['p'][0] for m in self.bins], [m['p'][1] for m in self.bins], marker='o', s=150, facecolors='none', linewidths=2.5, label='Bin')
        ax.set_xlabel('X (m)'); ax.set_ylabel('Y (m)'); ax.set_title('AUV Mission Map — Trail + Detected Objects'); ax.grid(True, linestyle='--', alpha=0.4); ax.set_aspect('equal', adjustable='datalim')
        if self.trail or self.gates or self.bins: ax.legend()
        fig.savefig(self.map_path, dpi=self.map_dpi, bbox_inches='tight'); plt.close(fig)

        if self.create_3d_html and PLOTLY_AVAILABLE:
            fig = go.Figure()
            if self.trail:
                fig.add_trace(go.Scatter3d(x=[p[0] for p in self.trail], y=[p[1] for p in self.trail], z=[p[2] for p in self.trail], mode='lines', name='AUV trail'))
            if self.gates:
                fig.add_trace(go.Scatter3d(x=[m['p'][0] for m in self.gates], y=[m['p'][1] for m in self.gates], z=[m['p'][2] for m in self.gates], mode='markers', marker=dict(size=8), name='Gate'))
            if self.bins:
                fig.add_trace(go.Scatter3d(x=[m['p'][0] for m in self.bins], y=[m['p'][1] for m in self.bins], z=[m['p'][2] for m in self.bins], mode='markers', marker=dict(size=8), name='Bin'))
            fig.update_layout(title='AUV Mission Map — Interactive 3D', scene=dict(xaxis_title='X (m)', yaxis_title='Y (m)', zaxis_title='Z (m)', aspectmode='data'))
            fig.write_html(self.html_path)


def main(args=None):
    rclpy.init(args=args)
    node = TrailMapperNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
