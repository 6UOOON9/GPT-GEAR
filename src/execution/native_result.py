"""Result packaging for the additional simulator adapters."""
from pathlib import Path


def result(native, official):
    from execution.artifacts import write_json
    if official['check_success'] != native.success:
        raise RuntimeError('official success changed without stepping')
    video = native.video.finish() if native.video is not None else None
    if not video or not video['complete']:
        raise RuntimeError('episode video incomplete')
    path = Path(native.args.output) / 'official_result.json'
    write_json(path, official)
    value = dict(complete=True, valid_for_success_rate=not native.uncertain,
        task_success=native.success, native_steps=native.action_count,
        initialization_steps=native.initialization_steps,
        decision_steps=native.action_count - (native.initialization_steps if native.benchmark == 'robocasa-gr1' else 0),
        official_result=official, official_result_path=str(path), video=video)
    if native.benchmark == 'univtac':
        value.update(physics_steps=native.physics_steps, policy_actions=native.policy_actions,
                     initialization_step_unit='physics_step', tactile_mode=native.tactile_mode)
        if native.tactile_video is not None:
            value['tactile_video'] = native.tactile_video.finish()
            if not value['tactile_video']['complete']:
                raise RuntimeError('tactile video incomplete')
    return value
