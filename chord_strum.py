#!/usr/bin/env python3
"""
chord_strum.py
================
Tạo file WAV âm thanh đệm guitar từ chuỗi hợp âm.

- Tổng hợp âm bằng thuật toán Karplus-Strong (mô phỏng dây đàn được gảy).
- Hỗ trợ pattern strum (xuống/lên/luân phiên).
- Pure Python: chỉ dùng stdlib (math, wave, struct, argparse, random).

Cách dùng:
    python chord_strum.py "C G Am F" -o song.wav
    python chord_strum.py "Em G D C" -o ballad.wav --bpm 80 --pattern D-DU-UDU
    python chord_strum.py --list-chords
"""

from __future__ import annotations

import argparse
import math
import random
import struct
import sys
import wave
from typing import List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Tham số chung
# ---------------------------------------------------------------------------
SAMPLE_RATE = 44100  # Hz, chuẩn CD
SAMPLE_WIDTH = 2     # 16-bit PCM

# Tần số các dây buông guitar (chuẩn EADGBE), từ dây 6 (trầm) -> dây 1 (cao)
# Index 0..5 = dây 6..1
OPEN_STRING_FREQS = [
    82.4069,    # E2 - dây 6
    110.0000,   # A2 - dây 5
    146.8324,   # D3 - dây 4
    195.9977,   # G3 - dây 3
    246.9417,   # B3 - dây 2
    329.6276,   # E4 - dây 1
]

# Bảng hợp âm phổ biến: (fret cho dây 6,5,4,3,2,1). None = dây không gảy (mute).
# Tham khảo voicing chuẩn cho người mới.
CHORD_SHAPES: dict[str, List[Optional[int]]] = {
    # Major
    "C":     [None, 3, 2, 0, 1, 0],
    "D":     [None, None, 0, 2, 3, 2],
    "E":     [0, 2, 2, 1, 0, 0],
    "F":     [1, 3, 3, 2, 1, 1],
    "G":     [3, 2, 0, 0, 0, 3],
    "A":     [None, 0, 2, 2, 2, 0],
    "B":     [None, 2, 4, 4, 4, 2],
    # Minor
    "Cm":    [None, 3, 5, 5, 4, 3],
    "Dm":    [None, None, 0, 2, 3, 1],
    "Em":    [0, 2, 2, 0, 0, 0],
    "Fm":    [1, 3, 3, 1, 1, 1],
    "Gm":    [3, 5, 5, 3, 3, 3],
    "Am":    [None, 0, 2, 2, 1, 0],
    "Bm":    [None, 2, 4, 4, 3, 2],
    # 7th
    "C7":    [None, 3, 2, 3, 1, 0],
    "D7":    [None, None, 0, 2, 1, 2],
    "E7":    [0, 2, 0, 1, 0, 0],
    "G7":    [3, 2, 0, 0, 0, 1],
    "A7":    [None, 0, 2, 0, 2, 0],
    "B7":    [None, 2, 1, 2, 0, 2],
    # Minor 7
    "Am7":   [None, 0, 2, 0, 1, 0],
    "Dm7":   [None, None, 0, 2, 1, 1],
    "Em7":   [0, 2, 2, 0, 3, 0],
    # Major 7
    "Cmaj7": [None, 3, 2, 0, 0, 0],
    "Dmaj7": [None, None, 0, 2, 2, 2],
    "Fmaj7": [None, None, 3, 2, 1, 0],
    "Gmaj7": [3, 2, 0, 0, 0, 2],
    "Amaj7": [None, 0, 2, 1, 2, 0],
    # sus
    "Dsus2": [None, None, 0, 2, 3, 0],
    "Dsus4": [None, None, 0, 2, 3, 3],
    "Asus2": [None, 0, 2, 2, 0, 0],
    "Asus4": [None, 0, 2, 2, 3, 0],
    "Esus4": [0, 2, 2, 2, 0, 0],
}


def fret_to_freq(string_index: int, fret: int) -> float:
    """Quy đổi (dây, ngăn phím) -> tần số (Hz). Mỗi fret = 1 nửa cung."""
    base = OPEN_STRING_FREQS[string_index]
    return base * (2.0 ** (fret / 12.0))


def get_chord_freqs(name: str) -> List[float]:
    """Trả về list tần số các dây được gảy của hợp âm (theo thứ tự dây 6 -> 1)."""
    if name not in CHORD_SHAPES:
        raise KeyError(
            f"Không nhận diện hợp âm '{name}'. Dùng --list-chords để xem danh sách."
        )
    shape = CHORD_SHAPES[name]
    freqs: List[float] = []
    for idx, fret in enumerate(shape):
        if fret is None:
            continue  # dây mute
        freqs.append(fret_to_freq(idx, fret))
    return freqs


