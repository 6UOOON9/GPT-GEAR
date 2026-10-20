## RoboCasa GR1 control

Every act requires both left and right arms. Each arm accepts optional hand: six
raw radian joint targets in order pinky, ring, middle, index, thumb flexion, thumb
rotation; each in [-3,3]. Omit hand to retain the previous target. There is no
gripper fraction or binary gripper field. Use measured hand positions and the
reported physical actuator limits; target values do not guarantee achieved angles.
Hand commands dwell for min(10,max_steps), subject to task and episode stops.

The grip-site goals are in environment/world axes. The native controller converts
them to absolute robot-base IK targets. translation_step and rotation_step bound
the advancing reference, not measured speed; tracking may lag. Pose completion is
measured. A held arm retains its reference while the other continues.

The egoview camera moves with measured head_pose; use each observation's current
calibration. Task success is official env._check_success, never hand closure or
motion completion. Measured depth, when enabled, is specified below.

Native env_step totals include the 10 initialization steps.
