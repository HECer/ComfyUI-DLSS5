# FlashDepth optional backend

FlashDepth is an expert, high-resolution alternative to the default Video Depth Anything Small workflow. It is not installed into ComfyUI because the official project currently pins Torch 2.4 or older and compiles Mamba/CUDA extensions. Replacing ComfyUI's Torch build can break other nodes.

Use an isolated environment and follow the official upstream installation instructions:

1. Clone <https://github.com/Eyeline-Labs/FlashDepth> to a separate folder.
2. Create its own Python environment and install the upstream dependencies there.
3. Download the official checkpoint from <https://huggingface.co/Eyeline-Labs/FlashDepth> into the path named by the upstream README.
4. In **DLSS 5 FlashDepth (External, Optional)**, select that environment's `python.exe` and the cloned repository folder.

Choose **FlashDepth Full (2K)** for high-resolution footage. Upstream recommends **FlashDepth-L** when the short side is below roughly 518 pixels. The node exchanges a temporary video with the isolated process and removes it after execution.

The FlashDepth repository and weights are Apache-2.0. NVIDIA's runtime DLL is separate, user-supplied software and is not included here.
