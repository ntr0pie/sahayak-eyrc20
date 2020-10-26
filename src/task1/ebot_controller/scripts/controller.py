#!/usr/bin/python2
# -*- coding: utf-8 -*-

"""
authors: 
"""

# imports 
import rospy 
from nav_msgs.msg import Odometry 
from sensor_msgs.msg import LaserScan 
from math import sin, cos, atan2, atan, sqrt
from geometry_msgs.msg import Twist, Pose
from tf.transformations import euler_from_quaternion

# parameters !!!
_goal_tolerance = 0.9
_range_max = 10

# for debugging choose sth like 1Hz 
_rate = 100 

# goal pose for debugging 
_goal_x  = 10
_goal_y  = 10
_goal_th = 0

# for way points
_x_low   =  20  # do not change 
_x_high  =  80
_x_step  =  2
_x_scale =  10

# controller gains 
_Kp     = 0.08
_Ktheta = 0.9

# Kp = 0.08, Ktheta = 0.9, x_high = 80 worked good as of 26/10 5:00 pm
# Kp = 0.06 & Ktheta = 0.3, though sub par, worked as of 25/10 2:27 am


# sensor data containers  
pose = []
regions = {}

# Waypoint Generator 
def Waypoints(t):
	"""
		generates waypoints along a given 
		continuous and differentiable curve t
	"""
	global _x_low, _x_high, _x_step, _x_scale

	# que x coordinates 
	xs = [x/_x_scale for x in range(_x_low, _x_high, _x_step)]

	# derivative of curve t
	t_dash = lambda x: cos(x/2) * sin(x) + 2 * sin(x/2) * cos(x)

	# angle of slope @ f'(x)
	t_theta = lambda x: atan(t_dash(x))

	# mini goal waypoint = [x, y, theta]
	waypoint_buffer = [[x, t(x), t_theta(x)] for x in xs]

	return waypoint_buffer

# Odom callback  
def odom_callback(data):
	global pose
	# convert quaternion to euler
	x  = data.pose.pose.orientation.x;
	y  = data.pose.pose.orientation.y;
	z  = data.pose.pose.orientation.z;
	w  = data.pose.pose.orientation.w;
	pose = [
			data.pose.pose.position.x, 
			data.pose.pose.position.y, 
			euler_from_quaternion([x, y, z, w])[2]
		]
	# print("Pose: {}".format(pose)) # for debugging 
	rospy.Rate(_rate).sleep()

# Laser callback  
def laser_callback(msg):
	global regions
	global _range_max

	_sec = 720//5
	# TODO: select range for optimum perception 
	regions = {
		'bright': min(min(msg.ranges[_sec*0 : _sec*1-1]), _range_max),
		'fright': min(min(msg.ranges[_sec*1 : _sec*2-1]), _range_max),
		'front' : min(min(msg.ranges[_sec*2 : _sec*3-1]), _range_max),
		'fleft' : min(min(msg.ranges[_sec*3 : _sec*4-1]), _range_max),
		'bleft' : min(min(msg.ranges[_sec*4 : _sec*5-1]), _range_max),
	}

# Helper functions 
def _getDeviation(_current_pose, _goal_pose):
	""" get deviation between two poses """

	# distance 
	_del_x = _goal_pose[0] - _current_pose[0]
	_del_y = _goal_pose[1] - _current_pose[1]

	# angle  
	theta = atan2( 				 # arctan(_del_y/_del_x)
		_goal_pose[1]  - _current_pose[1], # del y 
		_goal_pose[0]  - _current_pose[0]) # del x

	# deviation  
	_distance = sqrt(pow(_del_x, 2) + pow(_del_y, 2))
	_del_theta = theta - _current_pose[2]

	return [_distance, _del_theta]

# For testing
def _setTestGoalPose(_x = 2, _y = 2, _theta = 0):
	_goal_pose = Pose()
	_goal_pose.position   .x = _x
	_goal_pose.position   .y = _y
	_goal_pose.orientation.z = _theta
	goal_pose = [
		_goal_pose.position   .x,
		_goal_pose.position   .y,
		_goal_pose.orientation.z,
	]
	return goal_pose

# Control loop 
def control_loop():
	# topics 
	_odom = '/odom'
	_scan = '/ebot/laser/scan'
	_vel = '/cmd_vel'

	rospy.init_node('ebot_controller')
	pub = rospy.Publisher(_vel,  Twist,     queue_size = 10)
	rospy.Subscriber     (_scan, LaserScan, laser_callback)
	rospy.Subscriber     (_odom, Odometry,  odom_callback)
	rate = rospy.Rate(_rate)

	velocity_msg           = Twist()
	velocity_msg.linear .x = 0 
	velocity_msg.angular.z = 0
	pub.publish(velocity_msg)

	# Set test goal (in params above)
	goal_pose = _setTestGoalPose(_goal_x, _goal_y, _goal_th)
	
	# task 1.0: traverse the specified curve 
	trajectory = lambda x: 2 * sin(x) * sin(x/2)
	# task 1.1:  buffer mini goals!
	waypoint_buffer = Waypoints(trajectory)

	# task 2.0: go to goal base 
	# TODO: find the coordinates of final goal & populate this stamp
	# big_goal = Pose() 
	# waypoint_buffer.append(big_goal)

	_num_wp = len(waypoint_buffer) # for debugging 
	rospy.Rate(1).sleep() # wait for first odom value
	while not rospy.is_shutdown():
		while (len(waypoint_buffer)):
			##################### pick first mini goal #######################
			goal_pose = waypoint_buffer.pop(0)
			##################### go to mini goal ############################
			while(
				_getDeviation(pose, goal_pose)[0] > _goal_tolerance):

				print("[INFO] Distance: {} | Angle: {}".format(
						round(_getDeviation(pose, goal_pose)[0], 2), round(_getDeviation(pose, goal_pose)[1]), 2)) # for debugging 

				if(_getDeviation(pose, goal_pose)[0] > 10):
					print("[ERR] Controller has become unstable. Halting...")
					stop_vel = Twist() 
					pub.publish(stop_vel)
					return

				# print("Pose~: {}".format(pose)) # for debugging 
				# proportional controller 
				x = _Kp     * _getDeviation(pose, goal_pose)[0] 
				z = _Ktheta * _getDeviation(pose, goal_pose)[1] 

			#################################################################
			# algorithm for obstacle course goes here 
			# TODO: write algorithm to avoid concave obstacles
			#################################################################

				# log command 
				velocity_msg.linear .x  = x 
				velocity_msg.angular.z  = z 
				# for sanity 
				velocity_msg.linear .y  = 0
				velocity_msg.linear .z  = 0
				velocity_msg.angular.x  = 0
				velocity_msg.angular.y  = 0
				pub.publish(velocity_msg)

				# log iteration 
				# print("Controller message pushed at {}".format(rospy.get_time()))

				# zzz for <_rate>hz  
				rate.sleep()
				print("[INFO] Reached goal {} of {}: {}".format(
					 _num_wp - len(waypoint_buffer), _num_wp, goal_pose))
				
				if(_num_wp == 1):
					print("[INFO] Trajectory executed, planning final goal")

		# stop & break control loop 
		stop_vel = Twist() 
		pub.publish(stop_vel)
		print("[INFO] Reached final goal!")
		break 

if __name__ == '__main__':
	try:
		control_loop()
	except rospy.ROSInterruptException:
		pass