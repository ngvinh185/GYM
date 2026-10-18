# GymHeart

## 1. Cài đặt thư viện (backend)

Mở PowerShell tại thư mục gốc `gymvrs3`:

```powershell
gymvrs3\backend\.venv\Scripts\activate
pip install -r gymvrs3\backend\src\requirements.txt
```

> Nếu đang đứng trong `D:\gymvrs3` thì bỏ phần `gymvrs3\` ở đầu đường dẫn.

## 2. Chạy backend

```powershell
(.venv) (base) PS D:\gymvrs3\backend> cd .\src\
(.venv) (base) PS D:\gymvrs3\backend\src> py app.py
```

Backend chạy tại `http://localhost:8000`.

## 3. Chạy frontend

Mở một terminal khác, đứng ở thư mục gốc `gymvrs3`:

```powershell
(base) PS D:\gymvrs3> py -m http.server 5500
```

Mở trình duyệt tại `http://localhost:5500`.
