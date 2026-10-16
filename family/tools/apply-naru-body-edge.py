#!/usr/bin/env python3
"""Restore reviewed Naru outer clothing alpha from the native source, before normal rigc gates.
Requires Python Pillow/NumPy/SciPy and a directory with the pinned public Bun packages.
Never modifies the source or emits a Spine build. Policy hashes bind this to one accepted baseline.
"""
import argparse, copy, hashlib, json, math, shutil, subprocess
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt, gaussian_filter, map_coordinates


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pixel_sha(array):
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def require(condition, message):
    if not condition:
        raise RuntimeError('NARU_BODY_EDGE_' + message)


def image(path):
    return np.array(Image.open(path).convert('RGBA'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ['source-rig-dir', 'source-parts-dir', 'painting-rgba', 'painting', 'group-rgba', 'policy', 'runtime-dir', 'out-rig-dir', 'out-parts-dir']:
        parser.add_argument('--' + flag, required=True, type=Path)
    args = parser.parse_args()
    rigdir, partsdir, out, outparts, runtime = [p.resolve() for p in [args.source_rig_dir, args.source_parts_dir, args.out_rig_dir, args.out_parts_dir, args.runtime_dir]]
    policy = read(args.policy)
    require(policy['spec'] == 'naru-body-edge-restoration/1', 'POLICY_SPEC')
    for target in [out, outparts]:
        require(not target.exists(), 'OUTPUT_MUST_BE_FRESH ' + str(target))
        require(not any(target == source or source in target.parents for source in [rigdir, partsdir]), 'OUTPUT_INSIDE_SOURCE')
    require(out not in outparts.parents and outparts not in out.parents and out != outparts, 'OUTPUTS_MUST_BE_SEPARATE')
    for home, expected in [(rigdir, policy['sourceRigFiles']), (partsdir, policy['sourcePartsFiles'])]:
        for name, wanted in expected.items():
            require(sha(home / name) == wanted, 'PREIMAGE_CHANGED ' + str(home / name))
    for arg, key in [(args.painting_rgba, 'sourcePaintingRGBA'), (args.painting, 'sourcePainting'), (args.group_rgba, 'sourceGroupRGBA')]:
        require(sha(arg) == policy[key], 'PAINTING_CHANGED ' + str(arg))
    require(read(runtime / 'node_modules/@rig-c/parts/package.json')['version'] == '1.25.0', 'PUBLIC_PARTS_VERSION')
    rig, parts, meshreport = [read(p) for p in [rigdir / 'rig.json', partsdir / 'parts.json', rigdir / 'mesh_report.json']]
    before = copy.deepcopy(rig)
    attachment = rig['skins']['default']['topwear']['topwear']
    record = next(p for p in parts['parts'] if p['name'] == 'topwear')
    original_record = copy.deepcopy(record)
    source = image(args.painting_rgba)
    require(source.shape == (2284, 800, 4), 'SOURCE_DOMAIN')
    canvas = np.zeros_like(source)
    x, y, w, h = [record[k] for k in ['x', 'y', 'w', 'h']]
    canvas[y:y+h, x:x+w] = image(partsdir / 'parts/topwear.png')
    raw = image(args.group_rgba)[:, 2496:3296].copy()
    # The former x<218 hard clip removed the actual shoulder too. Select the opaque
    # row interval containing the shirt interior, excluding the detached pale strand.
    domain = policy['repairDomain']
    shoulder = domain['shoulder']
    for row in range(shoulder['rowStart'], shoulder['rowEndExclusive']):
        left = shoulder['interiorColumn']
        while left > 0 and raw[row, left-1, 3] >= 128:
            left -= 1
        source[row, max(0, left-shoulder['fringeBefore']):left+shoulder['insideAfter']] = raw[row, max(0, left-shoulder['fringeBefore']):left+shoulder['insideAfter']]
    solid = source[:, :, 3] >= 128
    sdf = distance_transform_edt(solid) - distance_transform_edt(~solid)
    support_distance = distance_transform_edt(canvas[:, :, 3] < 128)
    domain = policy['repairDomain']
    mask = np.zeros(solid.shape, bool)
    for row in range(domain['rowStart'], domain['rowEndExclusive']):
        xs = np.flatnonzero(solid[row])
        require(len(xs) > 0, 'SOURCE_ROW_EMPTY ' + str(row))
        for col in [int(xs.min()), int(xs.max())]:
            radius = domain['stripRadius']
            mask[row, max(0, col-radius):min(800, col+radius+1)] = True
    mask &= (abs(sdf) <= domain['stripRadius']) & (support_distance <= domain['supportDistance'])
    fixed = canvas.copy()
    fixed[mask] = source[mask]
    # The source figure remains opaque where forearms overlap the dark skirt.
    # In these two bounded trimap strips only, derive continuous matte from the
    # measured source luminance separation (skirt <40, cloth/skin cores >=65).
    old_solid = canvas[:, :, 3] >= 128
    old_sdf = distance_transform_edt(old_solid) - distance_transform_edt(~old_solid)
    rows, cols = np.mgrid[:2284, :800]
    semantic_domain = domain['semantic']
    semantic = np.zeros(solid.shape, bool)
    for left, top, right, bottom in semantic_domain['boxes']:
        semantic |= (cols >= left) & (cols < right) & (rows >= top) & (rows < bottom)
    semantic &= (abs(old_sdf) <= semantic_domain['trimapDistance']) & (source[:, :, 3] >= semantic_domain['sourceAlphaMinimum'])
    luma = .299*source[:, :, 0] + .587*source[:, :, 1] + .114*source[:, :, 2]
    matte = np.rint(np.clip((luma-semantic_domain['luminanceBackground'])/(semantic_domain['luminanceForeground']-semantic_domain['luminanceBackground']), 0, 1)*255).astype('uint8')
    fixed[semantic] = source[semantic]
    fixed[:, :, 3][semantic] = matte[semantic]
    mask |= semantic
    solid = fixed[:, :, 3] >= 128
    sdf = distance_transform_edt(solid) - distance_transform_edt(~solid)
    changed_pixels = np.any(fixed != canvas, axis=2)
    # Later accepted parts may not acquire or lose occlusion in this exterior repair.
    later = np.zeros(solid.shape, bool)
    found = False
    for part in parts['parts']:
        if part['name'] == 'topwear':
            found = True
            continue
        if not found:
            continue
        alpha = image(partsdir / ('parts/' + part['name'] + '.png'))[:, :, 3]
        later[part['y']:part['y']+part['h'], part['x']:part['x']+part['w']] |= alpha > 8
    require(not np.any(changed_pixels & later), 'LATER_PART_OCCLUSION_CHANGED')
    uv = np.array(attachment['uvs']).reshape(-1, 2)
    old_xy = uv * [attachment['width'], attachment['height']] + [x-4, y-4]
    new_xy = old_xy.copy()
    gy, gx = np.gradient(gaussian_filter(sdf, domain['normalSigma']))
    patch_distance = distance_transform_edt(~mask)
    changes = []
    for index, (px, py) in enumerate(old_xy[:attachment['hull']]):
        coords = np.array([[py], [px]])
        sample = lambda field: float(map_coordinates(field, coords, order=1, mode='nearest')[0])
        if sample(patch_distance) > domain['hullNeighbourhood'] or abs(sample(sdf)) > domain['boundaryDistance']:
            continue
        normal = -np.array([sample(gx), sample(gy)])
        require(np.hypot(normal[0], normal[1]) >= .05, 'SOURCE_NORMAL_UNDEFINED ' + str(index))
        dx, dy = normal / np.hypot(normal[0], normal[1]) * domain['outwardMargin']
        new_xy[index] += [dx, dy]
        for weight in attachment['weights'][index]:
            require(weight['bone'] in ['chest', 'hip'], 'BOUNDARY_BONE_CHANGED ' + weight['bone'])
            # Both accepted bind frames have identity linear transforms; assert this below.
            weight['x'] += float(dx)
            weight['y'] -= float(dy)
        changes.append({'vertex': index, 'before': old_xy[index].tolist(), 'after': new_xy[index].tolist(), 'delta': [float(dx), float(dy)]})
    bones = {b['name']: b for b in rig['bones']}
    for name in ['chest', 'hip']:
        while name in bones:
            bone = bones[name]
            require(all(bone.get(k, default) == default for k, default in [('rotation', 0), ('scaleX', 1), ('scaleY', 1), ('shearX', 0), ('shearY', 0)]), 'BIND_FRAME_CHANGED ' + name)
            name = bone.get('parent', '')
    triangles = np.array(attachment['triangles']).reshape(-1, 3)
    def areas(points):
        a, b, c = [points[triangles[:, k]] for k in range(3)]
        return ((b[:, 0]-a[:, 0])*(c[:, 1]-a[:, 1])-(b[:, 1]-a[:, 1])*(c[:, 0]-a[:, 0])) / 2
    initial_area, repaired_area = areas(old_xy), areas(new_xy)
    require(np.all(initial_area * repaired_area > 0), 'TRIANGLE_ORIENTATION_CHANGED')
    # The part domain includes all original texels, recovered cuff pixels, and expanded mesh hull.
    rows, cols = np.where(fixed[:, :, 3] > 0)
    nx = min(x, int(cols.min()), math.floor(new_xy[:, 0].min()))
    ny = min(y, int(rows.min()), math.floor(new_xy[:, 1].min()))
    right = max(x+w, int(cols.max())+1, math.ceil(new_xy[:, 0].max()))
    bottom = max(y+h, int(rows.max())+1, math.ceil(new_xy[:, 1].max()))
    crop = fixed[ny:bottom, nx:right].copy()
    padded = np.pad(crop, ((4, 4), (4, 4), (0, 0)))
    attachment['width'], attachment['height'] = padded.shape[1], padded.shape[0]
    attachment['uvs'] = ((new_xy-[nx-4, ny-4])/[attachment['width'], attachment['height']]).reshape(-1).tolist()
    require(min(attachment['uvs']) >= 0 and max(attachment['uvs']) <= 1, 'UV_DOMAIN')
    mask_image = Image.new('L', (padded.shape[1]*4, padded.shape[0]*4))
    draw = ImageDraw.Draw(mask_image)
    for triangle in triangles:
        draw.polygon([tuple((point-[nx-4, ny-4])*4) for point in new_xy[triangle]], fill=255)
    coverage = np.array(mask_image.resize((padded.shape[1], padded.shape[0]), Image.Resampling.BOX))
    require(not np.any((padded[:, :, 3] >= 128) & (coverage < 128)), 'OPAQUE_TEXEL_OUTSIDE_MESH')
    opaque = int((crop[:, :, 3] > 8).sum())
    record.update(x=nx, y=ny, w=right-nx, h=bottom-ny, opaque_px=opaque)
    # These optional fields describe original run masks, which this post-author
    # transform does not recreate. Retain original mandatory assembly counters
    # as history, and keep the complete original record in provenance.
    for field in ['visible_px', 'occluded_px', 'visible_not_projected_px']:
        record.pop(field, None)
    changed_vertices = [row['vertex'] for row in changes]
    proof = {'spec': policy['spec'], 'sourceRigSHA256': policy['sourceRigFiles']['rig.json'], 'sourcePaintingRGBA': policy['sourcePaintingRGBA'], 'assemblyTraceScope': 'Mandatory projection/merge/seam counters retain the original assembly execution trace and exclude this later edge repair. Original optional visibility values are historical in sourcePartRecord only; no current visibility mask is claimed.', 'sourcePartRecord': original_record, 'partRecord': record, 'repairDomain': domain, 'pixelsChanged': int(changed_pixels.sum()), 'alphaChanged': int((fixed[:, :, 3] != canvas[:, :, 3]).sum()), 'rgbChanged': int(np.any(fixed[:, :, :3] != canvas[:, :, :3], axis=2).sum()), 'boundaryChanges': changes, 'changedTriangles': np.flatnonzero(np.any(np.isin(triangles, changed_vertices), axis=1)).tolist(), 'triangleOrientationReversals': 0, 'minAbsoluteTriangleArea': float(abs(repaired_area).min()), 'opaqueTexelsOutsideMesh': 0, 'laterOcclusionChangedPixels': 0, 'texelRegistrationMaxError': float(np.max(abs(np.array(attachment['uvs']).reshape(-1, 2)*[attachment['width'], attachment['height']]+[nx-4, ny-4]-new_xy)))}
    current_report = next(row for row in meshreport if row['part'] == 'topwear')
    historical_report = copy.deepcopy(current_report)
    current_report.clear()
    current_report.update({key: historical_report[key] for key in ['part', 'vertices', 'triangles', 'hull', 'bones', 'max_influences', 'mean_influences', 'regions']})
    current_report.update(mode='source-alpha-edge-restoration', sourceContourReport=historical_report, restoration=proof)
    expected = policy['reviewedOutput']
    require(hashlib.sha256((json.dumps(rig, indent=2)+'\n').encode()).hexdigest() == expected['rigSHA256'], 'OUTPUT_RIG_NOT_REVIEWED')
    require(pixel_sha(crop) == expected['partRGBA'] and pixel_sha(padded) == expected['rigRGBA'], 'OUTPUT_ART_NOT_REVIEWED')
    # Validate everything above before creating either destination.
    shutil.copytree(rigdir, out)
    outparts.mkdir(parents=True)
    shutil.copytree(partsdir / 'parts', outparts / 'parts')
    Image.fromarray(crop).save(outparts / 'parts/topwear.png')
    Image.fromarray(padded).save(out / 'images/topwear.png')
    write(out / 'rig.json', rig)
    write(out / 'mesh_report.json', meshreport)
    write(outparts / 'parts.json', parts)
    code = """import{readFileSync,writeFileSync}from'node:fs';import{readPng}from'@rig-c/parts/src/raster/png.ts';import{recomposite,measureRecomposite,recompositeRecord}from'@rig-c/parts/src/assemble.ts';const[p,dir,painting]=process.argv.slice(-3),parts=JSON.parse(readFileSync(p,'utf8')),placed=parts.parts.map(record=>({record,image:readPng(dir+'/'+record.name+'.png')}));parts.recomposite=recompositeRecord(measureRecomposite(recomposite(placed,800,2284),readPng(painting),placed));writeFileSync(p,JSON.stringify(parts,null,2)+'\\n');"""
    subprocess.run(['bun', '-e', code, str(outparts/'parts.json'), str(outparts/'parts'), str(args.painting.resolve())], cwd=runtime, check=True)
    proof['recomposite'] = read(outparts / 'parts.json')['recomposite']
    proof['note'] = 'Native RGBA outer-strip restoration plus explicitly inferred source-RGB semantic matte, no resampling or invented artwork. No Spine artifact emitted; ordinary rigc build and rig-parts check remain required.'
    write(out / 'body-edge-restoration.provenance.json', proof)
    print(json.dumps({'status': 'APPLIED_UNBUILT', 'rig': str(out), 'parts': str(outparts), 'rigSHA256': sha(out/'rig.json'), 'partsSHA256': sha(outparts/'parts.json'), 'changedBoundaryVertices': len(changes)}))


if __name__ == '__main__':
    main()