# ---------------------------------------------------------------------------
# Karplus-Strong: tổng hợp 1 nốt giống dây guitar được gảy
# ---------------------------------------------------------------------------
def karplus_strong(
    freq: float,
    duration: float,
    sample_rate: int = SAMPLE_RATE,
    decay: float = 0.996,
    rng: Optional[random.Random] = None,
) -> List[float]:
    """Sinh waveform mô phỏng dây đàn rung từ tần số `freq` trong `duration` giây."""
    if rng is None:
        rng = random.Random()

    n_samples = int(duration * sample_rate)
    buffer_len = max(2, int(round(sample_rate / freq)))

    # Khởi tạo buffer = white noise [-1, 1]
    buf = [rng.uniform(-1.0, 1.0) for _ in range(buffer_len)]

    out = [0.0] * n_samples
    idx = 0
    for i in range(n_samples):
        cur = buf[idx]
        nxt = buf[(idx + 1) % buffer_len]
        # Low-pass filter trung bình + decay -> mô phỏng năng lượng giảm dần
        new_val = decay * 0.5 * (cur + nxt)
        buf[idx] = new_val
        out[i] = cur
        idx = (idx + 1) % buffer_len

    return out


def mix_into(target: List[float], src: Sequence[float], offset: int, gain: float) -> None:
    """Cộng dồn `src` vào `target` bắt đầu từ `offset`, có scale `gain`."""
    n = min(len(src), len(target) - offset)
    if n <= 0:
        return
    for i in range(n):
        target[offset + i] += src[i] * gain


# ---------------------------------------------------------------------------
# Strum: chơi 1 hợp âm với delay nhỏ giữa các dây để tạo cảm giác quẹt
# ---------------------------------------------------------------------------
def render_strum(
    target: List[float],
    chord: str,
    start_sample: int,
    duration: float,
    direction: str = "D",  # "D" = xuống (6->1), "U" = lên (1->6)
    velocity: float = 1.0,
    sample_rate: int = SAMPLE_RATE,
    rng: Optional[random.Random] = None,
) -> None:
    """Render 1 lần quẹt hợp âm vào buffer `target`."""
    freqs = get_chord_freqs(chord)
    if not freqs:
        return

    if direction == "U":
        freqs = list(reversed(freqs))
        # Quẹt lên thường nhẹ và nhanh hơn
        velocity *= 0.7
        strum_spread = 0.012
    else:
        strum_spread = 0.020

    per_string_delay = strum_spread / max(1, len(freqs) - 1)

    for i, f in enumerate(freqs):
        note = karplus_strong(f, duration, sample_rate=sample_rate, rng=rng)
        offset = start_sample + int(i * per_string_delay * sample_rate)
        # Dây trầm (vào trước khi quẹt xuống) hơi to hơn 1 chút
        gain = velocity * (0.85 + 0.05 * i if direction == "D" else 1.0 - 0.04 * i)
        mix_into(target, note, offset, gain)


# ---------------------------------------------------------------------------
# Pattern parser: chuỗi như "D-DU-UDU" thành các (beat_offset, direction)
# ---------------------------------------------------------------------------
def parse_pattern(pattern: str, beats_per_bar: int = 4) -> List[Tuple[float, str]]:
    """
    Mỗi ký tự = 1 nửa-phách (1/8 nốt):
      D = down strum, U = up strum, - hoặc . = nghỉ.
    Mặc định 8 ký tự = 1 ô nhịp 4/4.

    Trả về list (offset_tính_bằng_phách, direction).
    """
    pattern = pattern.strip()
    if not pattern:
        return [(0.0, "D")]

    half_beats_per_bar = beats_per_bar * 2
    events: List[Tuple[float, str]] = []
    for i, ch in enumerate(pattern):
        beat_offset = i / 2.0  # mỗi ký tự = 0.5 beat
        # Wrap nếu pattern dài hơn 1 ô nhịp -> không, ta tôn trọng pattern user nhập
        if ch in ("D", "d"):
            events.append((beat_offset, "D"))
        elif ch in ("U", "u"):
            events.append((beat_offset, "U"))
        elif ch in ("-", ".", " ", "_"):
            continue
        else:
            raise ValueError(f"Pattern ký tự không hợp lệ: '{ch}' (chỉ chấp nhận D/U/-)")

    if not events:
        events.append((0.0, "D"))
    return events


