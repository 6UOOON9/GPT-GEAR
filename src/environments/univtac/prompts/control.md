## UniVTAC control and enabled sensors

robot0 uses the measured gripper_center. For this benchmark, environment axes ARE
robot_base axes; rotations are wxyz left multiplications in that frame. Every arm
action requires gripper_position_m in [0,0.04]: the symmetric per-finger joint
position in metres, not total jaw gap and not a fraction. There is no binary gripper
field. Use the observed robot0_gripper_position_m to hold the measured opening.
The servo checks pose AND measured finger error (0.00005 m); a blocked closure can
stall. Inspect final_gripper_error_m. A control step contains up to control_decimation
physics ticks and stops early on task success or early-stop; native control and
policy-call budgets are reported separately.

Always inspect head and wrist RGB. The observation profile declares exactly which
additional inputs are enabled: none, tactile images, contact forces, or both.
left_tactile/right_tactile are optical tactile images, not ordinary camera views;
do not project them through RGB camera calibration. contact_forces contains a net
force vector per gelpad in robot_base axes and newtons. This is the last UIPC solver
contact gradient converted by -sum(gradient)/dt^2 and rotated into the base frame,
not a separately calibrated physical force sensor. It includes native normal and
friction contact; it does not identify a contact partner or hidden object class.
Use only enabled readings from the same observation; absent sensors are unknown.
Official reset/pre_move prepares the task. Do not replay expert actions or inspect
private task state. A task early-stop is an official failure, not a runtime error.

Control-cycle totals exclude initialization and are separate from physics ticks.
