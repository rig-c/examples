/** Mesh positions come from the same final posed frame the renderer draws. */
export function overlayGeometry(player, boneSpecs, { bones, mesh }) {
  const lines = [], joints = [];
  if (mesh) for (const slot of player.posedFrame().order) {
    if (slot.kind !== 'mesh') continue;
    const seen = new Set();
    for (let i = 0; i < slot.triangles.length; i += 3) {
      const ids = slot.triangles.slice(i, i + 3);
      for (let edge = 0; edge < 3; edge++) {
        const a = ids[edge], b = ids[(edge + 1) % 3], key = a < b ? `${a}:${b}` : `${b}:${a}`;
        if (seen.has(key)) continue;
        seen.add(key);
        lines.push({ kind: 'mesh', slot: slot.slot, points: [slot.vertices[2*a], slot.vertices[2*a+1], slot.vertices[2*b], slot.vertices[2*b+1]] });
      }
    }
  }
  if (bones) for (const spec of boneSpecs) {
    const bone = player.bone(spec.name);
    if (!bone.active) continue;
    joints.push([bone.x, bone.y]);
    const length = spec.length ?? 0;
    if (length > 0) lines.push({ kind: 'bone', points: [bone.x, bone.y, bone.x + bone.a * length, bone.y + bone.c * length] });
    else if (spec.parent) {
      const parent = player.bone(spec.parent);
      if (parent.active) lines.push({ kind: 'bone', points: [parent.x, parent.y, bone.x, bone.y] });
    }
  }
  return { lines, joints };
}
export function drawOverlay(canvas, entries, project, options, dpr = 1) {
  const width = canvas.clientWidth, height = canvas.clientHeight;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  const pixelWidth = Math.max(1, Math.round(width*dpr)), pixelHeight = Math.max(1, Math.round(height*dpr));
  if (canvas.width !== pixelWidth) canvas.width = pixelWidth;
  if (canvas.height !== pixelHeight) canvas.height = pixelHeight;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, width, height);
  if (!options.bones && !options.mesh) return;
  for (const entry of entries) {
    const { lines, joints } = overlayGeometry(entry.player, entry.boneSpecs, options);
    const point = (x,y) => project(x + entry.offsetX, y - entry.offsetY);
    for (const kind of ['mesh', 'bone']) {
      ctx.globalAlpha = kind === 'mesh' ? options.meshOpacity : 1;
      ctx.strokeStyle = kind === 'mesh' ? '#60ecff' : '#ffe07a'; ctx.lineWidth = kind === 'mesh' ? .8 : 1.3;
      ctx.beginPath();
      for (const line of lines) if (line.kind === kind) {
        const a = point(line.points[0], line.points[1]), b = point(line.points[2], line.points[3]);
        ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y);
      }
      ctx.stroke();
    }
    ctx.globalAlpha = 1; ctx.fillStyle = '#ffe07a';
    for (const [x,y] of joints) { const p = point(x,y); ctx.beginPath(); ctx.arc(p.x,p.y,2,0,Math.PI*2); ctx.fill(); }
  }
}
