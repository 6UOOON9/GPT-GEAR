# Visual reference step annotation

You are annotating the attached RGB reference images, not controlling a robot.
Inspect EVERY attached image from all supplied cameras (head, left_wrist and
right_wrist for RoboDojo). The image index lists camera and source timestamp in attachment order. Each video was sampled
independently at the rate specified below, retaining the first and last frames with duplicates removed.
The camera videos need not be frame-synchronous; gaps can hide important events.

Return ONLY English numbered steps (1. ..., 2. ..., ...), in observed operation
order. Identify objects using visible appearance and relative visual relations.
Describe the approach, interaction, transport or articulation, release/retreat only
where visible. Include observed changes, honest uncertainty and a short live check
for the online robot to perform before proceeding. Left/right denote robot arm
identities, not screen coordinates; if uncertain, say "active arm".
This is reference guidance to adapt to a different live scene, not an executable action sequence.

Do not infer unseen contact, grasp attachment, successful lifting or stable release
from finger closure or hand movement alone. Distinguish object-hand co-motion from
an empty grasp and object motion from hand arrival. If occlusion or sampling prevents
a conclusion, say so. Never invent hidden coordinates, measured depths, numerical
actions, official success results or task requirements not shown by the images.
No numeric motion measurements, file paths, frame ranges, JSON, review checklist or
claims of human review. Image timestamps are context only, not required output.
Use no tools, shell, MCP, external services, source files or other sessions. Do not
start an environment, execute motion or create files; return the final text only.
