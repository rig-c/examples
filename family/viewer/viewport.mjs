/** One world-space camera; comparison and rig receive the same pixels per world unit. */
export function fitCamera(box, zoom = 1, focusTop = false) {
  return { zoom, x: box.x + box.width / 2, y: box.y + box.height * (focusTop ? .75 : .5) };
}
export function cameraScale(box, panels, zoom) {
  return .88 * Math.min(...panels.map(panel => Math.min(panel.width / box.width, panel.height / box.height))) * zoom;
}
export function worldToPanel(x, y, camera, scale, panel) {
  return { x: panel.width / 2 + (x - camera.x) * scale, y: panel.height / 2 - (y - camera.y) * scale };
}
export function zoomAt(camera, oldScale, factor, point, panel) {
  const zoom = Math.max(.05, Math.min(100, camera.zoom * factor));
  const ratio = zoom / camera.zoom;
  const dx = point.x - panel.width / 2, dy = point.y - panel.height / 2;
  return { zoom, x: camera.x + dx / oldScale * (1 - 1 / ratio), y: camera.y - dy / oldScale * (1 - 1 / ratio) };
}
/** Image registration measured from the source crop layout, independent of its encoded resolution. */
export function referenceFrame(character, box) {
  if (character === 'all5_wide') return { x: -496, y: 0, width: 4096, height: 2284 };
  if (character === 'all5' || character === 'composed') return { x: -400, y: 0, width: 2716, height: 2284 };
  return { ...box };
}
