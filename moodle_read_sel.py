from playwright.sync_api import sync_playwright, Page, Browser, TimeoutError as PlaywrightTimeout
from datetime import datetime
import json
from time import sleep
import os
import re
from typing import Optional, List


class Deadline:
    """Структура данных для хранения информации о дедлайне"""
    
    def __init__(self, title: str, course: str, due_date: str, source: str):
        self.title = title
        self.course = course
        self.due_date = due_date
        self.source = source
    
    def __str__(self):
        source_icon = "[LMS]" if self.source == "lms" else "[OE]"
        return f"{source_icon} {self.course} | {self.title} | {self.due_date}"
    
    def to_dict(self):
        return {
            "title": self.title,
            "course": self.course,
            "due_date": self.due_date,
            "source": self.source
        }


class MoodleDeadlineParser:
    """Парсер дедлайнов для LMS СПбПУ и Openedu на Playwright"""
    
    def __init__(self, username: str, password: str, browser_type: str = "chromium", 
                 headless: bool = False, chrome_profile: str = ""):
        self.username = username
        self.password = password
        self.browser_type = browser_type
        self.headless = headless
        self.chrome_profile = chrome_profile
        self.deadlines: List[Deadline] = []
        
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        
        self.default_timeout = 30000
        self.navigation_timeout = 60000
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False
        
    def init_browser(self):
        """Инициализация Playwright с системным браузером"""
        self.playwright = sync_playwright().start()
        
        browser_launcher = getattr(self.playwright, self.browser_type)
        
        mode_str = "фоновом" if self.headless else "обычном"
        print(f"[INFO] Запуск {self.browser_type.upper()} в {mode_str} режиме...")
        
        # Аргументы для обхода проблем на macOS
        args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-software-rasterizer",
        ]
        
        # Для macOS ARM64 добавляем дополнительные флаги
        if os.name == "posix":
            args.extend([
                "--disable-setuid-sandbox",
                "--no-zygote",
            ])
        
        launch_options = {
            "headless": self.headless,
            "args": args,
        }
        
        # Пытаемся найти системный Chrome
        if self.browser_type == "chromium":
            system_chrome_paths = [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Chromium.app/Contents/MacOS/Chromium",
            ]
            
            for chrome_path in system_chrome_paths:
                if os.path.exists(chrome_path):
                    launch_options["executable_path"] = chrome_path
                    print(f"[INFO] Используется системный Chrome: {chrome_path}")
                    break
        
        self.browser = browser_launcher.launch(**launch_options)
        
        self.context = self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="ru-RU",
            timezone_id="Europe/Moscow",
        )
        
        self.page = self.context.new_page()
        self.page.set_default_timeout(self.default_timeout)
        
    def cleanup(self):
        """Закрытие ресурсов"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        print("[INFO] Браузер закрыт")
    
    def login_lms(self) -> bool:
        """Вход в LMS СПбПУ"""
        print("\n" + "=" * 50)
        print("[AUTH] ВХОД В LMS СПбПУ")
        print("=" * 50)
        
        try:
            print("[INFO] Переход на страницу входа...")
            self.page.goto('https://lms.spbstu.ru/login/index.php', 
                          wait_until="domcontentloaded", 
                          timeout=self.navigation_timeout)
            sleep(2)
            
            try:
                sso_locator = self.page.locator("//*[contains(text(), 'единой записи СПБПУ')]").first
                if sso_locator.count() > 0:
                    sso_locator.locator("xpath=..").click(timeout=5000)
                    print("[OK] Нажата кнопка входа по единой записи СПБПУ")
                else:
                    self.page.locator("div.auth0-lock-social-button-text").first.click(timeout=5000)
                    print("[OK] Нажата кнопка входа (по классу)")
            except Exception as e:
                print(f"[WARN] Не удалось найти кнопку SSO: {e}")
            
            sleep(3)
            
            print("[INFO] Заполнение формы входа...")
            
            self.page.wait_for_selector("#user", timeout=10000)
            self.page.fill("#user", self.username)
            print("[OK] Логин введен")
            
            self.page.fill("#password", self.password)
            print("[OK] Пароль введен")
            
            with self.page.expect_navigation(timeout=30000):
                self.page.click("#doLogin")
            print("[OK] Кнопка Войти нажата")
            
            sleep(5)
            
            current_url = self.page.url
            if "lms.spbstu.ru" in current_url and "login" not in current_url.lower():
                print("[OK] Вход в LMS выполнен успешно")
                return True
            else:
                print(f"[WARN] Возможно, вход не удался. Текущий URL: {current_url}")
                return False
                
        except PlaywrightTimeout as e:
            print(f"[ERROR] Таймаут при входе в LMS: {e}")
            return False
        except Exception as e:
            print(f"[ERROR] Ошибка при входе в LMS: {e}")
            if self.page:
                self.page.screenshot(path="lms_login_error.png")
            return False
    
    def login_openedu(self) -> bool:
        """Вход в Openedu через учетную запись СПбПУ"""
        print("\n" + "=" * 50)
        print("[AUTH] ВХОД В OPENEDU")
        print("=" * 50)
        
        try:
            print("[INFO] Переход на страницу входа Openedu...")
            auth_url = 'https://sso.openedu.ru/realms/openedu/protocol/openid-connect/auth?client_id=plp&redirect_uri=https://openedu.ru/auth/complete/npoedsso/&state=kJVuDiqO1d3hJkl4aUdhkEnxEW34utAY&response_type=code&nonce=9uswzIVCibPRLfD7mQpKaclt3tq9tjczzRVhC5GYeLPWm2ule630aMpzUqadrxp0&scope=openid+profile+email'
            self.page.goto(auth_url, wait_until="domcontentloaded", timeout=self.navigation_timeout)
            sleep(3)
            
            polytech_clicked = False
            strategies = [
                ("CSS + текст", lambda: self.page.locator("span.social-form__label:has-text('Политех')").first),
                ("XPath по тексту", lambda: self.page.locator("xpath=//span[contains(text(), 'Политех')]/ancestor::a").first),
                ("XPath по href", lambda: self.page.locator("xpath=//a[contains(@href, 'spbstu')]").first),
            ]
            
            for strategy_name, locator_func in strategies:
                try:
                    locator = locator_func()
                    if locator.count() > 0 and locator.is_visible(timeout=3000):
                        with self.page.expect_navigation(timeout=30000, wait_until="domcontentloaded"):
                            locator.click(timeout=5000)
                        print(f"[OK] Нажата кнопка входа через СПбПУ ({strategy_name})")
                        polytech_clicked = True
                        break
                except:
                    continue
            
            if not polytech_clicked:
                print("[WARN] Не удалось найти кнопку Политех")
                if self.page:
                    self.page.screenshot(path="openedu_sso_not_found.png")
            
            sleep(3)
            
            if "openedu.ru" in self.page.url:
                print("[OK] Автоматический вход выполнен")
                return True
            
            print("[INFO] Проверка необходимости ввода логина/пароля...")
            
            try:
                if self.page.is_visible("#user", timeout=5000):
                    current_value = self.page.input_value("#user", timeout=2000)
                    if not current_value:
                        self.page.fill("#user", self.username)
                        print("[OK] Логин введен")
                    else:
                        print("[OK] Логин уже заполнен")
                    
                    if not self.page.input_value("#password", timeout=2000):
                        self.page.fill("#password", self.password)
                        print("[OK] Пароль введен")
                    else:
                        print("[OK] Пароль уже заполнен")
                    
                    if self.page.is_enabled("#doLogin"):
                        sleep(1)
                        with self.page.expect_navigation(timeout=30000, wait_until="domcontentloaded"):
                            self.page.click("#doLogin")
                        print("[OK] Кнопка Войти нажата")
                        
            except PlaywrightTimeout:
                print("[OK] Поле логина не найдено - предположительно автоматический вход")
            except Exception as e:
                print(f"[WARN] Нестандартная ситуация: {e}")
            
            print("[INFO] Ожидание завершения входа...")
            sleep(8)
            
            if "openedu.ru" in self.page.url:
                print("[OK] Вход в Openedu выполнен успешно")
                return True
            else:
                sleep(5)
                if "openedu.ru" in self.page.url:
                    print("[OK] Вход подтвержден после паузы")
                    return True
                return False
                
        except Exception as e:
            print(f"[ERROR] Ошибка при входе в Openedu: {e}")
            if self.page:
                self.page.screenshot(path="openedu_login_error.png")
            return False
    
    def parse_lms_deadlines(self) -> List[Deadline]:
        """Парсит дедлайны с LMS СПбПУ"""
        deadlines = []
        pages = ['/my/', '/calendar/view.php?view=upcoming']
        
        for page_path in pages:
            try:
                url = f"https://lms.spbstu.ru{page_path}"
                print(f"[INFO] Парсинг LMS: {url}")
                self.page.goto(url, wait_until="domcontentloaded", timeout=self.navigation_timeout)
                sleep(3)
                
                events = self.page.locator(".event").all()
                
                for event in events:
                    try:
                        title = event.locator(".event-name").text_content(timeout=2000)
                        course = event.locator(".course-name").text_content(timeout=2000)
                        date = event.locator(".date").text_content(timeout=2000)
                        
                        if title and course and date:
                            deadline = Deadline(title.strip(), course.strip(), date.strip(), "lms")
                            deadlines.append(deadline)
                    except:
                        continue
                        
            except Exception as e:
                print(f"[WARN] Ошибка при парсинге {page_path}: {e}")
        
        return deadlines
    
    def parse_openedu_deadlines(self) -> List[Deadline]:
        """Парсит дедлайны с Openedu"""
        deadlines = []
        courses_url = 'https://openedu.ru/my/courses/'
        
        try:
            print("\n[INFO] Переход к моим курсам...")
            self.page.goto(courses_url, wait_until="networkidle", timeout=self.navigation_timeout)
            sleep(5)
            
            if "login" in self.page.url or "auth" in self.page.url:
                print("[WARN] Требуется авторизация...")
                if not self.login_openedu():
                    return deadlines
                self.page.goto(courses_url, wait_until="networkidle", timeout=self.navigation_timeout)
                sleep(5)
            
            print("[INFO] Поиск курсов...")
            try:
                self.page.wait_for_selector("div.ed-product-card", timeout=20000)
                print("[OK] Карточки курсов загружены")
            except PlaywrightTimeout:
                print("[WARN] Карточки не загрузились")
                if self.page:
                    self.page.screenshot(path="openedu_no_courses.png")
                return deadlines
            
            course_cards = self.page.locator("div.ed-product-card").all()
            print(f"[INFO] Найдено курсов: {len(course_cards)}")
            
            course_titles = []
            for card in course_cards:
                try:
                    title_elem = card.locator("div.ed-product-card__header__title span")
                    title = title_elem.text_content(timeout=3000)
                    title = title.strip() if title else f"Курс {len(course_titles)+1}"
                    course_titles.append(title)
                except:
                    course_titles.append(f"Курс {len(course_titles)+1}")
            
            for idx, course_title in enumerate(course_titles, 1):
                print(f"\n[INFO] Курс {idx}/{len(course_titles)}: {course_title[:50]}...")
                
                try:
                    course_buttons = self.page.locator("//*[contains(text(), 'К материалам курса')]").all()
                    if idx > len(course_buttons):
                        print(f"[WARN] Кнопка не найдена для курса {idx}")
                        continue
                    
                    button = course_buttons[idx - 1]
                    button.scroll_into_view_if_needed(timeout=5000)
                    sleep(2)
                    
                    try:
                        button.click(timeout=5000)
                    except:
                        try:
                            handle = button.element_handle(timeout=3000)
                            self.page.evaluate("el => el.click()", handle)
                        except Exception as e:
                            print(f"[WARN] Не удалось кликнуть: {e}")
                            continue
                    
                    sleep(5)
                    
                    schedule_selectors = [
                        "a.nav-link:has-text('Расписание курса')",
                        "a:has-text('Расписание')",
                        "a[href*='dates']",
                        "a.nav-link[href*='static_tab']"
                    ]
                    
                    schedule_clicked = False
                    for selector in schedule_selectors:
                        try:
                            link = self.page.locator(selector).first
                            if link.is_visible(timeout=3000):
                                link.click(timeout=5000)
                                print("[OK] Перешли в расписание")
                                schedule_clicked = True
                                break
                        except:
                            continue
                    
                    if not schedule_clicked:
                        print("[WARN] Расписание не найдено")
                        self.page.goto(courses_url)
                        sleep(3)
                        continue
                    
                    sleep(5)
                    
                    deadlines.extend(self._parse_schedule_table(course_title))
                    
                    self.page.goto(courses_url, wait_until="domcontentloaded")
                    sleep(3)
                    
                except Exception as e:
                    print(f"[WARN] Ошибка обработки курса: {e}")
                    self.page.goto(courses_url)
                    sleep(3)
                    continue
            
            print(f"\n[INFO] Найдено дедлайнов Openedu: {len(deadlines)}")
            
        except Exception as e:
            print(f"[ERROR] Ошибка парсинга Openedu: {e}")
            if self.page:
                self.page.screenshot(path="openedu_parse_error.png")
        
        return deadlines
    
    def _parse_schedule_table(self, course_title: str) -> List[Deadline]:
        """Вспомогательный метод парсинга таблицы расписания"""
        deadlines = []
        
        try:
            self.page.wait_for_selector("table", timeout=15000)
            tables = self.page.locator("table").all()
            
            for table in tables:
                rows = table.locator("tr").all()
                if len(rows) < 2:
                    continue
                
                rowspan_tracker = {}
                
                for row_idx, row in enumerate(rows):
                    if row_idx == 0:
                        continue
                    
                    cells = row.locator("td").all()
                    if not cells:
                        continue
                    
                    def get_cell_text(cell) -> str:
                        try:
                            text = cell.text_content(timeout=2000)
                            return text.strip() if text else ""
                        except:
                            return ""
                    
                    title = get_cell_text(cells[0])
                    if not title:
                        continue
                    
                    date_text = None
                    for cell in reversed(cells):
                        text = get_cell_text(cell)
                        if text and '.' in text:
                            date_text = text
                            break
                    
                    if not date_text or date_text in ['-', '—'] or 'инд.' in date_text.lower():
                        continue
                    
                    try:
                        if '.' in date_text:
                            parts = date_text.split('.')
                            if len(parts) >= 2:
                                day = parts[0].strip().zfill(2)
                                month = parts[1].strip().zfill(2)
                                
                                if len(parts) >= 3 and parts[2].strip():
                                    year = parts[2].strip()
                                    if len(year) == 2:
                                        year = f"20{year}"
                                    elif len(year) != 4:
                                        year = "2026"
                                else:
                                    year = "2026"
                                
                                if day.isdigit() and month.isdigit() and year.isdigit():
                                    formatted_date = f"{year}-{month}-{day}"
                                    deadlines.append(Deadline(
                                        title=f"{course_title}: {title}",
                                        course=course_title,
                                        due_date=formatted_date,
                                        source="openedu"
                                    ))
                    except Exception as e:
                        print(f"[WARN] Ошибка парсинга даты '{date_text}': {e}")
                        continue
                
        except Exception as e:
            print(f"[WARN] Ошибка парсинга таблицы: {e}")
        
        return deadlines
    
    def print_deadlines(self, deadlines: List[Deadline], source_name: str):
        """Вывод дедлайнов в консоль"""
        if not deadlines:
            print(f"\n[INFO] Дедлайнов в {source_name} не найдено")
            return
        
        print("\n" + "=" * 60)
        print(f"[LIST] {source_name.upper()}: {len(deadlines)} дедлайнов")
        print("=" * 60)
        
        sorted_deadlines = sorted(deadlines, key=lambda x: x.due_date)
        
        for i, deadline in enumerate(sorted_deadlines, 1):
            print(f"{i}. {deadline}")
    
    def save_all_deadlines(self):
        """Сохраняет все дедлайны в JSON"""
        if not self.deadlines:
            print("[INFO] Нет данных для сохранения")
            return
        
        os.makedirs("data", exist_ok=True)
        
        filename = f"data/deadlines_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        data = [d.to_dict() for d in self.deadlines]
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n[SAVE] Данные сохранены в {filename}")
    
    def show_menu(self) -> str:
        """Показывает меню"""
        print("\n" + "=" * 60)
        print("[MENU] ПАРСЕР ДЕДЛАЙНОВ (Playwright)")
        print("=" * 60)
        print(f"Браузер: {self.browser_type.upper()} | Режим: {'Headless' if self.headless else 'Visible'}")
        print("-" * 60)
        print("1. Получить дедлайны из LMS СПбПУ")
        print("2. Получить дедлайны из Openedu")
        print("3. Получить из обоих источников")
        print("4. Настройки")
        print("5. Выйти")
        print("-" * 60)
        return input("Выберите действие (1-5): ").strip()
    
    def show_settings(self):
        """Меню настроек"""
        while True:
            print("\n" + "=" * 60)
            print("[SETTINGS] НАСТРОЙКИ")
            print("=" * 60)
            print(f"1. Браузер: {self.browser_type} (chromium/firefox/webkit)")
            print(f"2. Режим отображения: {'headless' if self.headless else 'visible'}")
            print("3. Вернуться в главное меню")
            print("-" * 60)
            
            choice = input("Выберите действие (1-3): ").strip()
            
            if choice == '1':
                browsers = ['chromium', 'firefox', 'webkit']
                print(f"Доступные браузеры: {', '.join(browsers)}")
                new_browser = input("Введите название браузера: ").strip().lower()
                if new_browser in browsers:
                    self.browser_type = new_browser
                    print(f"[OK] Браузер изменен на {new_browser}")
                else:
                    print("[ERROR] Неверное название браузера")
            elif choice == '2':
                self.headless = not self.headless
                mode = "headless" if self.headless else "visible"
                print(f"[OK] Режим изменен на {mode}")
            elif choice == '3':
                break
            else:
                print("[ERROR] Неверный выбор")
    
    def run(self):
        """Основной метод запуска с меню"""
        while True:
            choice = self.show_menu()
            
            if choice == '5':
                print("\n[EXIT] Завершение работы")
                break
            
            if choice == '4':
                self.show_settings()
                continue
            
            if choice not in ['1', '2', '3']:
                print("\n[ERROR] Неверный выбор. Попробуйте снова.")
                continue
            
            self.init_browser()
            self.deadlines = []
            
            try:
                if choice == '1':
                    if self.login_lms():
                        print("\n[PARSE] Поиск дедлайнов в LMS...")
                        lms_deadlines = self.parse_lms_deadlines()
                        self.deadlines.extend(lms_deadlines)
                        self.print_deadlines(lms_deadlines, "LMS СПбПУ")
                
                elif choice == '2':
                    if self.login_openedu():
                        print("\n[PARSE] Поиск дедлайнов в Openedu...")
                        openedu_deadlines = self.parse_openedu_deadlines()
                        self.deadlines.extend(openedu_deadlines)
                        self.print_deadlines(openedu_deadlines, "Openedu")
                
                elif choice == '3':
                    if self.login_lms():
                        print("\n[PARSE] Поиск дедлайнов в LMS...")
                        lms_deadlines = self.parse_lms_deadlines()
                        self.deadlines.extend(lms_deadlines)
                        self.print_deadlines(lms_deadlines, "LMS СПбПУ")
                    
                    if self.login_openedu():
                        print("\n[PARSE] Поиск дедлайнов в Openedu...")
                        openedu_deadlines = self.parse_openedu_deadlines()
                        self.deadlines.extend(openedu_deadlines)
                        self.print_deadlines(openedu_deadlines, "Openedu")
                
                if self.deadlines:
                    self.save_all_deadlines()
                
            except KeyboardInterrupt:
                print("\n[WARN] Прервано пользователем")
            except Exception as e:
                print(f"\n[ERROR] Критическая ошибка: {e}")
            finally:
                self.cleanup()
            
            print("\n" + "-" * 60)
            input("Нажмите Enter, чтобы продолжить...")


def load_credentials(filepath: str = "misc/credentials.json") -> dict:
    """Загрузка учетных данных из файла"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] Файл {filepath} не найден")
        print("Создайте файл со следующей структурой:")
        print(json.dumps({
            "moodle": {
                "username": "your.email@edu.spbstu.ru",
                "password": "your_password"
            },
            "chrome": {
                "chrome_profile": ""
            }
        }, indent=4, ensure_ascii=False))
        exit(1)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Ошибка парсинга JSON: {e}")
        exit(1)


if __name__ == "__main__":
    creds = load_credentials()
    
    browser_type = os.getenv("BROWSER", "chromium").lower()
    headless = os.getenv("HEADLESS", "false").lower() == "true"
    
    with MoodleDeadlineParser(
        username=creds['moodle']['username'],
        password=creds['moodle']['password'],
        chrome_profile=creds.get('chrome', {}).get('chrome_profile', ''),
        browser_type=browser_type,
        headless=headless
    ) as parser:
        parser.run()