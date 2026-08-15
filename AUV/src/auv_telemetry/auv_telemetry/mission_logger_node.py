#!/usr/bin/env python3
"""CSV mission logger using the typed AUV perception interfaces."""

import csv
import math
import os
from datetime import datetime

import rclpy
from auv_msgs.msg import BinDetection2D, BinPosition3D, GateDetection2D, GatePosition3D
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray, String


class MissionLoggerNode(Node):
    def __init__(self):
        super().__init__('mission_logger_node')
        self.state_topic = self.declare_parameter('state_topic','/auv/mission_state').value
        self.odom_topic = self.declare_parameter('odom_topic','/auv/odom').value
        self.gate_2d_topic = self.declare_parameter('gate_2d_topic','/auv/gate_detection_2d').value
        self.gate_3d_topic = self.declare_parameter('gate_3d_topic','/auv/gate_position_3d').value
        self.bin_2d_topic = self.declare_parameter('bin_2d_topic','/auv/bin_detection_2d').value
        self.bin_3d_topic = self.declare_parameter('bin_3d_topic','/auv/bin_position_3d').value
        self.navigator_debug_topic = self.declare_parameter('navigator_debug_topic','/auv/navigator_debug').value
        self.cmd_vel_topic = self.declare_parameter('cmd_vel_topic','/auv/cmd_vel').value
        self.log_directory = os.path.expanduser(self.declare_parameter('log_directory','~/auv_ws/mission_logs').value)
        self.logging_hz = float(self.declare_parameter('logging_hz',1.0).value)
        self.flush_every_row = bool(self.declare_parameter('flush_every_row',True).value)
        os.makedirs(self.log_directory,exist_ok=True)
        stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_filepath=os.path.join(self.log_directory,f'mission_run_{stamp}.csv')
        self.csv_file=open(self.log_filepath,'w',newline='',encoding='utf-8')
        self.writer=csv.writer(self.csv_file)
        self.writer.writerow(['wall_time','sim_time_sec','mission_state','odom_x','odom_y','odom_z','odom_yaw_deg','odom_vel_x','odom_vel_yaw','dist_from_start','gate_2d_detected','gate_2d_px_x','gate_2d_px_y','gate_2d_w_px','gate_2d_h_px','gate_2d_conf','gate_3d_x','gate_3d_y','gate_3d_z','gate_3d_conf','bin_2d_detected','bin_2d_px_x','bin_2d_px_y','bin_2d_w_px','bin_2d_h_px','bin_2d_conf','bin_3d_x','bin_3d_y','bin_3d_z','bin_3d_conf','nav_gate_odom_x','nav_gate_odom_y','nav_gate_odom_z','nav_distance_m','nav_bearing_err_deg','nav_commit_ticks','nav_align_ticks','nav_yolo_fresh','nav_gate_conf','nav_source','cmd_linear_x','cmd_angular_z'])
        self.start_time=self.get_clock().now(); self.state='UNKNOWN'; self.prev_state=None
        self.odom=None; self.start_xyz=None; self.gate2d=None; self.gate3d=None; self.bin2d=None; self.bin3d=None; self.nav=None; self.cmd=None
        self.create_subscription(String,self.state_topic,self.state_cb,10)
        self.create_subscription(Odometry,self.odom_topic,self.odom_cb,10)
        self.create_subscription(GateDetection2D,self.gate_2d_topic,lambda m:setattr(self,'gate2d',m),10)
        self.create_subscription(GatePosition3D,self.gate_3d_topic,lambda m:setattr(self,'gate3d',m),10)
        self.create_subscription(BinDetection2D,self.bin_2d_topic,lambda m:setattr(self,'bin2d',m),10)
        self.create_subscription(BinPosition3D,self.bin_3d_topic,lambda m:setattr(self,'bin3d',m),10)
        self.create_subscription(Float32MultiArray,self.navigator_debug_topic,lambda m:setattr(self,'nav',list(m.data)),10)
        self.create_subscription(Twist,self.cmd_vel_topic,lambda m:setattr(self,'cmd',(float(m.linear.x),float(m.angular.z))),10)
        self.create_timer(1.0/self.logging_hz,self.log_tick)

    def state_cb(self,msg): self.state=msg.data; self.prev_state=msg.data

    def odom_cb(self,msg):
        p=msg.pose.pose.position; q=msg.pose.pose.orientation
        yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))
        self.odom=(float(p.x),float(p.y),float(p.z),yaw,float(msg.twist.twist.linear.x),float(msg.twist.twist.angular.z))
        if self.start_xyz is None: self.start_xyz=self.odom[:3]

    @staticmethod
    def f(v,d=4):
        if v is None:return ''
        try:x=float(v)
        except (TypeError,ValueError):return str(v)
        if math.isnan(x):return 'nan'
        if math.isinf(x):return 'inf' if x>0 else '-inf'
        return f'{x:.{d}f}'

    def log_tick(self):
        if self.csv_file.closed:return
        now=self.get_clock().now(); sim_time=(now-self.start_time).nanoseconds/1e9
        o=self.odom or [None]*6; dist=math.dist(o[:3],self.start_xyz) if self.start_xyz and self.odom else None
        g2=self.gate2d; g3=self.gate3d; b2=self.bin2d; b3=self.bin3d; n=self.nav or [None]*10; c=self.cmd or [None,None]
        row=[datetime.now().isoformat(),self.f(sim_time,2),self.state,self.f(o[0]),self.f(o[1]),self.f(o[2]),self.f(math.degrees(o[3]) if o[3] is not None else None,2),self.f(o[4]),self.f(o[5]),self.f(dist)]
        row += [int(bool(g2 and g2.detected)),self.f(g2.center_x_px if g2 else None,1),self.f(g2.center_y_px if g2 else None,1),self.f(g2.width_px if g2 else None,1),self.f(g2.height_px if g2 else None,1),self.f(g2.confidence if g2 else None,3)]
        row += [int(bool(g3 and g3.detected)),self.f(g3.x_fwd_m if g3 else None),self.f(g3.y_left_m if g3 else None),self.f(g3.z_up_m if g3 else None),self.f(g3.confidence if g3 else None,3)]
        row += [int(bool(b2 and b2.detected)),self.f(b2.center_x_px if b2 else None,1),self.f(b2.center_y_px if b2 else None,1),self.f(b2.width_px if b2 else None,1),self.f(b2.height_px if b2 else None,1),self.f(b2.confidence if b2 else None,3)]
        row += [int(bool(b3 and b3.detected)),self.f(b3.x_fwd_m if b3 else None),self.f(b3.y_left_m if b3 else None),self.f(b3.z_up_m if b3 else None),self.f(b3.confidence if b3 else None,3)]
        row += [self.f(v) for v in n] + [self.f(c[0],3),self.f(c[1],4)]
        self.writer.writerow(row)
        if self.flush_every_row:self.csv_file.flush()

    def destroy_node(self):
        try:self.csv_file.close()
        except Exception:pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args); node=MissionLoggerNode()
    try:rclpy.spin(node)
    except KeyboardInterrupt:pass
    finally:node.destroy_node(); rclpy.try_shutdown()


if __name__=='__main__':main()
