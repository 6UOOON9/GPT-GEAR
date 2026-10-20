## RoboDojo control

Every act requires both left and right arms. Each arm accepts optional gripper:
0 closes and 1 opens (fraction in [0,1]); omitted/null holds the previous target.
Control points are the measured left_ee and right_ee in environment axes.
The native budget counts synchronized take_action steps; use episode_status for
remaining budget and the official task result.
