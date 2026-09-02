# Asset provenance

## Project icon

`docs/images/icon-source.png` was generated specifically for this project with OpenAI image generation. The unchanged source contains a structurally detected PNG C2PA manifest-store chunk; cryptographic verification and signer trust were not established because no conforming verifier or trust policy was supplied.

`docs/images/icon.png` is a 400-by-400-pixel ImageMagick resize required for the Comfy Registry listing. The resize does not retain the source C2PA structure, so this human-readable record accompanies the derivative. The Registry package excludes the larger source asset through `.comfyignore`, while the source remains available in the GitHub repository.

The artwork contains no NVIDIA, DLSS, ComfyUI, or other third-party logo.

The icon is project branding only. It does not imply affiliation with or endorsement by NVIDIA, ComfyUI, RenoDX, VapourKit, or OpenAI.

## Synthetic benchmark sources

`docs/images/benchmark-rainy-city-source.png` and `docs/images/benchmark-industrial-source.png` were generated specifically for this project's documentation with OpenAI image generation on 2026-09-02. They are synthetic test inputs selected for fine geometry, reflections, material detail, people, and strong depth layering; they are not game captures or claims of native engine output.

Both PNG files contain a structurally detected `caBX` manifest-store chunk. A conforming C2PA verifier and named trust policy were unavailable, so cryptographic verification and signer trust remain unknown. The bounded metadata-privacy audit reported `NONE_OBSERVED` for supported privacy fields.

## ComfyUI screenshots

The four `comfyui-vda-*` and `comfyui-flashdepth-*` PNGs were captured from a local isolated ComfyUI 0.32.0 instance loading the published workflow JSON files. Their bounded metadata-privacy audits reported `NONE_OBSERVED`. Screenshots demonstrate graph layout and settings only; they are not inference-quality evidence.

## Runtime proof derivatives

The files under `docs/images/proofs/` derive from the two synthetic benchmark sources above. They were created locally on 2026-09-02 with the user-supplied NVIDIA runtime through the same VapourSynth bridges used by the ComfyUI nodes. The included `runtime-reports.txt` files record the reported runtime feature, dimensions, guides, and SR preset.

The overview sheets resize panels proportionally. The detail sheets enlarge 1× crops by an exact 2× using nearest-neighbor sampling and place them beside native 2× output crops. Neither sheet changes an image's aspect ratio.

The runtime derivatives and comparison sheets do not retain the source PNG's structural C2PA marker. A full scan of both JPEG overview sheets found no supported provenance carrier. This absence does not identify the author or prove human authorship; the human-readable record above links the derivatives to their generated sources.
