# 📤 Гайд по загрузке на GitHub

## Шаг 1: Подготовка репозитория

### 1.1 Создай репозиторий на GitHub

1. Зайди на [github.com](https://github.com)
2. Нажми **+** → **New repository**
3. Заполни:
   - **Repository name:** `steam-launcher`
   - **Description:** "Steam Launcher — скрытый запуск с веб-интерфейсом"
   - **Visibility:** Public (или Private)
   - ✅ **Add a README file** — НЕ СТАВИТЬ!
   - ✅ **Add .gitignore** — НЕ СТАВИТЬ!
   - ✅ **Choose a license** — НЕ СТАВИТЬ!
4. Нажми **Create repository**

---

## Шаг 2: Подготовка файлов

### 2.1 Проверь структуру

Убедись что в папке `web/` есть:

```
web/
├── README.md          ← Создан автоматически
├── .gitignore         ← Создан автоматически
├── main.py
├── requirements.txt
├── steam.ico
├── scripts/
│   ├── вирус.bat
│   ├── не вирус.bat
│   ├── винлокер.bat
│   └── simulate.exe
├── templates/
│   └── index.html
└── static/
    ├── css/
    │   └── styles.css
    └── js/
        └── app.js
```

### 2.2 Что НЕ нужно загружать

❌ Не загружай эти папки/файлы:
- `__pycache__/`
- `logs/`
- `build/`
- `dist/`
- `*.spec`
- `.venv/`, `venv/`

---

## Шаг 3: Загрузка через Git

### 3.1 Установи Git

Скачай с [git-scm.com](https://git-scm.com/download/win)

### 3.2 Инициализация репозитория

```bash
cd "c:\Program Files (x86)\test\web"
git init
git branch -M main
git remote add origin https://github.com/neverjoskiy/steam-launcher.git
```

### 3.3 Добавление файлов

```bash
git add .
git commit -m "Initial commit: Steam Launcher v1.0"
```

### 3.4 Загрузка на GitHub

```bash
git push -u origin main
```

---

## Шаг 4: Загрузка через браузер (без Git)

### 4.1 Через GitHub Desktop (рекомендуется)

1. Скачай [GitHub Desktop](https://desktop.github.com)
2. Login через GitHub
3. **File** → **Add Local Repository** → Выбери папку `web`
4. **Publish repository**
5. Готово!

### 4.2 Через веб-интерфейс

1. Открой свой репозиторий на GitHub
2. Нажми **uploading an existing file**
3. Перетащи файлы из папки `web/` (кроме `logs/`, `build/`, `dist/`)
4. Напиши commit message: `Initial commit`
5. Нажми **Commit changes**

---

## Шаг 5: Создание релиза

### 5.1 Собери exe файл

```bash
cd "c:\Program Files (x86)\test\web"
pyinstaller --onefile --windowed ^
  --name "SteamLauncher" ^
  --icon=steam.ico ^
  --add-data "static;static" ^
  --add-data "templates;templates" ^
  --add-data "scripts;scripts" ^
  --hidden-import=uvicorn ^
  --hidden-import=fastapi ^
  --hidden-import=webview ^
  main.py
```

### 5.2 Создай архив

1. Создай папку `SteamLauncher_v1.0`
2. Скопируй в неё:
   - `dist/SteamLauncher.exe`
   - `scripts/вирус.bat`
   - `scripts/не вирус.bat`
   - `scripts/винлокер.bat`
   - `scripts/simulate.exe`
   - `steam.ico` (опционально)
3. Запакуй в ZIP: `SteamLauncher_v1.0.zip`

### 5.3 Опубликуй релиз

1. В репозитории перейди на вкладку **Releases**
2. Нажми **Draft a new release**
3. Заполни:
   - **Tag version:** `v1.0.0`
   - **Release title:** `Steam Launcher v1.0.0`
   - **Description:**
     ```markdown
     ## Что нового
     - ✨ Веб-интерфейс в тёмных тонах
     - 🛠️ Инструменты очистки
     - 📦 Портативная версия
     ```
4. Прикрепи файл `SteamLauncher_v1.0.zip` в **Attach binaries**
5. ✅ **Set as the latest release**
6. Нажми **Publish release**

---

## Шаг 6: Проверка

### 6.1 Проверь репозиторий

- ✅ README отображается
- ✅ Все файлы на месте
- ✅ .gitignore работает

### 6.2 Проверь релиз

- ✅ ZIP скачивается
- ✅ EXE запускается
- ✅ Инструменты работают

---

## 🔗 Полезные ссылки

- [Git для начинающих](https://git-scm.com/book/ru/v2)
- [GitHub Docs](https://docs.github.com/ru)
- [PyInstaller документация](https://pyinstaller.org/en/stable/)

---

## 📝 Шпаргалка команд Git

```bash
# Инициализация
git init
git add .
git commit -m "message"

# Ветки
git branch -M main
git checkout -b feature-name

# Push
git push -u origin main
git push origin feature-name

# Обновление
git pull origin main
git fetch --all
```

---

**Готово!** 🎉 Твой проект на GitHub!
