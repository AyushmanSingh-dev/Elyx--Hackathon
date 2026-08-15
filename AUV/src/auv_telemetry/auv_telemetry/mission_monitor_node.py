#!/usr/bin/env python3
"""Read-only live AUV mission monitor using typed perception messages."""

import math
import time
from datetime import datetime

import rclpy
from auv_msgs.msg import BinPosition3D, GateDetection2D, GatePosition3D
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray, String


class MissionMonitorNode(Node):
    def __init__(self):
        super().__init__('mission_monitor_node')
        self.state_topic=self.declare_parameter('state_topic','/auv/mission_state').value
        self.odom_topic=self.declare_parameter('odom_topic','/auv/odom').value
        self.gate_detection_topic=self.declare_parameter('gate_detection_topic','/auv/gate_detection_2d').value
        self.gate_position_topic=self.declare_parameter('gate_position_topic','/auv/gate_position_3d').value
        self.bin_position_topic=self.declare_parameter('bin_position_topic','/auv/bin_position_3d').value
        self.navigator_debug_topic=self.declare_parameter('navigator_debug_topic','/auv/navigator_debug').value
        self.cmd_vel_topic=self.declare_parameter('cmd_vel_topic','/auv/cmd_vel').value
        self.refresh_hz=float(self.declare_parameter('refresh_hz',1.0).value)
        self.state='UNKNOWN'; self.odom=None; self.det=None; self.gate=None; self.bin=None; self.nav=None; self.cmd=None; self.start=time.time()
        self.create_subscription(String,self.state_topic,lambda m:setattr(self,'state',m.data),10)
        self.create_subscription(Odometry,self.odom_topic,self.odom_cb,10)
        self.create_subscription(GateDetection2D,self.gate_detection_topic,lambda m:setattr(self,'det',m),10)
        self.create_subscription(GatePosition3D,self.gate_position_topic,lambda m:setattr(self,'gate',m),10)
        self.create_subscription(BinPosition3D,self.bin_position_topic,lambda m:setattr(self,'bin',m),10)
        self.create_subscription(Float32MultiArray,self.navigator_debug_topic,lambda m:setattr(self,'nav',list(m.data)),10)
        self.create_subscription(Twist,self.cmd_vel_topic,lambda m:setattr(self,'cmd',(float(m.linear.x),float(m.angular.z))),10)
        self.create_timer(1.0/self.refresh_hz,self.draw)

    def odom_cb(self,msg):
        p=msg.pose.pose.position; q=msg.pose.pose.orientation
        yaw=math.degrees(math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z)))
        self.odom=(p.x,p.y,p.z,yaw)

    def draw(self):
        now=datetime.now().strftime('%H:%M:%S'); runtime=int(time.time()-self.start)
        lines=['='*64,f'AUV GATE MISSION | {now}','='*64,f'State: {self.state}']
        lines.append(f'Odom : x={self.odom[0]:+.2f} y={self.odom[1]:+.2f} z={self.odom[2]:+.2f} yaw={self.odom[3]:+.1f}deg' if self.odom else 'Odom : waiting')
        lines.append(f'YOLO : {"DETECTED" if self.det and self.det.detected else "NONE"} conf={self.det.confidence:.2f}' if self.det else 'YOLO : waiting')
        lines.append(f'Gate : x={self.gate.x_fwd_m:.2f} y={self.gate.y_left_m:+.2f} z={self.gate.z_up_m:+.2f} conf={self.gate.confidence:.2f}' if self.gate and self.gate.detected else 'Gate : waiting')
        lines.append(f'Bin  : x={self.bin.x_fwd_m:.2f} y={self.bin.y_left_m:+.2f} z={self.bin.z_up_m:+.2f} conf={self.bin.confidence:.2f}' if self.bin and self.bin.detected else 'Bin  : waiting')
        if self.nav and len(self.nav)>=10: lines.append(f'Nav  : remaining={self.nav[3]:.2f}m bearing={self.nav[4]:+.1f}deg')
        if self.cmd: lines.append(f'Cmd  : fwd={self.cmd[0]:+.3f} rot={self.cmd[1]:+.3f}')
        lines.append(f'Runtime: {runtime//60:02d}:{runtime%60:02d} | Ctrl+C to stop')
        print('\033[2J\033[H'+'\n'.join(lines),flush=True)


def main(args=None):
    rclpy.init(args=args); node=MissionMonitorNode()
    try:rclpy.spin(node)
    except KeyboardInterrupt:pass
    finally:node.destroy_node(); rclpy.try_shutdown()


if __name__=='__main__':main()
