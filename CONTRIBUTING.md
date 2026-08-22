# Contributing images

Submit one self-contained folder under `images/`, named with lowercase kebab-case words.

Every submission must contain:

- `manifest.json`, following the [C64 Layered Image Format](https://github.com/angelday/c64-layered-image-format);
- every PNG named by the manifest; and
- `preview.jpg`, a low-resolution JPEG of the default composition. It uses the first animation frame and the phase-intent composition, and excludes overlays.

Keep asset names lowercase kebab-case. Do not add ZIP files, app-specific thumbnails, or generated build files to an image folder. Releases will package accepted folders as ZIP downloads.
