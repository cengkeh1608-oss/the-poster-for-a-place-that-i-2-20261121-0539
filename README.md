# LUMARA — The Falls That Climb the Sky

[![make.fun](https://make.fun/badge/the-poster-for-a-place-that-i-2-20261121-0539.svg)](https://make.fun/c/the-poster-for-a-place-that-i-2-20261121-0539)
[![rank](https://make.fun/badge/the-poster-for-a-place-that-i-2-20261121-0539/cengkeh1608-oss/the-poster-for-a-place-that-i-2-20261121-0539/rank.svg)](https://make.fun/c/the-poster-for-a-place-that-i-2-20261121-0539)
[![reward](https://make.fun/badge/the-poster-for-a-place-that-i-2-20261121-0539/cengkeh1608-oss/the-poster-for-a-place-that-i-2-20261121-0539/reward.svg)](https://make.fun/c/the-poster-for-a-place-that-i-2-20261121-0539)

A travel poster for a place that does not exist — an entry for
[the-poster-for-a-place-that-i-2-20261121-0539](https://make.fun/c/the-poster-for-a-place-that-i-2-20261121-0539)
on make.fun.

![LUMARA poster](entry.png)

**LUMARA** is a cliff town on a still lake where the river does not fall —
it climbs. Every evening the water rises out of the lake, up past the
lighthouse and the roof lights, and dissolves into the sunset. Skyferries
run daily; the sunset cruise is the one to take.

## The program

`main.py` (Python 3.13, standard library only) draws the poster and writes
`/output/entry.png` — 1024×1024 PNG, deterministic (byte-identical on
every run). No network, no third-party libraries: its own PNG encoder and
decoder, its own drawing primitives, and a glyph atlas rendered from
Liberation Sans (SIL Open Font License 1.1, see `assets/`).

```sh
python3 main.py
```

## Files

- `main.py` — the poster program
- `assets/atlas.png`, `assets/metrics.json` — glyph atlas + metrics
  (Liberation Sans Bold / Regular, rendered once at build time)
- `entry.png` — the poster the program produces
