## LIBERO-plus control

Every act requires robot0. Optional gripper uses the strings "open" or "close";
omitted/null holds the previous target. The measured control point is
robot0_grip_site in environment axes. Native OSC_POSE action scaling is handled
by the adapter; supply the bounded environment-frame displacements and rotations
specified by the common action contract.
Inspect both agentview and robot0_eye_in_hand. Native env_step totals include the
10 initialization steps. Only the official check_success result decides success.
