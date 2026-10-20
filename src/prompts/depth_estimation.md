## Explicit depth estimation

Every act must include top-level depth_estimates (beside observation_id, action and
reason), a nonempty list of objects with exactly these fields:
- object: a descriptive visual object label;
- camera: a camera name in the CURRENT observation images/view_specs;
- pixel_uv: the estimated visible object centre [u,v] = [column,row], in pixels
  from the top-left of that camera's RGB image;
- depth_m: your estimated positive optical-axis Z depth in metres, NOT Euclidean range.

Cover the current interaction object; during placement include the destination too.
Estimate only from the latest RGB, its calibration and current proprioceptive state.
These are estimates, not measured depth or privileged coordinates. Do not infer live
depth from reference trajectories or old images, and do not request real depth,
backprojection or ground-truth error tools. Keep action reason brief as before.
The host validates observation identity, fields, finite numbers, image bounds and
positive depth before motion; this validates syntax, NOT accuracy or object coverage.
If the object cannot be estimated from current evidence, do not fabricate precision
or issue an unsupported action; end safely subject to the existing safety rules.

The declaration is for this ONE synchronized decision. All configured arm actions remain mandatory;
object coverage follows the actual interaction, not a quota of one object per arm.
