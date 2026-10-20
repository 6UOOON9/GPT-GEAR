"""Read native UIPC contact gradients on the two gelpads only.

UIPC's IPC normal and friction contact energies use kappa * dt**2. Their
exported vertex gradient is therefore -force * dt**2 (not a force directly).
Sum only vertices belonging to each gelpad, remove dt**2 and rotate world to
robot base. No actor/target pose, contact partner identity or task truth is read.
This is the last solver contact gradient, not a calibrated physical force sensor.
"""
import numpy as np
from perception.calibration import ee_transform


def aggregate_contact_force(indices, gradients, offset, count, dt, world_to_base_rotation):
    indices = np.asarray(indices).reshape(-1)
    gradients = np.asarray(gradients,dtype=np.float64).reshape(-1,3)
    if len(indices) != len(gradients) or not np.isfinite(gradients).all() or not np.isfinite(dt) or dt <= 0:
        raise ValueError('invalid native contact gradient')
    selected = (indices >= offset) & (indices < offset + count)
    force_world = -gradients[selected].sum(axis=0) / dt**2
    force = np.asarray(world_to_base_rotation,dtype=float) @ force_world
    if not np.isfinite(force).all():raise ValueError('nonfinite native contact force')
    return dict(force_N=force.tolist(), magnitude_N=float(np.linalg.norm(force)),
                coordinate_frame='robot_base', unit='N', measurement='net_contact_force_on_gelpad')


class NativeContactForces:
    def __init__(self, env):
        from uipc.geometry import Geometry
        from uipc import builtin
        self.env = env
        self.feature = env.uipc_sim.world.features().find('contact_system')
        if self.feature is None or not hasattr(self.feature,'contact_gradient'):
            raise RuntimeError('native UIPC contact_system feature unavailable')
        self.buffer = Geometry()
        self.dt = float(env.uipc_sim.cfg.dt)
        self.ranges = {}
        for name in ('left_tactile','right_tactile'):
            gelpad = env._tactile_manager.tactiles[name].gelpad
            slots = gelpad.geo_slot_list
            if len(slots) != 1:raise ValueError('expected one native geometry per gelpad')
            geometry = slots[0].geometry()
            offset = geometry.meta().find(builtin.global_vertex_offset)
            if offset is None:raise ValueError('missing native gelpad vertex offset')
            self.ranges[name] = (int(np.asarray(offset.view()).reshape(-1)[0]),int(geometry.vertices().size()))
        self.metadata = dict(source='UIPC ContactSystemFeature.contact_gradient',
            conversion='F_world = -sum(grad_on_gelpad_vertices) / dt^2; F_base = R_base_world @ F_world',
            physics_dt=self.dt, includes='native normal and frictional contact',
            excludes='elastic internal forces, attachment constraints, object/target poses, contact partner identities',
            sample='last assembled native solver contact gradient', units='N', coordinate_frame='robot_base')

    def read(self):
        self.feature.contact_gradient(self.buffer)
        indices = self.buffer.instances().find('i').view()
        gradients = self.buffer.instances().find('grad').view()
        robot = self.env._robot_manager.robot
        quat = robot.data.root_link_quat_w[0].detach().cpu().numpy()
        rotation = ee_transform(np.r_[np.zeros(3),quat])[:3,:3].T
        return {name:aggregate_contact_force(indices,gradients,*span,self.dt,rotation)
                for name,span in self.ranges.items()}
