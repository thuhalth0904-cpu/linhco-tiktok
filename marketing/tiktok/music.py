"""Nhạc nền ngũ cung kiểu đàn tranh, soạn hoàn toàn bằng mã (không dùng nhạc có bản quyền).

Dùng: python music.py <giây> out.wav [seed]
"""
import sys
import numpy as np, wave

SR = 44100
DUR = float(sys.argv[1])
OUT = sys.argv[2]
SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 7
N = int(SR * DUR)
rng = np.random.default_rng(SEED)
out = np.zeros((N, 2))


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def add(sig, t0, pan=0.0, gain=1.0):
    i = int(t0 * SR)
    if i >= N:
        return
    sig = sig[: N - i] * gain
    l = np.cos((pan + 1) * np.pi / 4)
    r = np.sin((pan + 1) * np.pi / 4)
    out[i:i + len(sig), 0] += sig * l
    out[i:i + len(sig), 1] += sig * r


def pluck(m, dur=2.2, bright=1.0):
    t = np.arange(int(SR * dur)) / SR
    f = hz(m)
    env = np.exp(-t * 2.6) * (1 - np.exp(-t * 400))
    s = (np.sin(2 * np.pi * f * t) + 0.45 * bright * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 3)
         + 0.2 * bright * np.sin(2 * np.pi * 3.01 * f * t) * np.exp(-t * 5) + 0.08 * np.sin(2 * np.pi * 4.02 * f * t) * np.exp(-t * 8))
    return s * env


def pad(ms, dur):
    t = np.arange(int(SR * dur)) / SR
    s = np.zeros_like(t)
    for m in ms:
        for d in (-0.07, 0.0, 0.06):
            f = hz(m) * 2 ** (d / 12)
            s += np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) + 0.25 * np.sin(2 * np.pi * 2 * f * t)
    att = np.minimum(1, t / 0.9)
    rel = np.minimum(1, (dur - t) / 0.9)
    lfo = 0.85 + 0.15 * np.sin(2 * np.pi * 0.2 * t)
    return s * att * rel * lfo / (len(ms) * 3)


def bell(m, dur=4.0):
    t = np.arange(int(SR * dur)) / SR
    f = hz(m)
    s = sum(a * np.sin(2 * np.pi * f * k * t) * np.exp(-t * dcy) for k, a, dcy in [(1, 1, 1.2), (2.76, 0.5, 2.0), (5.4, 0.25, 3.5), (8.93, 0.12, 5)])
    return s * (1 - np.exp(-t * 300))


def swell(dur=1.0):
    n = int(SR * dur)
    x = rng.standard_normal(n)
    # simple one-pole low-pass sweep
    y = np.zeros(n)
    a = np.linspace(0.02, 0.25, n)
    for i in range(1, n):
        y[i] = y[i - 1] + a[i] * (x[i] - y[i - 1])
    env = np.sin(np.linspace(0, np.pi, n)) ** 2
    return y * env


# D minor pentatonic world. chords as midi lists (low register), change at scene cuts
D, F, G, A, C, Bb, E = 50, 53, 55, 57, 48, 46, 52
PROG = [[D, A, 62, 65], [Bb, 58, 62, 65], [F, 60, 65, 69], [C, 55, 60, 64], [D, 57, 62, 65], [Bb, 58, 62, 65], [C, 55, 60, 67], [D, 57, 62, 69]]
SEG = 3.2
chords = []
_t = 0.0
_k = 0
while _t < DUR:
    chords.append((_t, min(DUR, _t + SEG), PROG[_k % len(PROG)]))
    _t += SEG
    _k += 1
for s, e, ms in chords:
    add(pad(ms, e - s + 0.9), s - 0.0 if s == 0 else s - 0.45, 0, 0.22)
    add(pluck(ms[0] - 12, 3.5, 0.4), s, -0.1, 0.35)

# arpeggio + melody (guzheng-like), beat = 0.8s
beat = 0.8
scale = [62, 65, 67, 69, 72, 74, 77, 79, 81]
melody = [74, 72, 69, 67, 69, 72, 74, 77, 74, 72, 69, 72, 74, 69, 67, 65,
          67, 69, 72, 74, 77, 79, 77, 74, 72, 74, 69, 67, 65, 67, 69, 74, 72, 69, 67, 62, 62, 62, 62, 62]
for k in range(int(DUR / 0.8) + 2):
    t = 0.75 + k * beat
    if t > DUR - 2.0:
        break
    m = melody[k % len(melody)]
    if k % 4 == 3 and t < DUR - 5:
        add(pluck(m + 12, 1.2, 0.8), t + beat / 2, 0.35, 0.10)  # grace note
    add(pluck(m, 2.4, 1.0), t, rng.uniform(-0.3, 0.3), 0.30 if t < DUR - 5 else 0.24)
for s, e, ms in chords:
    for j in range(int((e - s) / (beat / 2))):
        t = s + j * beat / 2
        m = ms[1 + j % 3] + (12 if j % 6 >= 3 else 0)
        add(pluck(m, 1.0, 0.6), t + 0.02, -0.4 + 0.8 * ((j % 3) / 2), 0.07)

add(bell(74, 5), 0.05, 0, 0.30)
add(bell(62, 5), max(0.0, DUR - 5.0), 0, 0.30)
add(bell(69, 4), 29.0 - 3.5, 0.2, 0.0)
for t in []:
    add(swell(0.9), t - 0.6, 0, 0.05)

# reverb: FFT convolution with decaying stereo noise
irl = int(SR * 2.4)
ti = np.arange(irl) / SR
ir = np.stack([rng.standard_normal(irl), rng.standard_normal(irl)], 1) * np.exp(-ti * 2.6)[:, None]
ir[:int(SR * 0.012)] = 0
wet = np.zeros_like(out)
L = 1 << int(np.ceil(np.log2(N + irl)))
for c in range(2):
    wet[:, c] = np.fft.irfft(np.fft.rfft(out[:, c], L) * np.fft.rfft(ir[:, c], L), L)[:N]
wet /= np.max(np.abs(wet)) + 1e-9
dry = out / (np.max(np.abs(out)) + 1e-9)
mix = 0.72 * dry + 0.38 * wet
t = np.arange(N) / SR
mix *= np.minimum(1, t / 0.15)[:, None] * np.minimum(1, (DUR - t) / 1.8)[:, None]
mix /= np.max(np.abs(mix)) * 1.12
with wave.open(OUT, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((mix * 32767).astype("<i2").tobytes())
print("ok")
