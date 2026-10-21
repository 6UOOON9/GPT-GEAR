## LIBERO-GeoMotion control

Every act requires robot0. Optional gripper is "open" or "close"; omission/null
holds the previous target. The measured control point is robot0_grip_site in
environment axes. The adapter converts bounded displacement and rotation to
native OSC_POSE actions. Inspect agentview and robot0_eye_in_hand.
The episode starts at the fixed test state without warmup steps. Every native
env_step counts toward the budget. Official check_success alone decides success.
