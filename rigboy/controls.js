/** Controls for the original side-profile sample. Call after player.play(). */
export function rigboyControls(player) {
  const previous = player.adjust;
  let degrees = 0, travel = false, originX = 0;
  const velocities = { walk: 48 / (.6 * 1.25), run: 64 / (.4 * (5/6)) };
  player.adjust = (bones, context) => {
    previous?.(bones, context);
    bones.bone('aim_control').rotation = degrees;
    if (travel && velocities[context.animation])
      bones.bone('root').x += originX + velocities[context.animation] * (context.trackTime ?? 0);
  };
  const setAimDegrees = value => {
    if (!Number.isFinite(value)) throw new Error('Aim angle must be finite');
    degrees = Math.max(-8, Math.min(8, value));
    player.setPhysicsParameters('arm_settle', { mix: 0 });
    return degrees;
  };
  return {
    setAimDegrees,
    /** World point, Y up. The narrow admitted aim arc is around the painted upward toy. */
    aimAt([x, y]) {
      const shoulder = player.bone('near_arm'), chest = player.bone('chest');
      const a = chest.rotationX * Math.PI / 180;
      const dx = x - shoulder.x, dy = y - shoulder.y;
      const tx = Math.cos(a) * dx + Math.sin(a) * dy;
      const ty = -Math.sin(a) * dx + Math.cos(a) * dy;
      // The admitted drawing places the toy pivot199px right of its shoulder.
      // Solve the rotated toy ray against the point, rather than aim the shoulder axis at it.
      const radius = Math.hypot(tx, ty);
      if (radius < 199) throw new Error('Target is inside the admitted aim arc');
      const requested = (Math.atan2(ty, tx) - Math.acos(199 / radius)) * 180 / Math.PI;
      const applied = setAimDegrees(requested);
      return { requested, applied, clamped: applied !== requested };
    },
    setTravel(enabled, x = 0) { travel = enabled; originX = x; },
    recoilPhysics() { player.clearPhysicsParameters('arm_settle'); },
    dispose() { player.adjust = previous; }
  };
}
