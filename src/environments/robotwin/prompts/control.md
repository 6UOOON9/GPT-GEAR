## RoboTwin native dual-arm control

Both left and right arms must appear in every action, with independent environment-frame
increments and budgets. Poses refer to RoboTwin's native EE, not an object center or
fingertip. Rotation increments are wxyz quaternions applied by left multiplication.
Use gripper="open" or "close"; null keeps the previous command. Measured gripper
opening is a separate observation, not a verified source action in reference data.

Head, left wrist and right wrist RGB views describe the same current scene. Use
the reported calibration and measured EE poses. Task language may designate an
arm or object; follow that designation. True depth and object poses are unavailable.

One native step is one synchronized RoboTwin take_action(ee) call for both arms,
not a physics tick. Initialization does not consume that budget. A planning failure
is motion feedback, not task success. Success comes from the official simulator;
finish only ends control. These episodes do not use expert screening.
