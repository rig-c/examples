#!/usr/bin/env python3
"""Encode and verify transparent README loops without altering source poses."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageStat, features


def visible_difference(a, b):
    if a.size != b.size:
        raise ValueError('PREVIEW_LOOP_SIZE_MISMATCH')
    a, b = a.convert('RGBA'), b.convert('RGBA')
    channels = ImageChops.difference(a, b).split()
    rgb = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2])
    support = ImageChops.lighter(a.getchannel('A'), b.getchannel('A')).point(lambda x: 255 if x else 0)
    mask = ImageChops.lighter(ImageChops.multiply(rgb, support), channels[3]).point(lambda x: 255 if x else 0)
    return mask.histogram()[255]


def foreground_mae(a, b):
    if a.size != b.size:
        raise ValueError('PREVIEW_LOOP_SIZE_MISMATCH')
    a, b = a.convert('RGBA'), b.convert('RGBA')
    mask = ImageChops.lighter(a.getchannel('A'), b.getchannel('A')).point(lambda x: 255 if x else 0)
    if not mask.getbbox():
        return 0.0
    # Pillow's 8-bit RGBa conversion defines this encoded-transition metric.
    diff = ImageChops.difference(a.convert('RGBa'), b.convert('RGBa'))
    return sum(ImageStat.Stat(diff, mask).mean) / 4


def check_loop(images, durations, loop, endpoint):
    if len(images) < 2 or len(durations) != len(images):
        raise ValueError('PREVIEW_LOOP_FRAME_COUNT')
    if any(not isinstance(d, int) or d <= 0 for d in durations) or sum(durations) != 3333 or loop != 0:
        raise ValueError('PREVIEW_LOOP_TIMING')
    if not isinstance(endpoint, (tuple, list)) or len(endpoint) != 2 or any(not isinstance(im, Image.Image) for im in endpoint):
        raise ValueError('PREVIEW_LOOP_ENDPOINT_REQUIRED')
    endpoint_diff = visible_difference(*endpoint)
    internal = [foreground_mae(a, b) for a, b in zip(images, images[1:])]
    seam = foreground_mae(images[-1], images[0])
    if seam > max(internal):
        raise ValueError('PREVIEW_LOOP_ENCODED_SEAM')
    if not any(visible_difference(images[0], im) for im in images[1:]):
        raise ValueError('PREVIEW_LOOP_STATIC')
    return {'visibleEndpointDifferingPixels': endpoint_diff, 'foregroundPremultipliedRGBA': {'adjacentMAEMin': min(internal), 'adjacentMAEMax': max(internal), 'lastToFirstMAE': seam}, 'nonstatic': True, 'PASS': True}


def controls():
    a = Image.new('RGBA', (2, 2), (40, 60, 80, 255))
    b = a.copy(); b.putpixel((0, 0), (80, 60, 80, 255))
    assert check_loop([a, b], [1667, 1666], 0, (a, a))['PASS']
    assert check_loop([a, b], [1667, 1666], 0, (a, b))['visibleEndpointDifferingPixels'] == 1
    low = Image.new('RGBA', (1, 1), (0, 0, 0, 1)); low2 = low.copy(); low2.putpixel((0, 0), (1, 0, 0, 1))
    assert visible_difference(low, low2) == 1
    assert visible_difference(low, Image.new('RGBA', (1, 1), (0, 0, 0, 0))) == 1
    transparent = Image.new('RGBA', (2, 2), (255, 0, 0, 0)); hidden = Image.new('RGBA', (2, 2), (0, 255, 0, 0))
    assert visible_difference(transparent, hidden) == 0
    failures = [
        ('missing endpoint', lambda: check_loop([a, b], [1667, 1666], 0, None), 'ENDPOINT_REQUIRED'),
        ('nonfinite duration', lambda: check_loop([a, b], [float('nan'), 3333], 0, (a, a)), 'TIMING'),
        ('static', lambda: check_loop([a, a], [1667, 1666], 0, (a, a)), 'STATIC'),
        ('empty', lambda: check_loop([], [], 0, (a, a)), 'FRAME_COUNT'),
        ('duration', lambda: check_loop([a, b], [0, 3333], 0, (a, a)), 'TIMING'),
        ('loop', lambda: check_loop([a, b], [1667, 1666], 1, (a, a)), 'TIMING'),
        ('size', lambda: visible_difference(a, Image.new('RGBA', (1, 1))), 'SIZE_MISMATCH'),
    ]
    # Monotonic tiny transitions have an intentionally excessive wrap jump.
    ramp = [Image.new('RGBA', (2, 2), (n, 0, 0, 255)) for n in (0, 10, 20)]
    failures.append(('seam', lambda: check_loop(ramp, [1111] * 3, 0, (a, a)), 'ENCODED_SEAM'))
    for name, action, code in failures:
        try:
            action()
        except ValueError as error:
            assert code in str(error), (name, str(error))
        else:
            raise AssertionError('CONTROL_DID_NOT_REFUSE_' + name)
    return {'normalPeriodic': True, 'visibleEndpointReported': True, 'alphaOneRGBDefectDetected': True, 'hiddenTransparentRGBIgnored': True, 'plantedSeamRefused': True, 'edgeRefusals': [name for name, _, _ in failures], 'PASS': True}


def encode(evidence, output, width, height, quality, preflight=False):
    control = controls()
    inputs = json.loads((evidence / 'capture-inputs.json').read_text())
    count = 2 if preflight else 100
    paths = [evidence / f'frame-{i:03}.png' for i in range(count + 1)]
    aggregate = hashlib.sha256()
    for p in paths:
        data = p.read_bytes(); aggregate.update(data)
        if hashlib.sha256(data).hexdigest() != inputs['frames'][p.name]:
            raise ValueError('PREVIEW_FRAME_HASH_DRIFT')
    first, endpoint = [Image.open(p).convert('RGBA') for p in (paths[0], paths[-1])]
    # Persist a small boundary sheet before refusing so a red result is inspectable.
    sheet = Image.new('RGB', (960, 300), 'white')
    for col, (label, image) in enumerate([('first', first), ('one-cycle endpoint' if not preflight else 'probe endpoint', endpoint), ('difference', ImageChops.difference(first, endpoint))]):
        white = Image.alpha_composite(Image.new('RGBA', image.size, 'white'), image).convert('RGB') if col < 2 else image.convert('RGB')
        sheet.paste(white.resize((320, 277), Image.Resampling.LANCZOS), (col * 320, 23)); ImageDraw.Draw(sheet).text((col * 320 + 5, 5), label, fill='black')
    sheet.save(evidence / 'loop-boundary.png', optimize=True)
    n = 3 if preflight else 67
    indices = [round(i * count / n) for i in range(n)]
    durations = [round((i + 1) * 10000 / 3 / n) - round(i * 10000 / 3 / n) for i in range(n)]
    images = [Image.open(paths[i]).convert('RGBA').resize((width, height), Image.Resampling.LANCZOS) for i in indices]
    images[0].save(output, format='WEBP', save_all=True, append_images=images[1:], duration=durations, loop=0, lossless=False, quality=quality, alpha_quality=100, method=4, minimize_size=True)
    decoded, actual_durations = [], []
    with Image.open(output) as im:
        actual_loop = im.info.get('loop')
        for i in range(im.n_frames):
            im.seek(i); im.load(); decoded.append(im.convert('RGBA')); actual_durations.append(im.info.get('duration'))
    if not preflight and actual_durations != durations:
        raise ValueError('PREVIEW_ENCODED_DURATIONS')
    if not preflight and len(decoded) != n:
        raise ValueError('PREVIEW_ENCODED_FRAME_COUNT')
    verification = {'preflightOnly': True, 'acceptanceMeasured': False} if preflight else check_loop(decoded, actual_durations, actual_loop, (first, endpoint))
    alpha_error = max(ImageChops.difference(a.getchannel('A'), b.getchannel('A')).getextrema()[1] for a, b in zip(images, decoded))
    if not preflight and alpha_error != 0:
        raise ValueError('PREVIEW_ALPHA_ENCODING_DRIFT')
    verification['alphaMaxErrorFromEncodingPNG'] = alpha_error
    alpha_stats = []
    for im in decoded:
        a = im.getchannel('A'); hist = a.histogram(); corners = [a.getpixel(p) for p in [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]]
        alpha_stats.append({'min': a.getextrema()[0], 'max': a.getextrema()[1], 'intermediate': sum(hist[1:255]) > 0, 'corners': corners})
    if not preflight and any(r['min'] != 0 or r['max'] != 255 or not r['intermediate'] or any(r['corners']) for r in alpha_stats):
        raise ValueError('PREVIEW_ALPHA_CONTRACT')
    result = {'controls': control, 'verification': verification, 'decodedFrames': len(decoded), 'durationMs': sum(d for d in actual_durations if d is not None), 'decodedLoop': actual_loop, 'sourceFrameIndices': indices, 'frameDurationsMs': durations, 'framesSHA256': aggregate.hexdigest(), 'frameOrder': [p.name for p in paths], 'alpha': alpha_stats, 'encoder': {'Pillow': __import__('PIL').__version__, 'libwebp': features.version('webp'), 'method': 4, 'minimizeSize': True, 'alphaQuality': 100}}
    (evidence / 'preview-loop.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--controls', action='store_true'); parser.add_argument('--evidence', type=Path); parser.add_argument('--out', type=Path); parser.add_argument('--width', type=int); parser.add_argument('--height', type=int); parser.add_argument('--quality', type=float); parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    if args.controls:
        print(json.dumps(controls()))
    else:
        encode(args.evidence, args.out, args.width, args.height, args.quality, args.preflight)
        print('PREVIEW_READER_CHAIN_PROBE_PASS' if args.preflight else 'PREVIEW_LOOP_PASS')
