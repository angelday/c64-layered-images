# Layered C64 Image Format

A collection-ready layered image is a folder containing artwork as separate PNG layers, a `manifest.json` that describes them, and a required `preview.jpg`.

This specification describes both static layered artwork and manifest-timed layer animation. See [Layer animation](#layer-animation) for the animation object, frame order, and timing rules.

Manifests do not carry a version. Unknown fields are ignored rather than rejected, so compatible additions do not prevent an existing implementation from using a manifest.

Authors choose the layer breakdown, order, and descriptions. The rules below are the only constraints.

## The folder

A collection-ready image folder contains:

- `manifest.json`, which names and describes the image;
- `preview.jpg`, a low-resolution JPEG of the artwork's default composition; and
- one PNG named `artwork.png` when the manifest has no `layers` array, unless `image` provides a different filename; or
- the PNG files named by every static layer and animation frame when the manifest has a `layers` array.

## Preview

`preview.jpg` is required when an image folder is submitted to a collection. It is a low-resolution JPEG for listing or distributing the image, not an artwork asset: it is not named in the manifest and is not used to reconstruct or render the image. Collection submission checks enforce this requirement; format readers ignore the file.

For a single-image folder, the preview shows the image file. For a layered image, it shows the non-overlay layers in their declared compositing order, using the first frame of an animation and the `phaseIntent` layer in place of a phase pair. Its precise dimensions, palette, display treatment, and encoding settings are publishing choices.

## The simplest image

One picture and a credit:

```json
{
  "name": "Image title",
  "author": "Artist name",
  "released": 2026
}
```

| Field | Required | Default | Meaning |
| --- | --- | --- | --- |
| `name` | yes | - | Title |
| `author` | yes | - | Artist credit |
| `released` | no | none | Year |
| `csdb` | no | none | CSDb release-page URL |
| `image` | no | `artwork.png` | Artwork filename; ignored when `layers` is present |
| `layers` | no | none | When present, makes the image layered |
| `hasSprites` | no | `false` | See [Hardware sprites](#hardware-sprites) |

Filenames are single path components. A filename containing `/` or `..` is rejected, so an implementation can read assets only from the image folder.

The format does not declare a graphics mode, palette, screen area, or display scale. Those are properties of the source artwork or choices made by an implementation, not properties of the layer manifest.

## PNG requirements

Every PNG in the folder - a standalone image, a static layer, or an animation frame - must:

- be fully opaque or fully transparent per pixel - no partial alpha,
- match every other PNG in the folder in width and height.

The format does not prescribe a PNG color type or a particular C64 palette. A writer may use indexed or truecolor PNGs, provided that every asset uses binary alpha and has the same canvas dimensions.

## Layers

Replace `image` with `layers` to compose the artwork from separate parts. Non-overlay layers are listed **bottom first**: the first non-overlay layer is the base, and later non-overlay layers composite over it. Overlays follow their own compositing rule below.

```json
"layers": [
  { "file": "background.png", "role": "background" },
  { "file": "bitmap-background.png", "name": "Bitmap Background" }
]
```

| Field | Required | Default | Meaning |
| --- | --- | --- | --- |
| `file` | static layers | - | PNG in this folder; optional when `animation` is present |
| `name` | no | filename stem or first frame stem | Suggested layer label |
| `role` | no | `data` | What kind of layer it is |
| `phaseGroup` | no | - | Required by the phase roles |
| `description` | no | none | Informational note about the layer |
| `animation` | no | none | Timed replacement frames for this layer |

A layer with no `role` is ordinary artwork. A `background` layer is the first compositing layer; it is only valid as the first layer. A static layer needs `file`. An animated layer can omit it, in which case its first frame is the layer's initial frame.

Use `description` when a layer needs explanation; omit it when the name says enough.

## Overlays

An overlay is an annotation rather than artwork: sprite position markers, raster split lines, a sketch aligned over the finished piece, or a reference capture.

```json
{ "file": "sprite-markers.png", "name": "Sprite Markers", "role": "overlay" }
```

Overlays are composited after every non-overlay layer regardless of where they sit in the array. Their order relative to each other still follows the array. Whether an overlay is initially visible is a presentation choice, not part of this format.

They use the same canvas as every other layer, so an annotation stays aligned with the artwork.

## Hardware sprites

```json
{ "file": "sprite-borders.png", "name": "Sprite Borders", "role": "sprite" }
```

Sprites are not detectable from pixels - on screen, they are indistinguishable from bitmap artwork - so the manifest must declare their use.

A layer with `role: "sprite"` declares its use of hardware sprites. Where sprites are not separated into their own layer, use the top-level `hasSprites` field instead. Either declaration identifies the image as using sprites, so setting `hasSprites` alongside sprite layers is redundant but valid.

## Layer animation

An `animation` object supplies a sequence of full-canvas PNG frames for its layer. The first frame is the layer's initial frame.

```json
{
  "name": "Animated layer",
  "animation": {
    "durationMs": 80,
    "frames": [
      "character-frame-01.png",
      { "file": "character-frame-02.png", "durationMs": 160 },
      "character-frame-03.png"
    ]
  }
}
```

`animation` belongs directly on the layer it animates, so animation requires a layered image.

| Field | Required | Default | Meaning |
| --- | --- | --- | --- |
| `durationMs` | no | none | Default display duration for each frame, in milliseconds |
| `frames` | yes | - | Ordered PNG filenames or frame objects |

Use a filename string when the frame uses the animation's default duration. Use a frame object only to override that duration:

| Field | Required | Default | Meaning |
| --- | --- | --- | --- |
| `file` | yes | - | PNG filename in this folder |
| `durationMs` | no | animation's `durationMs` | Display duration for this frame, in milliseconds |

Every frame must meet the same alpha and canvas-dimension requirements as a layer. `frames` cannot be empty, and every frame must resolve to a `durationMs` greater than zero from its own field or the animation default. A fileless animated layer uses its first frame's filename stem as its suggested label.

An implementation presents frames in array order. It begins with the first frame, holds each frame for its resolved duration, then repeats from the first frame. All animated layers begin at timeline time zero, so layers with different frame timings stay synchronized without needing a common frame rate.

To create an animation, put every full-canvas frame in the image folder and replace the changing layer's `file` entry with an `animation` object. Use a shared `durationMs` when every frame lasts equally, and frame objects only when a frame needs a different duration.

## Interlaced pairs

Interlaced artwork consists of two nearly identical pictures that the hardware alternates faster than the eye can separate them. The format carries both pictures, plus the composite they represent.

An image composed solely of an interlaced element can declare its group like this:

```json
{
  "name": "Image title",
  "author": "Artist name",
  "released": 2026,
  "layers": [
    {
      "file": "interlaced-intent.png",
      "role": "phaseIntent",
      "phaseGroup": "main"
    },
    {
      "file": "interlaced-phase-b.png",
      "role": "phaseB",
      "phaseGroup": "main"
    },
    {
      "file": "interlaced-phase-a.png",
      "role": "phaseA",
      "phaseGroup": "main"
    }
  ]
}
```

One `phaseIntent`, one `phaseA`, and one `phaseB` sharing a `phaseGroup` value form a group. The roles record that the three assets represent one interlaced element: `phaseIntent` is the intended composite, while `phaseA` and `phaseB` are its alternating source phases. The format declares this relationship but does not prescribe how an implementation presents it or the frequency it uses.

A phase role without `phaseGroup` is invalid. Multiple groups are allowed.

## Roles

The following roles are defined:

| Role | Meaning |
| --- | --- |
| `background` | First compositing layer; every later layer composites over it |
| `data` | Ordinary artwork layer |
| `overlay` | Annotation layer composited after every non-overlay layer |
| `sprite` | Artwork produced by hardware sprites; implies `hasSprites` |
| `phaseIntent` | The intended composite of an interlaced pair |
| `phaseA` | First alternating source phase |
| `phaseB` | Second alternating source phase |

## The first layer

`background` is reserved for the first entry and marks the usual fixed base. It needs neither `name` nor `description`, although both remain allowed. A `phaseIntent` may be first when an interlaced group is the whole image.

## Submission errors

An image folder is invalid for collection submission if any of the following apply:

- missing `name` or `author`
- a submitted image with a missing or non-JPEG `preview.jpg`
- malformed JSON
- unknown `role`
- a `background` role outside the first layer
- a phase role without `phaseGroup`
- an `animation` object with an empty `frames` array or a non-positive frame duration
- a layer with neither `file` nor `animation`
- a missing static-layer or animation-frame file
- an empty `layers` array
- `file` or `image` that does not resolve
- a filename containing `/` or `..`
- a PNG with partial alpha or canvas dimensions that differ from another asset in the folder

Implementations may report additional diagnostics, but they must not treat an unknown field or a display-program-specific PNG property as a defined format feature.
