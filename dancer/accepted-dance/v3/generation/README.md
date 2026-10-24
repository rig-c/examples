# Historical generated-part provenance

These are the recipes and receipts of the accepted source, not operations run
by this transfer. Accepted PNGs are used byte for byte. [Source file hashes](source-files.json)
also name omitted generation paintings, masks, warp/control images and separated
layers; a hash reference is not a claim that the file is committed. Reference
footage and its pixels are withheld. The final replay needs only the three
accepted pieces and pinned public base images.

The source configuration pins `novaAnimeXL_ilV80.safetensors`, no LoRA,
832×1216 latent size, 30 steps, CFG 5.5, `euler_ancestral` / `normal`.
The inpaint graph in [inpaint2.py](keys3/inpaint2.py) uses
`controlnet-openpose-sdxl-1.0.safetensors` at strength 1.0 through 0.9,
DifferentialDiffusion, denoise 1.0, then `4x-AnimeSharp.pth` and 0.5 Lanczos.
Each selected seed receipt below preserves the complete positive/negative text,
warp settings and historical generation identifier. The base config seed 74101
belongs to the original painting; it is not one of the selected inpaint seeds.

| Accepted output | Historical key / seed | Exact prompt and warp record | See-through record |
| --- | --- | --- | --- |
| Head arms | H1_hold_head / 1 | [seed receipt](keys3/inpaint_H1_hold_head/warp_s1.json), [prewarp](keys3/inpaint_H1_hold_head/prewarp.json) | [metadata](keys3/set_H1_hold_head/layers_full/meta.json) |
| Low arms | H2z_hold_low / 53 | [seed receipt](keys3/inpaint_H2z_hold_low/warp_s53.json), [prewarp](keys3/inpaint_H2z_hold_low/prewarp.json) | [metadata](keys3/set_H2z_hold_low/layers_full/meta.json) |
| Waist painting | H1m_hold_head / 62 | [seed receipt](keys3/inpaint_H1m_hold_head/warp_s62.json), [prewarp](keys3/inpaint_H1m_hold_head/prewarp.json) | [metadata](keys3/set_H1m_hold_head/layers_full/meta.json) |

The historical commands, from the dancer-generation workspace, were:

```sh
python3 keys3/inpaint2.py H1_hold_head warp 1
python3 keys3/inpaint2.py H2z_hold_low warp 53
python3 keys3/inpaint2.py H1m_hold_head warp 62
RIG_PARTS_BIN="$PINNED_RUNTIME/node_modules/.bin" bash keys3/run_seethrough.sh H1_hold_head keys3/inpaint_H1_hold_head/warp_s1.png
RIG_PARTS_BIN="$PINNED_RUNTIME/node_modules/.bin" bash keys3/run_seethrough.sh H2z_hold_low keys3/inpaint_H2z_hold_low/warp_s53.png
RIG_PARTS_BIN="$PINNED_RUNTIME/node_modules/.bin" bash keys3/run_seethrough.sh H1m_hold_head keys3/inpaint_H1m_hold_head/warp_s62.png
```

`COMFY_HOST` is supplied by the operator; no endpoint or credentials are stored.
The only path adapter replaces the historical absolute executable directory in
`run_seethrough.sh` with `RIG_PARTS_BIN`. See declared-repairs-v3.json at the corpus root
for before/after file hashes. No graph, image, geometry or motion value was
changed. The wrapper runs parts 1.60.0 `inputs --source ... --config
alts/seethrough_config.json`, then `comfy seethrough --resolution 1024 --steps
30 --seed 42 --wait 900`, with no offload or LaMa. Each selected receipt records
29 separated layers, `quant: none`, offload false and LaMa false.

The supplied source closure contains the base generation config, H1m and H2z
configs, imported `keys2/masks.py` and See-through config. H1's original config
file is not supplied; its complete actual graph prompt is preserved by the seed
receipt. Do not invent a replacement from H1m. The historical model binary
digests and ComfyUI/custom-node revisions were not recorded in these receipts;
regeneration byte identity is not claimed. These historical commands also need
the hash-referenced warp/mask/layer inputs, which are not bundled. They are
provenance commands, not an instruction to regenerate a new accepted hand pass.

[cut_piece.py](scripts/cut_piece.py), [cut_jacket.py](scripts/cut_jacket.py),
[assemble_hold.py](scripts/assemble_hold.py) and [v3_waist.py](scripts/v3_waist.py)
are retained as original historical recipe source. The final assembly chose
`chest`, not the assembly script's default `hip`, with frame boundaries
124/219/234/329. The final waist script historically extended the H1m midriff
70 rig pixels upward and added the 17u compensated chest lift. This transfer
does **not** run them or re-author their outputs. Placement JSON describes the
cut's setup coordinates; final accepted attachment values come directly from
`../rig.json`, not a newly recomputed placement.
