#!/usr/bin/env python3
"""Read-only live AUV mission monitor."""

import math
import time
from datetime import datetime

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray, String


class MissionMonitorNode(Node):
    def __init__(self):
        super().__init__('mission_monitor_node')
        self.state_topic = self.declare_parameter('state_topic', '/auv/mission_state').value
        self.odom_topic = self.declare_parameter('odom_topic', '/auv/odom').value
        self.gate_detection_topic = self.declare_parameter('gate_detection_topic', '/auv/gate_detection_2d').value
        self.gate_position_topic = self.declare_parameter('gate_position_topic', '/auv/gate_position_3d').value
        self.navigator_debug_topic = self.declare_parameter('navigator_debug_topic', '/auv/navigator_debug').value
        self.cmd_vel_topic = self.declare_parameter('cmd_vel_topic', '/auv/cmd_vel').value
        self.refresh_hz = float(self.declare_parameter('refresh_hz', 1.0).value)
        self.state='UNKNOWN'; self.odom=None; self.det=None; self.gate=None; self.nav=None; self.cmd=None
        self.start=time.time()
        self.create_subscription(String, self.state_topic, lambda m: setattr(self,'state',m.data),10)
        self.create_subscription(Odometry, self.odom_topic, self.odom_cb,10)
        self.create_subscription(Float32MultiArray, self.gate_detection_topic, lambda m: setattr(self,'det',list(m.data)),10)
        self.create_subscription(Float32MultiArray, self.gate_position_topic, lambda m: setattr(self,'gate',list(m.data)),10)
        self.create_subscription(Float32MultiArray, self.navigator_debug_topic, lambda m: setattr(self,'nav',list(m.data)),10)
        self.create_subscription(Twist, self.cmd_vel_topic, lambda m: setattr(self,'cmd',(float(m.linear.x),float(m.angular.z))),10)
        self.create_timer(1.0/self.refresh_hz, self.draw)

    def odom_cb(self,msg):
        p=msg.pose.pose.position; q=msg.pose.pose.orientation
        yaw=math.degrees(math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z)))
        self.odom=(p.x,p.y,p.z,yaw)

    def draw(self):
        now=datetime.now().strftime('%H:%M:%S'); runtime=int(time.time()-self.start)
        lines=['='*64,f'AUV GATE MISSION | {now}', '='*64, f'State: {self.state}']
        if self.odom: lines.append(f'Odom : x={self.odom[0]:+.2f} y={self.odom[1]:+.2f} z={self.odom[2]:+.2f} yaw={self.odom[3]:+.1f}deg')
        else: lines.append('Odom : waiting')
        if self.det and len(self.det)>=6: lines.append(f'YOLO : {"DETECTED" if self.det[0]>0.5 else "NONE"} conf={self.det[5]:.2f}')
        else: lines.append('YOLO : waiting')
        if self.gate and len(self.gate)>=4: lines.append(f'Gate : x={self.gate[0]:.2f} y={self.gate[1]:+.2f} z={self.gate[2]:+.2f} conf={self.gate[3]:.2f}')
        else: lines.append('Gate : waiting')
        if self.nav and len(self.nav)>=5: lines.append(f'Nav  : remaining={self.nav[3]:.2f}m bearing={self.nav[4]:+.1f}deg')
        if self.cmd: lines.append(f'Cmd  : fwd={self.cmd[0]:+.3f} rot={self.cmd[1]:+.3f}')
        lines.append(f'Runtime: {runtime//60:02d}:{runtime%60:02d} | Ctrl+C to stop')
        print('\033[2J\033[H'+'\n'.join(lines), flush=True)


def main(args=None):
    rclpy.init(args=args); node=MissionMonitorNode()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally: node.destroy_node(); rclpy.try_shutdown()


if __name__ == '__main__': main()
