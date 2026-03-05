from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import json
from time import sleep
from datetime import datetime
import os

class Deadline:
    """Структура данных для хранения информации о дедлайне"""
    def __init__(self, title: str, course: str, due_date: str, source: str):
        self.title = title      # Название задания
        self.course = course    # Название курса
        self.due_date = due_date  # Дата дедлайна в формате YYYY-MM-DD
        self.source = source    # Источник: "lms" или "openedu"
    
    def __str__(self):
        icon = "🎓" if self.source == "lms" else "🌐"
        return f"{icon} {self.course} | 📝 {self.title} | 📅 {self.due_date}"
    
    def to_dict(self):
        return {
            "title": self.title,
            "course": self.course,
            "due_date": self.due_date,
            "source": self.source
        }


class MoodleDeadlineParser:
    def __init__(self, username, password, chrome_profile=""):
        self.username = username
        self.password = password
        self.chrome_profile = chrome_profile
        self.deadlines = []  # Массив структур Deadline
        self.driver = None
    
    def init_driver(self):
        """Инициализация драйвера Chrome"""
        options = webdriver.ChromeOptions()
        if self.chrome_profile:
            options.add_argument(f"user-data-dir={self.chrome_profile}")
        options.add_argument("--no-proxy-server")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-infobars")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--remote-allow-origins=*")
        
        print("🟢 Запуск браузера...")
        self.driver = webdriver.Chrome(options=options)
        self.driver.implicitly_wait(10)
    
    def login_lms(self) -> bool:
        """Вход в LMS СПбПУ"""
        print("\n" + "="*50)
        print("🔐 ВХОД В LMS СПбПУ")
        print("="*50)
        
        try:
            print("🌐 Переход на страницу входа...")
            self.driver.get('https://lms.spbstu.ru/login/index.php')
            sleep(2)
            
            # Ищем и нажимаем кнопку единого входа
            try:
                sso_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'единой записи СПБПУ')]")
                if sso_elements:
                    sso_elements[0].find_element(By.XPATH, "..").click()
                    print("✅ Нажата кнопка 'Вход по единой записи СПБПУ'")
                else:
                    sso_button = self.driver.find_element(By.CSS_SELECTOR, "div.auth0-lock-social-button-text")
                    sso_button.find_element(By.XPATH, "..").click()
                    print("✅ Нажата кнопка входа (по классу)")
            except Exception as e:
                print(f"⚠️ Не удалось найти кнопку SSO: {e}")
            
            sleep(3)
            
            # Заполняем форму входа
            print("🔑 Заполнение формы входа...")
            
            login_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "user"))
            )
            login_field.clear()
            login_field.send_keys(self.username)
            print("✅ Логин введен")
            
            password_field = self.driver.find_element(By.ID, "password")
            password_field.clear()
            password_field.send_keys(self.password)
            print("✅ Пароль введен")
            
            login_button = self.driver.find_element(By.ID, "doLogin")
            login_button.click()
            print("✅ Кнопка 'Войти' нажата")
            
            sleep(5)
            
            current_url = self.driver.current_url
            if "lms.spbstu.ru" in current_url and "login" not in current_url.lower():
                print("✅ Вход в LMS выполнен успешно!")
                return True
            else:
                print(f"⚠️ Возможно, вход не удался. Текущий URL: {current_url}")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка при входе в LMS: {e}")
            return False
    
    def login_openedu(self) -> bool:
        """Вход в Openedu через учетную запись СПбПУ"""
        print("\n" + "="*50)
        print("🔐 ВХОД В OPENEDU")
        print("="*50)
        
        try:
            print("🌐 Переход на страницу входа Openedu...")
            self.driver.get('https://sso.openedu.ru/realms/openedu/protocol/openid-connect/auth?client_id=plp&redirect_uri=https://openedu.ru/auth/complete/npoedsso/&state=kJVuDiqO1d3hJkl4aUdhkEnxEW34utAY&response_type=code&nonce=9uswzIVCibPRLfD7mQpKaclt3tq9tjczzRVhC5GYeLPWm2ule630aMpzUqadrxp0&scope=openid+profile+email')
            sleep(3)
            
            # Ищем кнопку "Политех" для входа через СПбПУ
            try:
                # Ищем по точному классу и тексту
                polytech_span = self.driver.find_element(By.CSS_SELECTOR, "span.social-form__label")
                if "Политех" in polytech_span.text:
                    # Поднимаемся к родительской ссылке
                    polytech_link = polytech_span.find_element(By.XPATH, "../..")
                    polytech_link.click()
                    print("✅ Нажата кнопка 'Политех'")
                else:
                    raise Exception("Текст не совпадает")
                    
            except Exception as e:
                try:
                    # Запасной вариант: ищем по тексту
                    polytech_link = self.driver.find_element(By.XPATH, "//span[contains(text(), 'Политех')]/ancestor::a")
                    polytech_link.click()
                    print("✅ Нажата кнопка входа через СПбПУ (по тексту)")
                    
                except Exception as e:
                    try:
                        # Еще один запасной вариант: ищем по ссылке
                        polytech_link = self.driver.find_element(By.XPATH, "//a[contains(@href, 'spbstu')]")
                        polytech_link.click()
                        print("✅ Нажата кнопка входа через СПбПУ (по ссылке)")
                        
                    except Exception as e:
                        print(f"⚠️ Не удалось найти кнопку Политех: {e}")
                        # Сохраняем скриншот для отладки
                        self.driver.save_screenshot("openedu_sso_not_found.png")
                        # Возможно, мы уже на странице входа? Продолжаем выполнение
                        pass

            sleep(3)
            
            # Проверяем, не перенаправило ли нас после нажатия кнопки
            current_url = self.driver.current_url
            if "openedu.ru" in current_url:
                print("✅ Автоматический вход выполнен!")
                return True
            
            # Теперь мы на странице входа СПбПУ (возможно, с уже заполненными полями)
            print("🔑 Проверка необходимости ввода логина/пароля...")
            
            try:
                # Проверяем, есть ли поле логина (если нет - возможно авто-вход)
                login_field = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.ID, "user"))
                )
                
                # Если поле логина пустое, заполняем
                current_value = login_field.get_attribute("value")
                if not current_value:
                    login_field.clear()
                    login_field.send_keys(self.username)
                    print("✅ Логин введен")
                else:
                    print("✅ Логин уже заполнен")
                
                # Поле пароля
                password_field = self.driver.find_element(By.ID, "password")
                current_password = password_field.get_attribute("value")
                if not current_password:
                    password_field.clear()
                    password_field.send_keys(self.password)
                    print("✅ Пароль введен")
                else:
                    print("✅ Пароль уже заполнен")
                
                # Кнопка входа
                login_button = self.driver.find_element(By.ID, "doLogin")
                
                # Проверяем, активна ли кнопка и нужно ли нажимать
                if login_button.is_enabled():
                    # Делаем небольшую паузу перед нажатием
                    sleep(1)
                    login_button.click()
                    print("✅ Кнопка 'Войти' нажата")
                else:
                    print("⏳ Кнопка 'Войти' неактивна, возможно авто-вход")
                
            except TimeoutException:
                # Если поле логина не найдено, значит произошел авто-вход
                print("✅ Поле логина не найдено - предположительно автоматический вход")
                pass
            except Exception as e:
                print(f"⚠️ Нестандартная ситуация при заполнении формы: {e}")
            
            # Ждем завершения входа
            print("⏳ Ожидание завершения входа...")
            sleep(8)
            
            # Проверяем успешность входа
            current_url = self.driver.current_url
            if "openedu.ru" in current_url:
                print("✅ Вход в Openedu выполнен успешно!")
                return True
            else:
                print(f"⚠️ Текущий URL после входа: {current_url}")
                # Делаем дополнительную паузу и проверяем еще раз
                sleep(5)
                current_url = self.driver.current_url
                if "openedu.ru" in current_url:
                    print("✅ Вход в Openedu подтвержден после паузы!")
                    return True
                return False
                
        except Exception as e:
            print(f"❌ Ошибка при входе в Openedu: {e}")
            self.driver.save_screenshot("openedu_login_error.png")
            return False
    
    def parse_lms_deadlines(self) -> list:
        """Парсит дедлайны с LMS СПбПУ"""
        deadlines = []
        
        # Страницы для парсинга в LMS
        pages = [
            '/my/',
            '/calendar/view.php?view=upcoming',
        ]
        
        for page in pages:
            try:
                url = f"https://lms.spbstu.ru{page}"
                print(f"🌐 Парсинг LMS: {url}")
                self.driver.get(url)
                sleep(3)
                
                # Здесь нужно будет добавить реальные селекторы для LMS
                # Пока пример
                events = self.driver.find_elements(By.CLASS_NAME, "event")
                
                for event in events:
                    try:
                        title = event.find_element(By.CLASS_NAME, "event-name").text
                        course = event.find_element(By.CLASS_NAME, "course-name").text
                        date = event.find_element(By.CLASS_NAME, "date").text
                        
                        deadline = Deadline(title, course, date, "lms")
                        deadlines.append(deadline)
                    except:
                        continue
                        
            except Exception as e:
                print(f"⚠️ Ошибка при парсинге {page}: {e}")
        
        return deadlines
    
    def parse_openedu_deadlines(self) -> list:
        """Парсит дедлайны с Openedu со страницы моих курсов"""
        deadlines = []
        
        try:
            # Шаг 1: Нажимаем на иконку профиля
            print("\n👤 Открываем меню профиля...")
            profile_icon = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "img.profile-menu__icon"))
            )
            profile_icon.click()
            sleep(2)
            
            # Шаг 2: Нажимаем "Мои курсы" в выпадающем меню
            print("📚 Переходим в 'Мои курсы'...")
            my_courses_link = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/my/courses/') and contains(text(), 'Мои курсы')]"))
            )
            my_courses_link.click()
            sleep(5)
            
            # Шаг 3: Получаем ВСЕ названия курсов
            print("🔍 Ищем все курсы...")
            
            # Находим все карточки курсов
            course_cards = self.driver.find_elements(By.CSS_SELECTOR, "div.ed-product-card")
            print(f"📊 Найдено карточек курсов: {len(course_cards)}")
            
            # Сохраняем названия курсов
            course_titles = []
            for card in course_cards:
                try:
                    title = card.find_element(By.CSS_SELECTOR, "div.ed-product-card__header__title span").text.strip()
                    course_titles.append(title)
                    print(f"  📌 Найден курс: {title}")
                except Exception as e:
                    print(f"  ⚠️ Ошибка при получении названия курса: {e}")
                    course_titles.append(f"Курс {len(course_titles) + 1}")
            
            # Шаг 4: Обрабатываем каждый курс по очереди
            for course_index, course_title in enumerate(course_titles, 1):
                try:
                    print(f"\n--- Обработка курса {course_index}: {course_title} ---")
                    
                    # Находим кнопку для текущего курса ЗАНОВО
                    course_buttons = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'К материалам курса')]")
                    
                    if course_index > len(course_buttons):
                        print(f"⚠️ Не найдена кнопка для курса {course_index}, пропускаем")
                        continue
                    
                    # Берем соответствующую кнопку
                    current_button = course_buttons[course_index - 1]
                    
                    # Прокручиваем до кнопки и кликаем
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", current_button)
                    sleep(1)
                    current_button.click()
                    print("✅ Перешли к материалам курса")
                    
                    sleep(5)  # Ждем загрузки страницы курса
                    
                    # Шаг 5: Ищем и нажимаем "Расписание курса"
                    try:
                        schedule_found = False
                        
                        # Варианты поиска расписания
                        selectors = [
                            "//a[contains(@class, 'nav-link') and contains(text(), 'Расписание курса')]",
                            "//a[contains(text(), 'Расписание')]",
                            "//a[contains(@href, 'dates')]",
                            "//a[contains(@class, 'nav-link') and contains(@href, 'static_tab')]"
                        ]
                        
                        for selector in selectors:
                            try:
                                schedule_link = self.driver.find_element(By.XPATH, selector)
                                schedule_link.click()
                                print("✅ Перешли в расписание курса")
                                schedule_found = True
                                break
                            except:
                                continue
                        
                        if not schedule_found:
                            print("⚠️ Ссылка на расписание не найдена")
                            self.driver.back()
                            sleep(3)
                            # Возвращаемся к списку курсов
                            self.driver.get('https://openedu.ru/my/courses/')
                            sleep(3)
                            continue
                        
                        sleep(5)
                        
                    except Exception as e:
                        print(f"⚠️ Ошибка при переходе в расписание: {e}")
                        self.driver.get('https://openedu.ru/my/courses/')
                        sleep(3)
                        continue
                    
                    # Шаг 6: Парсим таблицу расписания
                    try:
                        tables = self.driver.find_elements(By.TAG_NAME, "table")
                        
                        if not tables:
                            print("⚠️ Таблица не найдена на странице")
                        else:
                            print(f"📋 Найдено таблиц: {len(tables)}")
                            
                            for table_index, table in enumerate(tables, 1):
                                # Получаем все строки таблицы
                                rows = table.find_elements(By.TAG_NAME, "tr")
                                print(f"  Таблица {table_index}: найдено строк {len(rows)}")
                                
                                # Определяем количество колонок по заголовку
                                if len(rows) > 0:
                                    header_cells = rows[0].find_elements(By.TAG_NAME, "td") if rows[0].find_elements(By.TAG_NAME, "td") else rows[0].find_elements(By.TAG_NAME, "th")
                                    col_count = len(header_cells)
                                    print(f"    Колонок в таблице: {col_count}")
                                
                                # Пропускаем заголовочную строку (первую)
                                for row_index, row in enumerate(rows):
                                    if row_index == 0:  # Пропускаем заголовок
                                        continue
                                    
                                    try:
                                        # Получаем все ячейки в строке
                                        cells = row.find_elements(By.TAG_NAME, "td")
                                        
                                        if not cells:
                                            continue
                                        
                                        # Первая ячейка - название задания
                                        title = cells[0].text.strip()
                                        
                                        if not title:
                                            continue
                                        
                                        # Берем ПОСЛЕДНЮЮ ячейку как жесткий дедлайн
                                        last_cell = cells[-1]
                                        date_text = last_cell.text.strip()
                                        
                                        # Пропускаем если дата не указана или это специальное значение
                                        if not date_text or date_text == '-' or date_text == '—' or 'инд.' in date_text.lower():
                                            print(f"    ⚠️ Пропущен (нет даты): {title} -> {date_text}")
                                            continue
                                        
                                        # Парсим дату
                                        try:
                                            if '.' in date_text:
                                                parts = date_text.split('.')
                                                if len(parts) >= 2:
                                                    day = parts[0].strip().zfill(2)
                                                    month = parts[1].strip().zfill(2)
                                                    
                                                    # Определяем год
                                                    if len(parts) >= 3:
                                                        year = parts[2].strip()
                                                        if len(year) == 2:
                                                            year = f"20{year}"
                                                        elif len(year) == 4:
                                                            year = year
                                                        else:
                                                            year = "2026"
                                                    else:
                                                        year = "2026"
                                                    
                                                    # Проверяем корректность
                                                    if day.isdigit() and month.isdigit() and year.isdigit():
                                                        formatted_date = f"{year}-{month}-{day}"
                                                        
                                                        deadline = Deadline(
                                                            title=f"{course_title}: {title}",
                                                            course=course_title,
                                                            due_date=formatted_date,
                                                            source="openedu"
                                                        )
                                                        deadlines.append(deadline)
                                                        print(f"    ✅ Добавлен: {title[:50]}... -> {formatted_date}")
                                                    else:
                                                        print(f"    ⚠️ Некорректная дата: {date_text}")
                                                else:
                                                    print(f"    ⚠️ Неверный формат даты: {date_text}")
                                            else:
                                                print(f"    ⚠️ Дата не содержит точек: {date_text}")
                                                
                                        except Exception as e:
                                            print(f"    ⚠️ Ошибка парсинга даты '{date_text}': {e}")
                                            continue
                                            
                                    except Exception as e:
                                        print(f"    ⚠️ Ошибка обработки строки {row_index}: {e}")
                                        continue

                    except Exception as e:
                        print(f"⚠️ Ошибка при парсинге таблицы: {e}")
                    
                    # Шаг 7: Возвращаемся к списку курсов
                    print("⏎ Возвращаемся к списку курсов...")
                    self.driver.get('https://openedu.ru/my/courses/')
                    sleep(5)
                    
                except Exception as e:
                    print(f"⚠️ Ошибка при обработке курса {course_index}: {e}")
                    # Возвращаемся к списку курсов в случае ошибки
                    self.driver.get('https://openedu.ru/my/courses/')
                    sleep(5)
                    continue
            
            print(f"\n📌 Всего найдено дедлайнов Openedu: {len(deadlines)}")
            
        except Exception as e:
            print(f"❌ Ошибка при парсинге Openedu: {e}")
            self.driver.save_screenshot("openedu_parse_error.png")
        
        return deadlines
    
    def print_deadlines(self, deadlines: list, source_name: str):
        """Вывод дедлайнов в консоль"""
        if not deadlines:
            print(f"\n📭 Дедлайнов в {source_name} не найдено")
            return
        
        print(f"\n" + "="*60)
        print(f"📋 {source_name.upper()}: {len(deadlines)} дедлайнов")
        print("="*60)
        
        # Сортируем по дате
        sorted_deadlines = sorted(deadlines, key=lambda x: x.due_date)
        
        for i, deadline in enumerate(sorted_deadlines, 1):
            print(f"\n{i}. {deadline}")
    
    def save_all_deadlines(self):
        """Сохраняет все дедлайны в JSON"""
        if not self.deadlines:
            print("📭 Нет данных для сохранения")
            return
        
        # Создаем папку для данных, если её нет
        os.makedirs("data", exist_ok=True)
        
        # Сохраняем общий файл
        filename = f"data/deadlines_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        data = [d.to_dict() for d in self.deadlines]
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Все данные сохранены в {filename}")
    
    def show_menu(self):
        """Показывает меню и возвращает выбор пользователя"""
        print("\n" + "="*60)
        print("🚀 ПАРСЕР ДЕДЛАЙНОВ")
        print("="*60)
        print("1. Получить дедлайны из LMS СПбПУ")
        print("2. Получить дедлайны из Openedu")
        print("3. Получить из обоих источников")
        print("4. Выйти")
        print("-"*60)
        
        choice = input("Выберите действие (1-4): ").strip()
        return choice
    
    def run(self):
        """Основной метод запуска с меню"""
        while True:
            choice = self.show_menu()
            
            if choice == '4':
                print("\n👋 До свидания!")
                break
            
            if choice not in ['1', '2', '3']:
                print("\n❌ Неверный выбор. Попробуйте снова.")
                continue
            
            # Инициализируем драйвер
            self.init_driver()
            self.deadlines = []
            
            try:
                if choice == '1':
                    if self.login_lms():
                        print("\n🔍 Поиск дедлайнов в LMS...")
                        lms_deadlines = self.parse_lms_deadlines()
                        self.deadlines.extend(lms_deadlines)
                        self.print_deadlines(lms_deadlines, "LMS СПбПУ")
                
                elif choice == '2':
                    if self.login_openedu():
                        print("\n🔍 Поиск дедлайнов в Openedu...")
                        openedu_deadlines = self.parse_openedu_deadlines()
                        self.deadlines.extend(openedu_deadlines)
                        self.print_deadlines(openedu_deadlines, "Openedu")
                
                elif choice == '3':
                    # Сначала LMS
                    if self.login_lms():
                        print("\n🔍 Поиск дедлайнов в LMS...")
                        lms_deadlines = self.parse_lms_deadlines()
                        self.deadlines.extend(lms_deadlines)
                        self.print_deadlines(lms_deadlines, "LMS СПбПУ")
                    
                    # Затем Openedu
                    if self.login_openedu():
                        print("\n🔍 Поиск дедлайнов в Openedu...")
                        openedu_deadlines = self.parse_openedu_deadlines()
                        self.deadlines.extend(openedu_deadlines)
                        self.print_deadlines(openedu_deadlines, "Openedu")
                
                # Сохраняем результаты
                if self.deadlines:
                    self.save_all_deadlines()
                
            except Exception as e:
                print(f"\n❌ Ошибка: {e}")
            
            finally:
                if self.driver:
                    self.driver.quit()
            
            print("\n" + "-"*60)
            input("Нажмите Enter, чтобы продолжить...")


if __name__ == "__main__":
    # Загрузка credentials
    try:
        with open("misc/credentials.json", 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("❌ Файл credentials.json не найден в папке misc/")
        print("Создайте файл со структурой:")
        print("""
{
    "moodle": {
        "username": "your.email@edu.spbstu.ru",
        "password": "your_password"
    },
    "chrome": {
        "chrome_profile": ""
    }
}
        """)
        exit(1)
    
    # Создаем парсер
    parser = MoodleDeadlineParser(
        username=data['moodle']['username'],
        password=data['moodle']['password'],
        chrome_profile=data['chrome']['chrome_profile']
    )
    
    # Запускаем с меню
    parser.run()