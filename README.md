# 🎸 Chord Strummer

Phần mềm tạo file đệm guitar từ chuỗi **hợp âm** đầu vào.

Có 2 cách dùng:

1. **Web app** (`index.html`) — mở trong trình duyệt là chạy ngay, không cần cài gì.
2. **Python CLI** (`chord_strum.py`) — chỉ dùng thư viện chuẩn, không cần `pip install`.

Cả hai đều dùng cùng thuật toán **Karplus-Strong** để mô phỏng dây đàn guitar được gảy.

---

## 1. Web app

Cách dùng:

```bash
# Cách đơn giản nhất: mở trực tiếp file
open index.html         # macOS
xdg-open index.html     # Linux
start index.html        # Windows

# Hoặc serve qua HTTP cho tiện:
python -m http.server 8000
# rồi truy cập http://localhost:8000/
```

Trong UI:

- Nhập chuỗi hợp âm vào ô trên cùng (vd: `C G Am F`).
- Chọn **BPM**, **số ô nhịp / hợp âm**, và **pattern strum**.
- Bấm **▶ Play** để nghe demo, **⬇ Tải WAV** để export file `.wav`.
- Click vào pill ở dưới để chèn nhanh hợp âm vào input.

---

## 2. Python CLI

```bash
# Tạo file WAV từ vòng hợp âm pop kinh điển
python chord_strum.py "C G Am F" -o pop.wav

# Tùy chỉnh tempo và pattern
python chord_strum.py "Em C G D" -o ballad.wav --bpm 75 --pattern "D---D---"

# Hợp âm dài 2 ô nhịp mỗi cái
python chord_strum.py "Am F C G" -o slow.wav --bars-per-chord 2

# Tái tạo cùng âm thanh với seed cố định
python chord_strum.py "C G Am F" -o demo.wav --seed 42

# Xem danh sách hợp âm hỗ trợ
python chord_strum.py --list-chords
```

### Cú pháp pattern strum

Mỗi ký tự = **1 nửa phách** (1/8 nốt):

| Ký tự | Ý nghĩa |
| ----- | ------- |
| `D`   | Quẹt **xuống** (down) |
| `U`   | Quẹt **lên** (up) |
| `-` `.` `_` | Nghỉ (không quẹt) |

Mặc định 8 ký tự = 1 ô nhịp 4/4. Ví dụ:

- `D-D-D-D-` → 4 cái xuống đều đặn (kiểu folk đơn giản)
- `D-DU-UDU` → pattern pop kinh điển
- `D---D---` → ballad chậm (1 cú quẹt mỗi 2 phách)
- `DUDUDUDU` → 16th note liên tục, sôi động

### Pattern fingerpicking (chỉ trên Web app)

Web app còn hỗ trợ gảy ngón thay vì strum:

- **Travis picking** — luân phiên bass (P) + ngón i, kiểu folk/country
- **Arpeggio P-I-M-A** — gảy lần lượt 4 dây, kiểu cổ điển
- **Ballad chậm** — bass + 3 dây cao đồng thời, mỗi 2 phách
- **Waltz 3/4** — P I M, hợp với nhịp 3/4

---

## Hợp âm hỗ trợ

33 voicing cho người mới: **Major, Minor, 7, m7, maj7, sus2, sus4** ở các phím phổ biến
(C, D, E, F, G, A, B và biến thể). Chạy `python chord_strum.py --list-chords` để xem đầy đủ.

Thêm hợp âm mới rất dễ — chỉ cần thêm vào `CHORD_SHAPES`:

```python
"E5":  [0, 2, 2, None, None, None],   # power chord E
```

Mỗi entry là 6 phần tử tương ứng dây 6 → dây 1 (E A D G B E).
Số = ngăn phím bấm, `None` = dây không gảy.

---

## Hoạt động bên trong

```
"C G Am F"
   ↓ parse hợp âm
   ↓ map shape → tần số 6 dây
   ↓ Karplus-Strong cho từng dây (mô phỏng vật lý dây rung + decay)
   ↓ delay nhỏ giữa các dây để tạo hiệu ứng strum
   ↓ lặp theo pattern và BPM
   ↓ normalize → WAV 16-bit mono 44.1 kHz
```

**Karplus-Strong** là kỹ thuật tổng hợp âm thanh kinh điển:
khởi tạo buffer bằng nhiễu trắng, sau đó lặp lại với low-pass filter và decay để mô phỏng năng
lượng dây đàn giảm dần — kết quả nghe rất giống guitar gảy.

---

## Cấu trúc dự án

```
music-test/
├── chord_strum.py    # CLI Python (pure stdlib)
├── index.html        # Web app standalone
└── README.md
```

Không có dependency nào. Pure Python stdlib + vanilla JavaScript.
