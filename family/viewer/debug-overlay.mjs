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

function drawBustSpheres(ctx, entries, project, options) {
  const bustData = options.bustData;
  if (!bustData) return;
  for (const entry of entries) {
    const chData = bustData[entry.key];
    if (!chData) continue;
    const outfit = entry.outfit ?? 'office';
    const regs = chData.outfits?.[outfit] ?? chData.outfits?.swimwear ?? chData.outfits?.office;
    if (!regs || !regs.bust_r || !regs.bust_l) continue;

    let poseDx = 0, poseDy = 0;
    if (!options.staticPose && entry.player?.bone && Array.isArray(chData.chest)) {
      try {
        const chest = entry.player.bone('chest');
        if (chest && chest.active) {
          const setupWx = chData.chest[0] - 400;
          const setupWy = 2284 - chData.chest[1];
          poseDx = chest.x - setupWx;
          poseDy = chest.y - setupWy;
        }
      } catch {}
    }

    const rReg = regs.bust_r;
    const lReg = regs.bust_l;
    const dist = Math.hypot(lReg.cx - rReg.cx, lReg.cy - rReg.cy);
    const overlap = (rReg.r + rReg.band + lReg.r + lReg.band) > (dist - 16);
    const isTarget = options.activeBustChar === entry.key;

    for (const [side, reg, baseColor] of [
      ['bust_r', rReg, '#00e5ff'],
      ['bust_l', lReg, '#ff4da6'],
    ]) {
      const wx = (reg.cx - 400) + poseDx + (entry.offsetX ?? 0);
      const wy = (2284 - reg.cy) + poseDy - (entry.offsetY ?? 0);
      const center = project(wx, wy);
      const edgeR = project(wx + reg.r, wy);
      const edgeBand = project(wx, wy + reg.r + reg.band);
      const pxR = Math.max(2, Math.hypot(edgeR.x - center.x, edgeR.y - center.y));
      const pxBand = Math.max(pxR + 2, Math.hypot(edgeBand.x - center.x, edgeBand.y - center.y));
      const color = overlap ? '#ff5252' : baseColor;

      ctx.save();
      ctx.globalAlpha = isTarget ? 0.95 : 0.65;

      // Outer falloff band circle (r + band)
      ctx.beginPath();
      ctx.setLineDash([5, 4]);
      ctx.strokeStyle = color;
      ctx.lineWidth = isTarget ? 1.6 : 1.1;
      ctx.arc(center.x, center.y, pxBand, 0, Math.PI * 2);
      ctx.stroke();

      // Core 100% weight circle (r)
      ctx.beginPath();
      ctx.setLineDash([]);
      ctx.fillStyle = color + '22';
      ctx.strokeStyle = color;
      ctx.lineWidth = isTarget ? 2.2 : 1.5;
      ctx.arc(center.x, center.y, pxR, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // Center crosshair
      ctx.beginPath();
      ctx.moveTo(center.x - 7, center.y);
      ctx.lineTo(center.x + 7, center.y);
      ctx.moveTo(center.x, center.y - 7);
      ctx.lineTo(center.x, center.y + 7);
      ctx.stroke();

      // Center handle (move cx, cy)
      ctx.beginPath();
      ctx.fillStyle = '#ffffff';
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.arc(center.x, center.y, 4.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // Core radius handle on right edge (resize r)
      ctx.beginPath();
      ctx.fillStyle = color;
      ctx.strokeStyle = '#111318';
      ctx.lineWidth = 1.5;
      ctx.arc(center.x + pxR, center.y, 4.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // Band radius handle on top edge (resize band)
      ctx.beginPath();
      ctx.fillStyle = '#111318';
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.arc(center.x, center.y - pxBand, 4.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // Coordinate readout badge
      const label = `${side === 'bust_r' ? 'R' : 'L'} (${Math.round(reg.cx)},${Math.round(reg.cy)}) r:${Math.round(reg.r)} b:${Math.round(reg.band)}`;
      ctx.font = '600 11px -apple-system, BlinkMacSystemFont, monospace';
      const tw = ctx.measureText(label).width + 8;
      const lx = center.x - tw / 2;
      const ly = center.y + pxBand + 14;
      ctx.fillStyle = 'rgba(12, 14, 18, 0.82)';
      ctx.fillRect(lx, ly - 11, tw, 15);
      ctx.fillStyle = color;
      ctx.fillText(label, lx + 4, ly);

      ctx.restore();
    }
  }
}

export function drawOverlay(canvas, entries, project, options, dpr = 1) {
  const width = canvas.clientWidth, height = canvas.clientHeight;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  const pixelWidth = Math.max(1, Math.round(width*dpr)), pixelHeight = Math.max(1, Math.round(height*dpr));
  if (canvas.width !== pixelWidth) canvas.width = pixelWidth;
  if (canvas.height !== pixelHeight) canvas.height = pixelHeight;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, width, height);
  if (!options.bones && !options.mesh && !options.bustEdit) return;
  if (options.bones || options.mesh) {
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
  if (options.bustEdit) {
    drawBustSpheres(ctx, entries, project, options);
  }
}
