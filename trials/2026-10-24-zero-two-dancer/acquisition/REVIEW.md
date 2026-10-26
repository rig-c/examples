# Reviewed ZeroTwo external acquisition

The first supplied extract.py selects argmax(mean(scores[:17])), the most
confident body-17 person per frame. This differs from Toca Toca's extent rule;
that extent rule is not used. Score < 0.3 marks a joint occluded. Body-18 names,
neck at the shoulders' midpoint, xy rounding to one decimal and score rounding
to three decimals are preserved. Model choice is unchanged: Wholebody balanced,
rtmw-dw-x-l and YOLOX-M, CPU ONNX Runtime. Exact packages and ONNX hashes reuse
the verified Toca acquisition pins.

The first provenance README documents a 1080x1920 re-encoding. This run reads
the original video afresh, not that old ref1080.mp4: original 2160x3840 frames
are resized to 1080x1920 by cv2.INTER_AREA before inference. No frame is dropped,
retimed or read from an existing pose. The resize operator is explicitly
frozen here; the old README did not state its interpolation/encoding settings.
The reported coordinates are in the resulting 1080x1920 picture space.

Reviewed changes from the first recipe: parameterized paths; correct source
credit (ZeroTwo / YouTube Shorts video (link withheld), creator not identified); pinned
packages and checkpoint digests; CPU provider/thread limits; finite point
checks; frozen source hash/identity; three-frame precheck; structured outputs
and progress. No detector value is manually edited. No reference pixels are
written. Public output is acquisition/pose.json; 133-point raw stays withheld
with its hash. The original recipe hash is in pins.json.

External acquisition is an input-producing step, not a rig-pose command:

```sh
sh acquisition/run.sh --video withheld/orig.webm --models withheld/models --out work/precheck --frames 0,156,312
sh acquisition/run.sh --video withheld/orig.webm --models withheld/models --out work/acquisition
```

Both source and processing dimensions, 24 fps, 313 decoded frames and zero
empty frames are required by acceptance.json before any inference. The
first precheck must pass before the full extraction. No earlier pose is used.

## Recorded decoder refusal and remedy

The first bounded precheck decoded zero frames: bundled OpenCV AV1 reported
"Your platform doesn't support hardware accelerated AV1 decoding", "Failed to
get pixel format" and "Get current frame error". It exited 1 and did not run
full acquisition. Package/model checks passed; this is not a model change.

A separate Nova capability check identified FFmpeg 7.0.2-static with libdav1d.
The documented software decoder now feeds native-size BGR frames through a
raw pipe to the same frozen OpenCV INTER_AREA resize and selection rule.
No old ref1080 video is read, no reference frame is written, and no detector
value is manually changed. Decoder version and command are recorded before
fresh inference; see pins.json and https://ffmpeg.org/ffmpeg-codecs.html#libdav1d.

```sh
ffmpeg -hide_banner -loglevel error -c:v libdav1d -threads 4 -i withheld/orig.webm -map 0:v:0 -an -fps_mode passthrough -pix_fmt bgr24 -f rawvideo pipe:1
```
