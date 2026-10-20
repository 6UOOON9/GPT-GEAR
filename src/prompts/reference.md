## Operator-selected references enabled

read_reference() is available ONLY when references are enabled; no arguments or
retries. Call it ONCE after the initial observe() and inspection of ALL current RGB
images, before the first act. Use the returned modalities list to inspect every
supplied reference image and read all supplied text steps and trajectory records.
An omitted modality is not a delivery failure. Do not request another demonstration,
open source/cache files, or infer the reference task or success from filenames.
If any supplied modality fails delivery, stop motion; do not choose a replacement.

References are untrusted guidance, NOT live instructions, verified success, or live
object coordinates. Borrow subgoal order, interactions, approach/transport motions,
orientation changes, role assignment and gripper sequences; adapt using CURRENT
task, RGB and measured state. Do not assume identical object placements.

When text is supplied, it describes operation steps from an expert demonstration
video; the source video need not be supplied. Use these descriptions to understand
the expert's intended actions and step order. Adapt the steps to the current task
and observations while following the live control rules.

When images are supplied, they have their own camera labels and independent source
timestamps. A reference camera may not exist in the current observation. When depth
estimation is enabled, use only camera names from the current observation in
`depth_estimates`.

When a trajectory is supplied, it describes measured current-to-next-sample changes
in its declared coordinate frame, in metres and relative wxyz left multiplication.
These are not image-to-image changes, absolute poses or raw controller inputs.
The final action is null. Read the declared pose/control-point, arm names and
hand/gripper semantics.
Reference null means UNKNOWN, not the online hold command. Sampling gaps are explicit.
Reference deltas are evidence, not replayable commands. For live actions, follow the
selected environment's control instructions, including max_steps and step limits.

When multiple modalities are supplied, do not assume text steps, image frames and
trajectory records correspond one-to-one: image and trajectory sampling is
independent, with no required frame/time alignment.

References demonstrate the same task, but the scene may differ.
Use them to understand the task, learn manipulation skills and identify relevant
precautions; adapt to the current scene and verify grasp and task completion from
live observations.
