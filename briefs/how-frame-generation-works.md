## Key facts
- Frame generation in all current consumer implementations is interpolation, not extrapolation — the generated frame is inserted between two already-rendered frames, which requires holding back a real frame (https://www.intel.com/content/www/us/en/developer/articles/technical/xess2-whitepaper.html)
- DLSS 3 Frame Generation fed a model with game data such as motion vectors and depth, plus an optical flow field from the RTX 40 Series hardware Optical Flow Accelerator, to generate one additional frame (https://www.nvidia.com/en-us/geforce/news/dlss4-multi-frame-generation-ai-innovations/)
- DLSS 4 replaced hardware optical flow with an AI model, and the frame-gen model now runs once per rendered frame to produce multiple frames (https://www.nvidia.com/en-us/geforce/news/dlss4-multi-frame-generation-ai-innovations/)
- NVIDIA's stated reason multi-frame was not viable on RTX 40: both the Optical Flow Accelerator and the AI model had to run for every generated frame, throttling the GPU and lowering input frame rate (https://www.nvidia.com/en-us/geforce/news/dlss4-multi-frame-generation-ai-innovations/)
- Blackwell adds hardware Flip Metering, moving frame pacing from CPU-level scheduling to the GPU display engine for more precise display timing (https://pcoptimizedsettings.com/the-4-technologies-driving-nvidia-dlss-4-multi-frame-generation/)
- Frame generation requires engine-side resource tagging: Streamline's DLSS-G plugin intercepts the present call with a proxy swap chain, and requires depth buffers, motion vectors and HUD-less color buffers (https://github.com/NVIDIA-RTX/Streamline/blob/main/docs/ProgrammingGuideDLSS_G.md)
- XeSS-FG interpolates a frame between two originals, then changes the order of presentation — showing the interpolated frame first and delaying the game's real frame (https://www.intel.com/content/www/us/en/developer/articles/technical/xess2-whitepaper.html)
- Intel requires XeLL latency reduction to be enabled whenever XeSS-FG is on; NVIDIA likewise pairs frame gen with Reflex (https://www.intel.com/content/www/us/en/developer/articles/technical/xess-fg-developer-guide.html)
- AMD FSR Frame Generation uses ML trained on Instinct GPUs, predicting per-pixel motion and appearance and blending it with motion-vector reprojection (https://gpuopen.com/amd-fsr-framegeneration/)
- AFMF is driver-level and needs no developer integration, but interpolates full frames including menus and UI (https://videocardz.com/newz/amd-preparing-fluid-motion-frames-2-1-afmf)
- Without in-game motion vectors, depth and timing data, driver-level interpolation produces more visual artifacts (https://www.club386.com/amd-afmf-2-1-will-let-you-choose-between-smooth-and-quality-frame-generation/)
- Multi Frame Generation is Blackwell-exclusive; RTX 40 owners get the DLSS 4 transformer model for Super Resolution/Ray Reconstruction/DLAA via NVIDIA app override but not the frame multiplier (https://arsenalpc.com/dlss-4-multi-frame-generation-explained-real-benchmarks-fake-frames-debate-and-what-it-means-for-your-rtx-50-series-build/)
- DLSS 4.5 Dynamic MFG varies the number of generated frames at runtime to hit a target frame rate (https://www.nvidia.com/en-us/geforce/news/dlss-4-5-rtx-path-tracing-game-announcements-gdc-2026/)
- NVIDIA states native DLSS Frame Generation and driver-level Smooth Motion are competing technologies and should not be stacked — doing so lowers performance and causes artifacts (https://docs.nvidia.com/datacenter/tesla/driver-installation-guide/gaming.html)
- 2D elements without geometry or motion vectors (in-world display screens, signage, paintings) are a recurring artifact source (https://hothardware.com/news/nvidia-dlss-45-dynamic-mfg-tested)

## Figures
- DLSS 4 frame-gen model: 40% faster, 30% less VRAM than DLSS 3's (https://www.nvidia.com/en-us/geforce/news/dlss4-multi-frame-generation-ai-innovations/)
- Warhammer 40,000: Darktide — 10% faster frame rate and 400MB less memory at 4K max settings with the new FG model (https://www.nvidia.com/en-us/geforce/news/dlss4-multi-frame-generation-ai-innovations/)
- NVIDIA claim: up to 8X frame rate vs brute-force rendering; up to 1.7X going from FG to MFG (https://www.nvidia.com/en-us/geforce/news/dlss4-multi-frame-generation-ai-innovations/)
- Alan Wake 2, 4K DLSS Quality, Reflex on: 96 FPS / 32ms native → 165 FPS / 39ms at 2X FG, with render rate falling 96→83 FPS (https://www.techspot.com/article/2945-nvidia-dlss-4/)
- Cyberpunk 2077: base 78 FPS → 139 / 197 / 250 FPS across FG modes (up to +221%), latency 34ms → 44ms, render rate down to 62 FPS (https://www.techspot.com/article/2945-nvidia-dlss-4/)
- Hogwarts Legacy: MFG 4X tripled output frame rate; latency worsened 19ms → 27ms (https://www.techspot.com/article/2945-nvidia-dlss-4/)
- TechSpot recommendation: start above 100 FPS base; 4X MFG turned a 110 FPS "feel" into a 79 FPS feel in one test (https://www.techspot.com/article/2945-nvidia-dlss-4/)
- RTX 5090, Cyberpunk 2077 path-traced 4K, DLSS Performance + 4X FG: ~280 FPS at ~52ms; 2X and 3X both ~44ms; DLSS off ~30 FPS with latency spiking to ~70ms (https://www.techpowerup.com/331242/nvidia-geforce-rtx-5090-performance-in-cyberpunk-2077-with-and-without-dlss-4-detailed)
- AMD guidance: below 60 fps input not recommended for FSR Frame Generation; sub-30 fps pre-interpolation should be avoided entirely (https://gpuopen.com/amd-fsr-framegeneration/)
- Intel guidance: 40 FPS minimum input for XeSS-FG, 60 FPS recommended for best latency, fluidity and fidelity (https://wccftech.com/how-to/how-to-use-nvidia-dlss-amd-fsr-intel-xess-frame-generation-technologies/)
- THE FINALS, RTX 5070, 4K max: 56ms with no Reflex → 27ms with Reflex Low Latency → 14ms with Reflex 2 Frame Warp (75% total reduction) (https://www.nvidia.com/en-us/geforce/news/reflex-2-even-lower-latency-gameplay-with-frame-warp/)
- VALORANT at 800+ FPS on RTX 5090: under 3ms PC latency with Reflex 2 Frame Warp (https://www.techpowerup.com/330822/nvidia-reflex-2-with-new-frame-warp-technology-reduces-latency-in-games-by-up-to-75-coming-to-the-finals-and-valorant)
- 75 existing DLSS Frame Generation games and apps upgradeable to MFG on RTX 50 Series via NVIDIA app (https://www.nvidia.com/en-us/geforce/news/dlss4-multi-frame-generation-ai-innovations/)
- DLSS 4.5 Dynamic MFG and 6X MFG overrides: March 31, RTX 50 Series, Game Ready Driver 595.79 WHQL or newer (https://www.nvidia.com/en-us/geforce/news/gdc-2026-nvidia-geforce-rtx-announcements/)
- XeSS SDK 2.1.0 opened XeSS-FG to non-Intel GPUs supporting Shader Model 6.4 — GTX 10-series Pascal or newer, RX 5000-series RDNA or newer (https://www.jonpeddie.com/news/intels-xess-2-supports-ai-driven-frame-generation-on-all-gpus/)

## Quotes
- "It seems to me that the majority of the extra latency still comes from buffering that extra frame, but adding further intermediate frames comes with a relatively minimal increase in latency" — Richard Leadbetter, Digital Foundry (https://www.digitaltrends.com/computing/how-dlss-4-actually-works/)
- "Our new DLSS transformer model uses a vision transformer, enabling self-attention operations to evaluate the relative importance of each pixel across the entire frame, and over multiple frames." — NVIDIA (https://www.nvidia.com/en-us/geforce/news/dlss4-multi-frame-generation-ai-innovations/)
- "we predict per-pixel motion and appearance, then blend that with motion vector reprojection to generate a new in-between frame" — AMD GPUOpen (https://gpuopen.com/amd-fsr-framegeneration/)
- "going below 60 fps is not recommended as interpolation artifacts become more prominent at lower frame rates" — AMD GPUOpen, FSR Frame Generation docs (https://gpuopen.com/amd-fsr-framegeneration/)
- "Native DLSS Frame Generation and Smooth Motion are competing technologies and should not be used together." — NVIDIA driver documentation (https://docs.nvidia.com/datacenter/tesla/driver-installation-guide/gaming.html)
- "The technology accurately interpolates background elements, creating native-like smoothness" — TechSpot DLSS 4 review (https://www.techspot.com/article/2945-nvidia-dlss-4/)

## Suggested sections
- **The pipeline** — where FG sits: post-render, pre-present; proxy swap chain intercepting the present call; inputs tagged by the engine (motion vectors, depth, HUD-less color)
- **Interpolation vs extrapolation** — why holding back a real frame is structurally required; why the latency floor exists; Frame Warp / reprojection as the alternative path
- **The three costs** — added latency, reduced render (base) rate from FG overhead, VRAM; each with measured numbers
- **Generation-count scaling** — 2X vs 3X vs 4X vs 6X; first-frame buffer cost dominates, marginal frames cheap; Dynamic MFG as target-rate arbitration
- **Vendor implementations side by side** — DLSS 4/4.5, FSR Redstone ML FG, XeSS-FG, AFMF/Smooth Motion; integrated vs driver-level; hardware gating
- **Artifact taxonomy** — UI/HUD handling, 2D screens without motion vectors, ghosting and halos, disocclusion, low-base-rate amplification
- **When not to use it** — base-rate floors from each vendor, competitive/mouse-look scenarios, VRR and refresh-rate headroom requirements, stacking conflicts

## Terms to define
- **Frame interpolation** — generating an intermediate frame from two real frames that already exist
- **Frame extrapolation** — predicting a future frame from past frames only; no buffering penalty, harder to get right
- **Motion vectors** — per-pixel engine-supplied data describing where each pixel moved between frames
- **Optical flow** — motion field estimated from the images themselves rather than supplied by the engine
- **Base / render rate** — the real engine frame rate, which governs responsiveness regardless of displayed FPS
- **PC / system latency** — click-to-photon delay; the number that actually tracks "feel"
- **Reflex / XeLL / Anti-Lag 2** — vendor latency-reduction layers that pace CPU-GPU work; mandatory companions to FG
- **Frame Warp** — late-stage reprojection of a rendered frame to the newest mouse input before display
- **Flip metering** — GPU display-engine control of when each frame is flipped to screen, for even pacing
- **Proxy swap chain** — FG-owned present queue substituted for the game's own
- **HUD-less color buffer** — scene render without UI, so interpolation doesn't smear the HUD
- **Disocclusion** — pixels revealed by motion that have no prior data to interpolate from
- **Vision transformer / self-attention** — model architecture weighing pixel relationships across a whole frame and across frames
- **DP4a / XMX / Tensor Cores** — the integer-dot-product and matrix hardware paths the models run on
- **Ghosting** — trailing residue of a moving object left in a generated frame
- **VRR (FreeSync / G-SYNC)** — variable refresh; required for FG output to pace cleanly
