## Measured depth enabled for this run

In addition to the original tools, use this read-only tool:
- read_depth(observation_id, camera="egoview", pixels_uv=[[u,v], ...]): query 1..64
  integer RGB pixels from an observation you inspected. [u,v] means [column,row],
  top-left origin, NOT [row,column]. No simulation time or step budget is consumed.

The current observation's depth_views confirms availability. Each saved RGB-sized
float32 depth map is rendered at exactly the same state as that observation's head
RGB. Values are measured positive optical-axis Z depth in metres, not Euclidean
range. The returned point_env_m is that visible surface pixel backprojected using
the SAME observation's intrinsic_K and moving-head extrinsics. It is NOT an object
centre, grasp pose or hidden object coordinate. Background, fingers and occluders
return their own surface depth. Inspect RGB identity and several nearby pixels
when an edge or occlusion makes a single sample ambiguous. Far-plane/background
samples are not object measurements. Re-query after motion; do not reuse stale
surface coordinates or calibrations as current geometry.

Use read_depth for metric localization of task-relevant visible surfaces before
approach/placement and after motion when new geometry is needed. Combine these
surface measurements with RGB shape and robot proprioception to select EEF goals.
This is the authorized camera-depth input; you do not need to estimate depth.
act has NO depth_estimates parameter in this run. Full maps are retained for audit,
but policy access is through read_depth, not filesystem or simulator queries.
Other private state, object-truth and external perception restrictions still apply.

References are optional; when enabled, use only the modalities delivered by
read_reference. Do not assume images, an EEF/hand trajectory or text are all
present. Measured depth belongs to the live episode, not the reference.