# ---------------------------------------------------------------------------
# Render toàn bộ bài
# ---------------------------------------------------------------------------
def render_song(
    chords: Sequence[str],
    bpm: float = 90.0,
    bars_per_chord: int = 1,
    beats_per_bar: int = 4,
    pattern: str = "D-DU-UDU",
    sample_rate: int = SAMPLE_RATE,
    seed: Optional[int] = None,
) -> List[float]:
    """Render đầy đủ chuỗi hợp âm thành buffer float [-1, 1]."""
    rng = random.Random(seed) if seed is not None else random.Random()

    sec_per_beat = 60.0 / bpm
    sec_per_bar = sec_per_beat * beats_per_bar
    sec_per_chord = sec_per_bar * bars_per_chord

    pattern_events = parse_pattern(pattern, beats_per_bar=beats_per_bar)
    pattern_len_beats = beats_per_bar * bars_per_chord  # độ dài 1 ô hợp âm tính bằng beat

    # Mỗi nốt được đánh sẽ rung lâu hơn 1 chút (sustain) so với khoảng giữa các đợt strum
    note_duration = max(sec_per_beat * 1.5, 0.8)

    total_seconds = sec_per_chord * len(chords) + 1.5  # +1.5s đuôi cho ring-out
    total_samples = int(total_seconds * sample_rate)
    buffer = [0.0] * total_samples

    for chord_index, chord_name in enumerate(chords):
        chord_start_sec = chord_index * sec_per_chord
        for beat_offset, direction in pattern_events:
            # Cho phép pattern dài hoặc ngắn hơn 1 ô — wrap quanh
            wrapped = beat_offset % pattern_len_beats
            t = chord_start_sec + wrapped * sec_per_beat
            start_sample = int(t * sample_rate)
            render_strum(
                buffer,
                chord_name,
                start_sample=start_sample,
                duration=note_duration,
                direction=direction,
                velocity=1.0,
                sample_rate=sample_rate,
                rng=rng,
            )

    return buffer


# ---------------------------------------------------------------------------
# Xuất WAV (16-bit PCM, mono)
# ---------------------------------------------------------------------------
def write_wav(path: str, samples: Sequence[float], sample_rate: int = SAMPLE_RATE) -> None:
    """Normalize về [-1, 1] và ghi ra file WAV 16-bit mono."""
    if not samples:
        raise ValueError("Buffer rỗng, không có gì để ghi.")

    peak = max(abs(s) for s in samples) or 1.0
    # Để 1 chút headroom, scale tới 0.95
    scale = 0.95 / peak

    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(sample_rate)
        # Pack thành int16
        frames = bytearray()
        for s in samples:
            v = max(-1.0, min(1.0, s * scale))
            frames += struct.pack("<h", int(v * 32767))
        wf.writeframes(bytes(frames))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Tạo file WAV đệm guitar từ chuỗi hợp âm (Karplus-Strong synthesis)."
    )
    p.add_argument(
        "chords",
        nargs="?",
        help='Chuỗi hợp âm cách nhau bởi space, vd: "C G Am F"',
    )
    p.add_argument("-o", "--output", default="output.wav", help="Tên file WAV output (default: output.wav)")
    p.add_argument("--bpm", type=float, default=90.0, help="Tempo (BPM), default 90")
    p.add_argument(
        "--bars-per-chord", type=int, default=1,
        help="Số ô nhịp cho mỗi hợp âm (default 1)",
    )
    p.add_argument(
        "--pattern", default="D-DU-UDU",
        help="Pattern strum, mỗi ký tự = 1/8 nốt. D=xuống, U=lên, -=nghỉ. Default 'D-DU-UDU'",
    )
    p.add_argument("--seed", type=int, default=None, help="Random seed (để tái tạo cùng âm thanh)")
    p.add_argument("--list-chords", action="store_true", help="Liệt kê danh sách hợp âm hỗ trợ")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_chords:
        names = sorted(CHORD_SHAPES.keys())
        print("Hợp âm hỗ trợ ({}):".format(len(names)))
        for i in range(0, len(names), 8):
            print("  " + "  ".join(f"{n:<7}" for n in names[i : i + 8]))
        return 0

    if not args.chords:
        parser.print_help()
        return 1

    chord_list = [c.strip() for c in args.chords.replace(",", " ").split() if c.strip()]
    if not chord_list:
        print("Cần ít nhất 1 hợp âm.", file=sys.stderr)
        return 1

    # Validate trước khi render
    unknown = [c for c in chord_list if c not in CHORD_SHAPES]
    if unknown:
        print("Hợp âm chưa hỗ trợ: " + ", ".join(unknown), file=sys.stderr)
        print("Dùng --list-chords để xem danh sách.", file=sys.stderr)
        return 2

    print(
        f"Render {len(chord_list)} hợp âm @ {args.bpm} BPM, "
        f"pattern='{args.pattern}', bars/chord={args.bars_per_chord}..."
    )
    samples = render_song(
        chord_list,
        bpm=args.bpm,
        bars_per_chord=args.bars_per_chord,
        pattern=args.pattern,
        seed=args.seed,
    )
    write_wav(args.output, samples)
    duration = len(samples) / SAMPLE_RATE
    print(f"OK -> {args.output} ({duration:.2f}s, {len(samples)} samples)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
